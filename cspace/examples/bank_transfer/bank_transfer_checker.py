##################################################################################
# Chainspace Mock
# bank_transfer_checker.py
#
# version: 0.0.1
##################################################################################
from json  import loads, dumps
from flask import Flask, request


##################################################################################
# checker
##################################################################################

# -------------------------------------------------------------------------------
# helper
# -------------------------------------------------------------------------------
def ccheck(V, msg):
    if not V:
        raise Exception(msg)

# -------------------------------------------------------------------------------
# checker
# -------------------------------------------------------------------------------      
def checker_function(T):

    # debug
    #print(T)

    ##
    ## create a new bank account
    ##
    if T["contractID"] == 1:
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


    ##
    ## check back transfer
    ##
    elif T["contractID"] == 2:
        # check transfer's format
        ccheck(len(T["inputs"]) == 2, "Expect exactly 2 inputs")
        ccheck(len(T["referenceInputs"]) == 0, "Expect no references")
        ccheck(len(T["parameters"]) == 1, "Expect exactly 1 parameter")
        ccheck(len(T["returns"]) == 0, "Expect no returns")
        ccheck(len(T["outputs"]) == 2, "Expect exactly 2 outputs")

        # retrieve inputs
        from_account     = loads(T[u"inputs"][0])
        to_account       = loads(T[u"inputs"][1])
        amount           = loads(T[u"parameters"][0])["amount"]
        from_account_new = loads(T[u"outputs"][0])
        to_account_new   = loads(T[u"outputs"][1])

        # check positive amount
        ccheck(0 < amount, "Transfer should be positive")

        # check sender and receiver account
        ccheck(from_account["accountId"] == from_account_new["accountId"],  "Old and new account do not match")
        ccheck(to_account["accountId"]   == to_account_new["accountId"],    "Old and new account do not match")

        # check that the sender has enough fundings
        ccheck(amount <= from_account["amount"], "No funds available")

        # check integrity of the operation
        ccheck(from_account["amount"] - amount == from_account_new["amount"], "Incorrect new balance")
        ccheck(to_account["amount"]   + amount == to_account_new["amount"],   "Incorrect new balance")


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
# /bank/transfer
# checker the correctness of a bank transfer
# -------------------------------------------------------------------------------
@app.route("/bank/transfer", methods=["GET", "POST"])
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