##################################################################################
# Chainspace Mock
# vote.py
#
# version: 0.0.1
##################################################################################
import sys
sys.path.append('../../')
from multiprocessing        import Process
from json                   import loads, dumps
from threading              import Thread
from cspace_service         import app            as app_cspace
from vote_checker           import app            as app_checker
from hashlib                import sha256
from binascii               import hexlify, unhexlify
import pytest
import requests
import time

import petlib
from petlib.pack    import encode, decode
from petlib.ecdsa   import do_ecdsa_sign, do_ecdsa_verify
from vote_lib       import setup, key_gen, add, sub, make_table, dec, binencrypt
from vote_lib       import provebin, proveone, provezero, verifyone, verifybin



##################################################################################
# utils
##################################################################################
def H(x):
    return hexlify(sha256(x).digest())

def pack(x):
    return hexlify(encode(x))

def unpack(x):
    return decode(unhexlify(x))


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
# variables
##################################################################################
# URLs
node_url      =  r"http://127.0.0.1:5000/process"
checker_url   =  r"http://127.0.0.1:5001/vote"

# AHEG parameters
params          = setup()
(G, g, hs, o)   = params
(priv, pub)     = key_gen(params)



##################################################################################
# tests
##################################################################################
# -------------------------------------------------------------------------------
# test 1
# try to validate a transaction (call the checker) at an hardcoded address
# -------------------------------------------------------------------------------
def test_request():
    ##
    ## run the checker
    ##
    t = Process(target=start_checker, args=(app_checker,))
    t.start()
    time.sleep(0.1)


    ##
    ## add vote
    ##
    # generate voter's key
    (voter1_priv, voter1_pub) = key_gen(params)

    # input scores
    input_a1, input_b1, input_k1 = binencrypt(params, pub, 0)   # Alice's initial score is 0
    input_c1 = (input_a1, input_b1)
    input_a2, input_b2, input_k2 = binencrypt(params, pub, 0)   # Bob's initial score is 0
    input_c2 = (input_a2, input_b2)
    vote_T0 = {
        "options"   : ["Alice", "Bob"],
        "scores"    : [pack(input_c1), pack(input_c2)],
        "voters_pk" : ["voter2_pk", pack(voter1_pub)],
        "params"    : pack(params),
        "tally_pk"  : pack(pub)
    }

    # output scores
    output_a1, output_b1, output_k1 = binencrypt(params, pub, 1)   # Alice's score is 1
    output_c1 = (output_a1, output_b1)
    output_a2, output_b2, output_k2 = binencrypt(params, pub, 0)   # Bob's score is 0
    output_c2 = (output_a2, output_b2)
    vote_T1 = {
        "options"   : ["Alice", "Bob"],
        "scores"    : [pack(output_c1), pack(output_c2)],
        "voters_pk" : ["voter2_pk"],
        "params"    : pack(params),
        "tally_pk"  : pack(pub)
    }

    # new votes
    vote_a1, vote_b1, vote_k1 = binencrypt(params, pub, 1)      # user is voting for Alice
    vote_c1 = (vote_a1, vote_b1)
    vote_a2, vote_b2, vote_k2 = binencrypt(params, pub, 0)      # user is not voting for Bob
    vote_c2 = (vote_a2, vote_b2)
    # signature
    hasher = sha256()
    ##hasher.update(dumps(vote_T0))
    ##print H(dumps(vote_T0))
    hasher.update(dumps([pack(vote_c1), pack(vote_c2)]))
    sig = do_ecdsa_sign(G, voter1_priv, hasher.digest()) 
    # pack parameters
    vote_parameters = {
        "votes"     : [pack(vote_c1), pack(vote_c2)],
        "voter_pk"  : pack(voter1_pub),
        "signature" : pack(sig)
    }
    

    # proof that votes are binary values
    # this also prove knowledge of the votes and that the ciphertexts are well-formed
    binProof1 = provebin(params, pub, (vote_a1,vote_b1), vote_k1, 1)
    binProof2 = provebin(params, pub, (vote_a2,vote_b2), vote_k2, 0)

    # proof that votes sum up to 1
    sum_c = add(vote_c1, vote_c2)
    sum_k = (vote_k1 + vote_k2) % o
    sumProof = proveone(params, pub, sum_c, sum_k)

    # proof that output == input + vote
    tmp_c1 = add(input_c1, vote_c1)
    tmp_c1 = sub(tmp_c1, output_c1)
    tmp_k1 = (input_k1 + vote_k1 - output_k1) % o
    consistencyProof1 = provezero(params, pub, tmp_c1, tmp_k1)
    tmp_c2 = add(input_c2, vote_c2)
    tmp_c2 = sub(tmp_c2, output_c2)
    tmp_k2 = (input_k2 + vote_k2 - output_k2) % o
    consistencyProof2 = provezero(params, pub, tmp_c2, tmp_k2)

    # pack proofs
    proofs = {
        "binary"      : [pack(binProof1), pack(binProof2)],                 # proof that votes are binary values
        "sum"         : pack(sumProof),                                     # proof that votes sum up to 1
        "consistency" : [pack(consistencyProof1), pack(consistencyProof2)]  # proof that output == input + vote 
    }

    # pack transaction
    add_vote = {
        "contractID"        : 2,
        "inputs"            : [dumps(vote_T0)],
        "referenceInputs"   : [],
        "parameters"        : [dumps(vote_parameters), dumps(proofs)],
        "returns"           : [],
        "outputs"           : [dumps(vote_T1)],
        "dependencies"      : []
    }



    ##
    ## tally
    ##
    # final score
    scores = [1, 0]

    # sign
    hasher = sha256()
    hasher.update(dumps(vote_T1))
    hasher.update(dumps(["Alice", "Bob"]))
    hasher.update(dumps(scores))
    tally_sig = do_ecdsa_sign(G, priv, hasher.digest())

    # pack
    result = {
        "options"   : ["Alice", "Bob"],
        "scores"    : scores,
        "params"    : pack(params),
        "tally_pk"  : pack(pub),
        "signature" : pack(tally_sig)
    }
    tally = {
        "contractID"        : 3,
        "inputs"            : [dumps(vote_T1)],
        "referenceInputs"   : [],
        "parameters"        : [],
        "returns"           : [],
        "outputs"           : [dumps(result)],
        "dependencies"      : []
    }



    ##
    # execute tests
    ##
    try:

        # test adding vote
        r = requests.post(checker_url, data = dumps(add_vote))
        print(loads(r.text))
        assert loads(r.text)["status"] == "OK"

        # test adding vote
        r = requests.post(checker_url, data = dumps(tally))
        print(loads(r.text))
        assert loads(r.text)["status"] == "OK"

    finally:
        t.terminate()
        t.join()


# -------------------------------------------------------------------------------
# test 2
# final check: simulate a complete transfer & account creation
# -------------------------------------------------------------------------------
"""
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
"""

##################################################################################