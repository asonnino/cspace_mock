##################################################################################
# Chainspace Mock
# smart_meter_checker.py
#
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

##
## Types created by this contract:
## (1) SMToken (2) SMMeter (3) SMBill


##
## Initialize new meter creation.
##

def check_init(T):
    ccheck(len(T["inputs"]) == 0, "Expect no inputs")
    ccheck(len(T["referenceInputs"]) == 0, "Expect no references")
    ccheck(len(T["parameters"]) == 0, "Expect no parameters")
    ccheck(len(T["returns"]) == 0, "Expect no returns")
    ccheck(len(T["outputs"]) == 1, "Expect exactly 1 output")

    # check integrity of the new token
    Token = loads(T[u"outputs"][0])

    ccheck(Token["type"] == "SMToken", "Expected SMToken")

##
## Update meter with new readings.
##

from petlib.ec import EcGroup
from petlib.ecdsa import do_ecdsa_sign, do_ecdsa_verify
from petlib.pack import encode, decode
from hashlib import sha256
from binascii               import hexlify, unhexlify


def check_createMeter(T):
    ccheck(len(T["inputs"]) == 1, "Expect inputs: SMToken")
    ccheck(len(T["referenceInputs"]) == 0, "Expect no references")
    ccheck(len(T["parameters"]) == 3, "Expect parameters: Public Key, Info, Sig")
    ccheck(len(T["returns"]) == 0, "Expect no returns")
    ccheck(len(T["outputs"]) == 2, "Expect exactly 2 output: SMToken, Meter")

    # Check the token
    TokenIn = loads(T[u"inputs"][0])
    ccheck(TokenIn["type"] == "SMToken", "Expected SMToken")

    # Do the crypto checks for authority:
    G = EcGroup()
    Pub = decode(unhexlify(T["parameters"][0]))
    Info = T["parameters"][1]
    digest = sha256("D" + str(len(T["parameters"][0])) + "|" + T["parameters"][0] + "|" + str(len(Info)) + "|" + Info).digest()
    Sig = decode(unhexlify(T["parameters"][2]))
    is_ok = do_ecdsa_verify(G, Pub, Sig, digest)
    ccheck(is_ok, "Check the signature to register the right meter.")
    

    # check integrity of the new account:
    Token = loads(T[u"outputs"][0])
    ccheck(Token["type"] == "SMToken", "Expected SMToken")

    Meter = loads(T[u"outputs"][1])
    ccheck(Meter["type"] == "SMMeter", "Expected SMMeter")
    ccheck(Meter["pub"] == T["parameters"][0], "Expected public key")
    ccheck(Meter["info"] == T["parameters"][1], "Expected Meter Information")
    ccheck(Meter["readings"] == hexlify(encode([])), "Expected Meter Information")


##
## Compute a bill from a meter.
##

def check_addReading(T):
    ccheck( len(T["inputs"]) == 1,           "Expect inputs: SMMeter")
    ccheck( len(T["referenceInputs"]) == 0,  "Expect no references")
    ccheck( len(T["parameters"]) == 2,       "Expect parameters: Readings, Sig")
    ccheck( len(T["returns"]) == 0,          "Expect no returns")
    ccheck( len(T["outputs"]) == 1,          "Expect exactly 1 output: SMMeter")

    MeterIn = loads(T[u"inputs"][0])
    MeterOut = loads(T[u"outputs"][0])
    ccheck( MeterIn["type"] == "SMMeter",       "Expect type SMMeter")
    ccheck( MeterOut["type"] == "SMMeter",      "Expect type SMMeter")
    ccheck( MeterIn["pub"] == MeterOut["pub"],  "Expect equal public keys")
    ccheck( MeterIn["info"] == MeterOut["info"],"Expect equal infos")

    G = EcGroup()
    Pub = decode(unhexlify(MeterIn["pub"]))
    digest = sha256("D" + str(len(T[u"inputs"][0])) + "|" + T[u"inputs"][0] + "|" + str(len(T["parameters"][0])) + "|" + T["parameters"][0]).digest()
    Sig = decode(unhexlify(T["parameters"][1]))

    is_ok = do_ecdsa_verify(G, Pub, Sig, digest)
    ccheck(is_ok, "Check the signature to record data from the right meter.")

    Commitements = decode(unhexlify(T["parameters"][0]))
    m1r = decode(unhexlify(MeterIn["readings"]))
    m2r = decode(unhexlify(MeterOut["readings"]))

    ccheck(m2r == m1r + [ Commitements ], "Expected Meter Information")


##
## Compute bill
##

def check_computeBill(T):
    ccheck( len(T["inputs"]) == 1,           "Expect inputs: SMMeter")
    ccheck( len(T["referenceInputs"]) == 0,  "Expect no references")
    ccheck( len(T["parameters"]) == 4,       "Expect parameters: period_index, tariffs, total, proof")
    ccheck( len(T["returns"]) == 0,          "Expect no returns")
    ccheck( len(T["outputs"]) == 2,          "Expect exactly 2 output: SMMeter, SMBill")

    MeterIn = loads(T[u"inputs"][0])
    MeterOut = loads(T[u"outputs"][0])
    ccheck( MeterIn["type"] == "SMMeter",       "Expect type SMMeter")
    ccheck( MeterOut["type"] == "SMMeter",      "Expect type SMMeter")
    ccheck( MeterIn["pub"] == MeterOut["pub"],  "Expect equal public keys")
    ccheck( MeterIn["info"] == MeterOut["info"],"Expect equal infos")
    ccheck( MeterIn["readings"] == MeterOut["readings"],"Expect equal readings")

    readings_commitments = decode(unhexlify(MeterIn["readings"]))

    # Get the necessary readings for the sought period
    G = EcGroup()
    period, Commitements = readings_commitments[int(T["parameters"][0])]
    tariffs = decode(unhexlify(T["parameters"][1]))
    big_commitment = sum([t*C for t, C in zip(tariffs, Commitements)], G.infinite())
    g = G.hash_to_point("g")
    h = G.hash_to_point("h")

    Blind = big_commitment - int(T["parameters"][2]) * g
    proof = decode(unhexlify(T["parameters"][3]))
    ccheck( Blind == proof,                             "Check correct bill")

    Bill = loads(T[u"outputs"][1])
    ccheck( Bill["type"] == "SMBill",                       "Expect type SMBill")
    ccheck( Bill["info"] == MeterIn["info"],                "Expect same info")
    ccheck( Bill["period"] == period,                       "Expect same period")
    ccheck( Bill["bill"] == int(T["parameters"][2]),        "Expect same total")


def checker_function(T):

    ##
    ## create a new bank account
    ##

    funcs = {
        101: check_init, 
        102: check_createMeter,
        103: check_addReading,
        104: check_computeBill,
    }

    if T["contractID"] in funcs:
        funcs[T["contractID"]](T)

    elif T["contractID"] == 1:
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

        # check inntegrity of the operation
        ccheck(from_account["amount"] - amount == from_account_new["amount"], "Incorrect new balance")
        ccheck(to_account["amount"]   + amount == to_account_new["amount"],   "Incorrect new balance")


    ##
    ## wrong method
    ##
    else:
        raise Exception("Wrong method: %s" % T["contractID"])

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
import traceback

@app.route("/bank/transfer", methods=["GET", "POST"])
def check():
    if request.method == "POST":
        try:
            return dumps(checker_function(loads(request.data)))
        except KeyError as e:
            traceback.print_exc()
            return dumps({"status": "ERROR", "message": e.args})
        except Exception as e:
            traceback.print_exc()
            return dumps({"status": "ERROR", "message": e.args})
    else:
        return dumps({"status": "ERROR", "message":"Use POST method."})


##################################################################################
# execute
##################################################################################
if __name__ == "__main__": 
    app.run(host="127.0.0.1", port="5001") 


##################################################################################