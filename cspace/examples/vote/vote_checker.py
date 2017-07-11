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
from petlib.pack import encode, decode
from vote_lib import binencrypt, verifybin, verifyone, verifyzero, add, sub


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
        ##
        ## check format
        ##
        # check length of scores and votes


        ##
        ## retrieve data
        ##
        old_scores  = loads(T["inputs"][0])["scores"]
        new_scores  = loads(T["outputs"][0])["scores"]
        votes       = loads(T["parameters"][1])["votes"]

        params      = unpack(loads(T["parameters"][0])["params"])
        tally_pk    = unpack(loads(T["parameters"][0])["tally_pk"])
        
        binary_proof      = loads(T["parameters"][2])["binary"]
        sum_proof         = unpack(loads(T["parameters"][2])["sum"])
        consistency_proof = loads(T["parameters"][2])["consistency"]
        

        ##
        ## verify voter's signature
        ##

        ##
        ## verify that voter is in the list
        ##

        ##
        ## verify that voter's has been removed from list
        ##

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


        
    ##
    ## wrong method
    ##
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