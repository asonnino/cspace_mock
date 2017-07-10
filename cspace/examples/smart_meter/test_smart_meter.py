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
from smart_meter_checker  import app            as app_checker
from hashlib                import sha256
from binascii               import hexlify
import pytest
import requests

from multiprocessing import Process
import time

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
        print "The checker is already running:", e
        assert False

def start_cspace(app):
    try:
        app.run(host="127.0.0.1", port="5000", threaded=True)
    except Exception as e:
        print "The cspace is already running:", e
        assert False


##################################################################################
# tests
##################################################################################
# -------------------------------------------------------------------------------
# test 1
# try to validate a transaction (call the checker) at an hardcoded address
# -------------------------------------------------------------------------------
def test_request():
    # run the checker
    t = Process(target=start_checker, args=(app_checker,))
    t.start()
    time.sleep(0.1)

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
        t.terminate()
        t.join()

# -------------------------------------------------------------------------------
# test 2 - Init contract function
# -------------------------------------------------------------------------------
def test_Init():
    # run the checker
    t = Process(target=start_checker, args=(app_checker,))
    t.start()
    time.sleep(0.1)

    # create test vectors
    T_init = {
        "contractID"        : 101,
        "inputs"            : [],
        "referenceInputs"   : [],
        "parameters"        : [],
        "returns"           : [],
        "outputs"           : [dumps({"type":"SMToken"})],
        "dependencies"      : []
    }

    T_init_bad = {
        "contractID"        : 101,
        "inputs"            : [],
        "referenceInputs"   : [],
        "parameters"        : [],
        "returns"           : [],
        "outputs"           : [dumps({"type":"SMToken_other"})],
        "dependencies"      : []
    }

    # execute tests
    try:
        # test account creation
        r = requests.post(checker_url, data = dumps(T_init))
        #print(loads(r.text))
        assert loads(r.text)["status"] == "OK"

        # test a valid transfer
        r = requests.post(checker_url, data = dumps(T_init_bad))
        #print(loads(r.text))
        assert loads(r.text)["status"] == "ERROR"

    finally:
        t.terminate()
        t.join()

# -------------------------------------------------------------------------------
# test 3 -- Create Meter function
# -------------------------------------------------------------------------------

from petlib.ec import EcGroup
from petlib.ecdsa import do_ecdsa_sign
from petlib.pack import encode


from hashlib import sha256


def test_createMeter():
    # run the checker
    t = Process(target=start_checker, args=(app_checker,))
    t.start()
    time.sleep(0.1)

    Token = dumps({"type":"SMToken"})

    # Do some crypto:
    G = EcGroup()
    sig_key = G.order().random()
    Pub_raw = sig_key * G.generator()
    

    Pub = hexlify(encode(Pub_raw))
    Info = "YYY"

    digest = sha256("D" + str(len(Pub)) + "|" + Pub + "|" + str(len(Info)) + "|" + Info).digest()
    Sig_raw = do_ecdsa_sign(G, sig_key, digest)
    Sig = hexlify(encode(Sig_raw))

    Meter = dumps({
        "type":"SMMeter",
        "pub":Pub,
        "info":Info,
        "readings":hexlify(encode([]))
        })

    # create test vectors
    T_init = {
        "contractID"        : 102,
        "inputs"            : [Token],
        "referenceInputs"   : [],
        "parameters"        : [Pub, Info, Sig],
        "returns"           : [],
        "outputs"           : [Token, Meter],
        "dependencies"      : []
    }

    # execute tests
    try:
        # test account creation
        r = requests.post(checker_url, data = dumps(T_init))
        #print(loads(r.text))
        assert loads(r.text)["status"] == "OK"

        
    finally:
        t.terminate()
        t.join()

# -------------------------------------------------------------------------------
# test 4 -- Add reading test
# -------------------------------------------------------------------------------

from petlib.ec import EcGroup
from petlib.ecdsa import do_ecdsa_sign
from petlib.pack import encode


from hashlib import sha256


def test_addReadings():
    # run the checker
    t = Process(target=start_checker, args=(app_checker,))
    t.start()
    time.sleep(0.1)

    Token = dumps({"type":"SMToken"})

    # Do some crypto:
    G = EcGroup()
    sig_key = G.order().random()
    Pub_raw = sig_key * G.generator()
    

    Pub = hexlify(encode(Pub_raw))
    Info = "YYY"

    Meter = dumps({
        "type":"SMMeter",
        "pub":Pub,
        "info":Info,
        "readings":hexlify(encode([]))
        })

    g = G.hash_to_point("g")
    h = G.hash_to_point("h")
    readings = [10, 20, 30, 10, 50]
    openings = [G.order().random() for _ in readings]
    commitments = (674, [r*g + o*h for r,o in zip(readings, openings)])

    Meter2 = dumps({
        "type":"SMMeter",
        "pub":Pub,
        "info":Info,
        "readings": hexlify(encode([] + [commitments]))
        })

    # Compute the commitments
    bin_commitments = hexlify(encode(commitments))
    digest = sha256("D" + str(len(Meter)) + "|" + Meter + "|" + str(len(bin_commitments)) + "|" + bin_commitments).digest()
    Sig_raw = do_ecdsa_sign(G, sig_key, digest)
    Sig = hexlify(encode(Sig_raw))


    # create test vectors
    T_AddReadings = {
        "contractID"        : 103,
        "inputs"            : [Meter],
        "referenceInputs"   : [],
        "parameters"        : [bin_commitments, Sig],
        "returns"           : [],
        "outputs"           : [Meter2],
        "dependencies"      : []
    }

    # execute tests
    try:
        # test account creation
        r = requests.post(checker_url, data = dumps(T_AddReadings))
        #print(loads(r.text))
        assert loads(r.text)["status"] == "OK"

        
    finally:
        t.terminate()
        t.join()

# -------------------------------------------------------------------------------
# test 5 -- Create Meter function
# -------------------------------------------------------------------------------

from petlib.ec import EcGroup
from petlib.ecdsa import do_ecdsa_sign
from petlib.pack import encode


from hashlib import sha256


def test_computeBill():
    # run the checker
    t = Process(target=start_checker, args=(app_checker,))
    t.start()
    time.sleep(0.1)


    # Do some crypto:
    G = EcGroup()
    sig_key = G.order().random()
    Pub_raw = sig_key * G.generator()
    

    Pub = hexlify(encode(Pub_raw))
    Info = "YYY"

    g = G.hash_to_point("g")
    h = G.hash_to_point("h")
    readings = [10, 20, 30, 10, 50]
    openings = [G.order().random() for _ in readings]
    commitments = (674, [r*g + o*h for r,o in zip(readings, openings)])

    # Compute the commitments
    bin_commitments = hexlify(encode(commitments))
    

    Meter = dumps({
        "type":"SMMeter",
        "pub":Pub,
        "info":Info,
        "readings":hexlify(encode([commitments]))
        })


    Meter2 = Meter
    tarrifs = [3, 5, 3, 5, 3]
    totalBill = sum(r*t for r,t in zip(readings, tarrifs))
    totalOpen = sum(r*t for r,t in zip(openings, tarrifs)) % G.order()

    proof = hexlify(encode(totalOpen * h))

    Bill = dumps({
        "type":"SMBill",
        "info": Info,
        "period": 674,
        "bill": totalBill
        })

    # create test vectors
    T_computeBill = {
        "contractID"        : 104,
        "inputs"            : [Meter],
        "referenceInputs"   : [],
        "parameters"        : [str(0), hexlify(encode(tarrifs)), 
                               str(totalBill), proof],
        "returns"           : [],
        "outputs"           : [Meter2, Bill],
        "dependencies"      : []
    }

    # execute tests
    try:
        # test account creation
        r = requests.post(checker_url, data = dumps(T_computeBill))
        #print(loads(r.text))
        assert loads(r.text)["status"] == "OK"

        
    finally:
        t.terminate()
        t.join()



# -------------------------------------------------------------------------------
# test 2
# final check: simulate a complete transfer & account creation
# -------------------------------------------------------------------------------
def test_transaction():
    # run checker and cspace
    t1 = Process(target=start_checker, args=(app_checker,))
    t1.start()
    t2 = Process(target=start_cspace, args=(app_cspace,))
    t2.start()
    time.sleep(0.2)

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
        print(loads(r.text))
        assert loads(r.text)["status"] == "OK"


    finally:
        t1.terminate()
        t2.terminate()
        t1.join()
        t2.join()

        import os
        import os.path
        if os.path.isfile("db.json"):
            os.remove("db.json")


##################################################################################