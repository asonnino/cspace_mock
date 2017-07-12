##################################################################################
# Chainspace Mock
# bank_transfer_checker.py
#
# version: 0.0.1
##################################################################################
from json       import loads, dumps
from flask      import Flask, request
from hashlib    import sha256
from binascii   import hexlify, unhexlify

import petlib
from petlib.pack    import encode, decode
from petlib.ecdsa   import do_ecdsa_sign, do_ecdsa_verify
from vote_lib       import binencrypt, verifybin, verifyone, verifyzero, add, sub


##################################################################################
# utils
##################################################################################
def H(x):
    return hexlify(sha256(x).digest())

def pack(x):
    return hexlify(encode(x))

def unpack(x):
    return decode(unhexlify(x))

def ccheck(V, msg):
    if not V:
        raise Exception(msg)


##################################################################################
# checker
##################################################################################
def checker_function(T):

    # ----------------------------------------------------------------------------
    # create new vote event
    # ----------------------------------------------------------------------------  
    if T["contractID"] == 1:
        """
        # check transfer's format
        ccheck(len(T["inputs"]) == 0, "Expect no inputs")
        ccheck(len(T["referenceInputs"]) == 0, "Expect no references")
        ccheck(len(T["parameters"]) == 0, "Expect no parameters")
        ccheck(len(T["returns"]) == 0, "Expect no returns")
        ccheck(len(T["outputs"]) == 1, "Expect exactly 1 output")

        # check integrity of the new account
        newAccount = loads(T[u"outputs"][0])
        ccheck(newAccount["accountId"] != None, "Malformed account")
        ccheck(newAccount["amount"] == 10, "Incorrect initial ammount")
        """


    # ----------------------------------------------------------------------------
    # add vote
    # ---------------------------------------------------------------------------- 
    elif T["contractID"] == 2:

        # load
        input_obj  = loads(T["inputs"][0])
        output_obj = loads(T["outputs"][0])

        ##
        ## check format
        ##
        # check input and output are consistents
        if input_obj["options"] != output_obj["options"]:
            raise Exception("Malformed transaction")
        if input_obj["tally_pk"] != output_obj["tally_pk"]:
            raise Exception("Malformed transaction")
        if input_obj["params"] != output_obj["params"]:
            raise Exception("Malformed transaction")

        # check length of scores, votes and options
        length = len(input_obj["options"])
        if len(input_obj["scores"]) != length:
            raise Exception("Malformed transaction")
        if len(output_obj["options"]) != length:
            raise Exception("Malformed transaction")
        if len(output_obj["scores"]) != length:
            raise Exception("Malformed transaction")
        if len(loads(T["parameters"][0])["votes"]) != length:
            raise Exception("Malformed transaction")


        ##
        ## retrieve data
        ##
        # parameters
        params      = unpack(input_obj["params"])
        tally_pk    = unpack(input_obj["tally_pk"])

        # votes
        old_scores  = input_obj["scores"]
        new_scores  = output_obj["scores"]
        votes       = loads(T["parameters"][0])["votes"]

        # voters pk
        old_voters_pk   = input_obj["voters_pk"]
        new_voters_pk   = output_obj["voters_pk"]
        voter_pk        = unpack(loads(T["parameters"][0])["voter_pk"])

        # signature
        sig = unpack(loads(T["parameters"][0])["signature"])

        # proofs
        binary_proof      = loads(T["parameters"][1])["binary"]
        sum_proof         = unpack(loads(T["parameters"][1])["sum"])
        consistency_proof = loads(T["parameters"][1])["consistency"]
        
      
        ##
        ## verify voter's signature
        ##
        hasher = sha256()
        ##hasher.update(dumps(input_obj))
        ##print H(dumps(input_obj))
        hasher.update(dumps(votes))
        (G, _, _, _) = params
        if not do_ecdsa_verify(G, voter_pk, sig, hasher.digest()):
            raise Exception("Signature does not match")

        ##
        ## verify that voter is in the list
        ##
        if not pack(voter_pk) in old_voters_pk:
            raise Exception("Voter unauthorised")

        ##
        ## verify that voter's has been removed from list
        ##
        if pack(voter_pk) in new_voters_pk:
            raise Exception("Malformed transaction")

        ##
        ## verify proof that votes are either zero or one
        ##
        for i in range(len(old_scores)):
            if not verifybin(params, tally_pk, unpack(votes[i]), unpack(binary_proof[i])):
                raise Exception("Votes have to be either zero or one")

        ##
        ## verify proof that sum of votes is exactly one
        ##
        sum_votes = unpack(votes[-1])
        for i in range(len(old_scores)-1):
            sum_votes = add(sum_votes, unpack(votes[i]))
        if not verifyone(params, tally_pk, sum_votes, sum_proof):
            raise Exception("Votes have to sum up to 1")

        ##
        ## verify proof that output == input + vote
        ##
        for i in range(len(old_scores)):
            tmp = add(unpack(votes[i]), unpack(old_scores[i]))
            tmp = sub(tmp, unpack(new_scores[i]))
            if not verifyzero(params, tally_pk, tmp, unpack(consistency_proof[i])):
                raise Exception("Mismatch input/output")


    # ----------------------------------------------------------------------------
    # tally
    # ---------------------------------------------------------------------------- 
    elif T["contractID"] == 3:
        # load
        input_obj  = loads(T["inputs"][0])
        output_obj = loads(T["outputs"][0])

        ##
        ## check format
        ##
        # check input and output are consistents
        if input_obj["options"] != output_obj["options"]:
            raise Exception("Malformed transaction")
        if input_obj["tally_pk"] != output_obj["tally_pk"]:
            raise Exception("Malformed transaction")
        if input_obj["params"] != output_obj["params"]:
            raise Exception("Malformed transaction")

        # check length of scores, votes and options
        length = len(input_obj["options"])
        if len(input_obj["scores"]) != length:
            raise Exception("Malformed transaction")
        if len(output_obj["options"]) != length:
            raise Exception("Malformed transaction")
        if len(output_obj["scores"]) != length:
            raise Exception("Malformed transaction")

        ##
        ## retrieve data
        ##
        # parameters
        params      = unpack(input_obj["params"])
        tally_pk    = unpack(input_obj["tally_pk"])

        # signature
        sig = unpack(output_obj["signature"])

        ##
        ## verify signature
        ##
        hasher = sha256()
        hasher.update(T["inputs"][0])
        hasher.update(dumps(output_obj["options"]))
        hasher.update(dumps(output_obj["scores"]))
        (G, _, _, _) = params
        if not do_ecdsa_verify(G, tally_pk, sig, hasher.digest()):
            raise Exception("Signature does not match")
     
        
    # ----------------------------------------------------------------------------
    # wrong method
    # ---------------------------------------------------------------------------- 
    else:
        raise Exception("Wrong method")

    ##
    ## return
    ##
    return {"status": "OK"}



##################################################################################
# webapp
##################################################################################
# the state of the infrastructure
app = Flask(__name__)

# -------------------------------------------------------------------------------
# /vote
# checker the correctness of a vote operation
# -------------------------------------------------------------------------------
@app.route("/vote", methods=["GET", "POST"])
def check():
    if request.method == "POST":
        try:
            return dumps(checker_function(loads(request.data)))
        except KeyError as e:
            return dumps({"status": "ERROR", "message": e.args})
        except Exception as e:
            return dumps({"status": "ERROR", "message": e.args})
    else:
        return dumps({"status": "ERROR", "message":"Use POST method."})


##################################################################################
# execute
##################################################################################
if __name__ == "__main__": 
    app.run(host="127.0.0.1", port="5001") 


##################################################################################