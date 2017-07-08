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
from sensor_data_checker    import app            as app_checker
from hashlib                import sha256
from binascii               import hexlify
import pytest
import requests


##################################################################################
# variables
##################################################################################
# checker URL
node_url      =  r"http://127.0.0.1:5000/process"
checker_url   =  r"http://127.0.0.1:5001/value/add"

# old accounts (before transaction)
sensor1_T0 = {"accountId": "sensor1", "temperature": [], "time" : []}
sensor1_T1 = {"accountId": "sensor1", "temperature": [20], "time" : ["T1"]}
sensor1_T2 = {"accountId": "sensor1", "temperature": [20, 21], "time" : ["T1", "T2"]}
sensor1_T3 = {"accountId": "sensor1", "temperature": [20, 21, 25], "time" : ["T1", "T2", "T3"]}




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
        print "\nThe checker is already running.\n"

def start_cspace(app): # pragma: no cover
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
    initSensor = {
        "contractID"        : 300,
        "inputs"            : [],
        "referenceInputs"   : [],
        "parameters"        : [],
        "returns"           : [],
        "outputs"           : [dumps(sensor1_T0)],
        "dependencies"      : []
    }
    addMeasurement = {
        "contractID"        : 301,
        "inputs"            : [dumps(sensor1_T0)],
        "referenceInputs"   : [],
        "parameters"        : [dumps({"temperature" : 20}), dumps({"time" : "T1"})],
        "returns"           : [],
        "outputs"           : [dumps(sensor1_T1)],
        "dependencies"      : []
    }
    addInvalidMeasurement = {
        "contractID"        : 301,
        "inputs"            : [dumps(sensor1_T0)],
        "referenceInputs"   : [],
        "parameters"        : [dumps({"temperature" : 25}), dumps({"time" : "T2"})],
        "returns"           : [],
        "outputs"           : [dumps(sensor1_T2)],
        "dependencies"      : []
    }
    malformedOperation = {
        "contractID"        : 301,
        # missing inputs
        "referenceInputs"   : [],
        "parameters"        : [dumps({"temperature" : 20}), dumps({"time" : "T1"})],
        "returns"           : [],
        "outputs"           : [dumps(sensor1_T1)],
        "dependencies"      : []
    }
    invalidOperation = {
        "contractID"        : 0,
        "inputs"            : [dumps(sensor1_T0)],
        "referenceInputs"   : [],
        "parameters"        : [dumps({"temperature" : 20}), dumps({"time" : "T1"})],
        "returns"           : [],
        "outputs"           : [dumps(sensor1_T1)],
        "dependencies"      : []
    }

    # execute tests
    try:
        # init sensor
        r = requests.post(checker_url, data = dumps(initSensor))
        assert loads(r.text)["status"] == "OK"

        # add valid measurement
        r = requests.post(checker_url, data = dumps(addMeasurement))
        assert loads(r.text)["status"] == "OK"

        # add invalid measurement
        r = requests.post(checker_url, data = dumps(addInvalidMeasurement))
        assert loads(r.text)["status"] == "ERROR"

        # test malformed transaction
        r = requests.post(checker_url, data = dumps(malformedOperation))
        assert loads(r.text)["status"] == "ERROR"

        # test invalid operation
        r = requests.post(checker_url, data = dumps(invalidOperation))
        assert loads(r.text)["status"] == "ERROR"

        # try a get request
        r = requests.get(checker_url)
        assert loads(r.text)["status"] == "ERROR"

    finally:
        t._Thread__stop()


# -------------------------------------------------------------------------------
# test 2
# final check: add a measurement
# -------------------------------------------------------------------------------
def test_transaction():
    # run checker and cspace
    t1 = Thread(target=start_checker, args=(app_checker,))
    t1.start()
    t2 = Thread(target=start_cspace, args=(app_cspace,))
    t2.start()

    try:
        ##
        # init sensor
        ##
        T = {
            "contractID"        : 300,
            "inputIDs"          : [],
            "referenceInputIDs" : [],
            "parameters"        : [],
            "returns"           : [],
            "outputs"           : [dumps(sensor1_T0)],
            "dependencies"      : []
        }
        store = []
        packet = {"transaction": T, "store": store};

        # sumbit the transaction to the ledger
        r = requests.post(node_url, data = dumps(packet))
        print(loads(r.text))
        assert loads(r.text)["status"] == "OK"


        ##
        # add a first measurement
        ##
        ID1 = H( H(dumps(T)) +"|"+ dumps(sensor1_T0))
        T = {
            "contractID"        : 301,
            "inputIDs"          : [ID1],
            "referenceInputIDs" : [],
            "parameters"        : [dumps({"temperature" : 20}), dumps({"time" : "T1"})],
            "returns"           : [],
            "outputs"           : [dumps(sensor1_T1)],
            "dependencies"      : []
        }
        store = [
            {"key" : ID1, "value" : dumps(sensor1_T0)}
        ]
        packet = {"transaction": T, "store": store};

        # sumbit the transaction to the ledger
        r = requests.post(node_url, data = dumps(packet))
        print(loads(r.text))
        assert loads(r.text)["status"] == "OK"


        ##
        # add a second measurement
        ##
        ID1 = H( H(dumps(T)) +"|"+ dumps(sensor1_T1))
        T = {
            "contractID"        : 301,
            "inputIDs"          : [ID1],
            "referenceInputIDs" : [],
            "parameters"        : [dumps({"temperature" : 21}), dumps({"time" : "T2"})],
            "returns"           : [],
            "outputs"           : [dumps(sensor1_T2)],
            "dependencies"      : []
        }
        store = [
            {"key" : ID1, "value" : dumps(sensor1_T1)}
        ]
        packet = {"transaction": T, "store": store};

        # sumbit the transaction to the ledger
        r = requests.post(node_url, data = dumps(packet))
        print(loads(r.text))
        assert loads(r.text)["status"] == "OK"



    finally:
        t1._Thread__stop()
        t2._Thread__stop()


##################################################################################