##################################################################################
# Chainspace Mock
# test_bank_transfer.py
#
# version: 0.0.1
##################################################################################
import sys
sys.path.append('../../')
from json                   import loads, dumps
from threading              import Thread
from cspace_service         import app            as app_cspace
from bank_transfer_checker  import app            as app_checker
from hashlib                import sha256
from binascii               import hexlify
import pytest
import requests


##################################################################################
# variables
##################################################################################
# URLs
node_url      =  r"http://127.0.0.1:5000/process"
checker_url   =  r"http://127.0.0.1:5001/bank/transfer"

# old accounts (before money transfer)
Sally_account = {"accountId": "Sally", "amount": 10}
Alice_account = {"accountId": "Alice", "amount": 10}

# new accounts (after money transfer)
Sally_account_new = {"accountId": "Sally", "amount": 2}
Alice_account_new = {"accountId": "Alice", "amount": 18}


##################################################################################
# utils
##################################################################################
def H(x):
    return hexlify(sha256(x).digest())


##################################################################################
# run the checker's service
##################################################################################
def start_checker(app):
    try:
        app.run(host="127.0.0.1", port="5001", threaded=True)
    except Exception as e:
        print "The checker is already running."

def start_cspace(app):
    app.run(host="127.0.0.1", port="5000", threaded=True)


##################################################################################
# tests
##################################################################################
# -------------------------------------------------------------------------------
# test 1
# try to validate a transaction (call the checker) at an hardcoded address
# -------------------------------------------------------------------------------
def test_request():
    # run the checker
    t = Thread(target=start_checker, args=(app_checker,))
    t.start()

    # create test vectors
    createAccount = {
        "contractID"        : 1,
        "inputs"            : [],
        "referenceInputs"   : [],
        "parameters"        : [],
        "returns"           : [],
        "outputs"           : [dumps(Sally_account)],
        "dependencies"      : []
    }
    transfer = {
        "contractID"        : 2,
        "inputs"            : [dumps(Sally_account), dumps(Alice_account)],
        "referenceInputs"   : [],
        "parameters"        : [dumps({"amount":8})],
        "returns"           : [],
        "outputs"           : [dumps(Sally_account_new), dumps(Alice_account_new)],
        "dependencies"      : []
    }
    invalidTransfer = {
        "contractID"        : 2,
        "inputs"            : [dumps(Sally_account), dumps(Alice_account)],
        "referenceInputs"   : [],
        "parameters"        : [dumps({"amount":100})],
        "returns"           : [],
        "outputs"           : [dumps(Sally_account_new), dumps(Alice_account_new)],
        "dependencies"      : []
    }
    malformedTransfer = {
        "contractID"        : 2,
        # inputs are missing
        "referenceInputs"   : [],
        "parameters"        : [dumps({"amount":8})],
        "returns"           : [],
        "outputs"           : [dumps(Sally_account_new), dumps(Alice_account_new)],
        "dependencies"      : []
    }
    invalidOperation = {
        "contractID"        : 100,
        "inputs"            : [dumps(Sally_account), dumps(Alice_account)],
        "referenceInputs"   : [],
        "parameters"        : [dumps({"amount":1})],
        "returns"           : [],
        "outputs"           : [dumps(Sally_account_new), dumps(Alice_account_new)],
        "dependencies"      : []
    }

    # execute tests
    try:
        # test account creation
        r = requests.post(checker_url, data = dumps(createAccount))
        #print(loads(r.text))
        assert loads(r.text)["status"] == "OK"

        # test a valid transfer
        r = requests.post(checker_url, data = dumps(transfer))
        #print(loads(r.text))
        assert loads(r.text)["status"] == "OK"

        # test a transfer with invalid amount
        r = requests.post(checker_url, data = dumps(invalidTransfer))
        #print(loads(r.text))
        assert loads(r.text)["status"] == "ERROR"

        # test malformed transaction
        r = requests.post(checker_url, data = dumps(malformedTransfer))
        #print(loads(r.text))
        assert loads(r.text)["status"] == "ERROR"

        # test invalid operation
        r = requests.post(checker_url, data = dumps(invalidOperation))
        #print(loads(r.text))
        assert loads(r.text)["status"] == "ERROR"

        # get request
        r = requests.get(checker_url)
        #print(loads(r.text))
        assert loads(r.text)["status"] == "ERROR"

    finally:
        t._Thread__stop()


# -------------------------------------------------------------------------------
# test 2
# final check: simulate a complete transfer & account creation
# -------------------------------------------------------------------------------
def test_transaction():
    # run checker and cspace
    t1 = Thread(target=start_checker, args=(app_checker,))
    t1.start()
    t2 = Thread(target=start_cspace, args=(app_cspace,))
    t2.start()

    try:
        ##
        # create Alice's account
        ##
        T1 = {
            "contractID"        : 1,
            "inputIDs"          : [],
            "referenceInputIDs" : [],
            "parameters"        : [],
            "returns"           : [],
            "outputs"           : [dumps(Sally_account)],
            "dependencies"      : []
        }
        store1 = []
        packet1 = {"transaction": T1, "store": store1}

        ##
        # create Sally's account
        ##
        T2 = {
            "contractID"        : 1,
            "inputIDs"          : [],
            "referenceInputIDs" : [],
            "parameters"        : [],
            "returns"           : [],
            "outputs"           : [dumps(Alice_account)],
            "dependencies"      : []
        }
        store2 = []
        packet2 = {"transaction": T2, "store": store2}

        ##
        # make the transfer
        ##
        ID1 = H( H(dumps(T1)) +"|"+ dumps(Sally_account))
        ID2 = H( H(dumps(T2)) +"|"+ dumps(Alice_account))
        T3 = {
            "contractID"        : 2,
            "inputIDs"          : [ID1, ID2],
            "referenceInputIDs" : [],
            "parameters"        : [dumps({"amount":8})],
            "returns"           : [],
            "outputs"           : [dumps(Sally_account_new), dumps(Alice_account_new)],
            "dependencies"      : [dumps(packet1), dumps(packet2)]
        }
        store3 = [
            {"key": ID1, "value": dumps(Sally_account)},
            {"key": ID2, "value": dumps(Alice_account)}
        ]
        packet3 = {"transaction": T3, "store": store3}


        ##
        # sumbit the transaction to the ledger
        ##
        r = requests.post(node_url, data = dumps(packet3))
        #print(loads(r.text))
        assert loads(r.text)["status"] == "OK"


    finally:
        t1._Thread__stop()
        t2._Thread__stop()


##################################################################################