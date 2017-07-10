###################################################
# Chainspace Mock
# cspace_service.py
#
# version: 0.0.2
###################################################
from json        import loads, dumps
from hashlib     import sha256
from binascii    import hexlify
from tinydb      import TinyDB, Query
import requests
import json


###################################################
# wrap
# compute the hash of x
###################################################
def H(x):
    return hexlify(sha256(x).digest())


###################################################
# Chainspace's class
###################################################
class ChainSpace:
    # ---------------------------------------------
    # init
    # At th moment, this function initialises all objects that will have be stored in a database.
    # ---------------------------------------------
    def __init__(self, dbName='db.json', configPath='config.json'):
        # init db
        db          = TinyDB(dbName)
        self.query  = Query()

        # repository of objects
        # contains objects of the form: {"id" : [ID], "object" : [Obj]}
        self.data   = db.table('data') 

        # state of Active objects
        # contains objects of the form: {"id" : [ID], "status" : [String]}
        self.active = db.table('active')    

        # a log of all transactions that were accepted
        # contains objects of the form: {"id" : [T_ID], "transaction" : [T_Obj]}
        self.log    = db.table('log')    

        # hash of transactions and output objects
        # contains ONE object of the form: {"head": [String]}
        self.head   = db.table('head')      

        # init hash of transactions and output objects
        self.head.insert({"head": "Ohm"})

        # load config
        with open(configPath) as json_data_file:
            self.config = json.load(json_data_file)



    # ---------------------------------------------
    # update_log
    # update the log with the input data.
    # ---------------------------------------------
    def update_log(self, data):
        # append data to the log
        self.log.insert(data)

        # update head
        s = dumps(data)
        oldHead = self.head.all()
        newHead = H(dumps(oldHead[0]["head"]) + "|" + s)
        self.head.purge()
        self.head.insert({"head": newHead})


    # ---------------------------------------------
    # call checker
    # call the transaction's checker
    # ---------------------------------------------
    def call_checker(self, packet):

        # call the checker
        checkerURL = r"http://127.0.0.1:5001/bank/transfer"
        #checkerURL = r"http://127.0.0.1:5001/value/add"

        #checkerURL = self.config["contracts"]
        """
        for item in self.config["contracts"]:
            if item["contractID"] == packet["contractID"]:
                checkerURL = item["url"]
        """


        r = requests.post(checkerURL, data = dumps(packet))
        # return result
        return loads(r.text)["status"] == "OK"


    # ---------------------------------------------
    # apply_transaction
    # execute a transaction
    # ---------------------------------------------
    def apply_transaction(self, requestData):

        # get transaction and store
        packet = loads(requestData)
        transaction, store = packet["transaction"], packet["store"]

        # loop over dependencies
        returns = []
        for dependency in transaction["dependencies"]: 
            returns += self.apply_transaction(dependency)

    	# assert that the transaction is well-formed
        self.check_format(transaction, store)

        # make transaction for checker
        packetForChecker = self.make_packet_for_checker(transaction, store)
        packetForChecker["parameters"] += returns

        # process top-level transaction
        return self.apply_transaction_helper(transaction, packetForChecker)



	# ---------------------------------------------
    # apply_transactio_helper
    # execute a transaction
    # ---------------------------------------------    	
    def apply_transaction_helper(self, transaction, packetForChecker):
        
        # call the checker to verify integrity of the computation
        if not self.call_checker(packetForChecker):
        	raise Exception("The checker declined the transaction.") 

        # create fresh transaction IDs
        Tx_ID       = H(dumps(transaction))
        #Output_IDs  = [H(Tx_ID+"|%s" % i) for i, _ in enumerate(transaction["outputs"])]
        Output_IDs = []
        for o in transaction["outputs"]:
            Output_IDs.append(H(Tx_ID +"|"+ o))

        # verify that the input objects are active
        for ID in transaction["inputIDs"]:
            o = self.active.get(self.query.id == ID)
            if o == None:
                raise Exception("Object: %s does not exist" % ID)
            elif o["status"] != None:
                raise Exception("Object: %s not active" % ID)

        # verify that the reference input objects are active
        for ID in transaction["referenceInputIDs"]:
            o = self.active.get(self.query.id == ID)
            if o == None: 
                raise Exception("Object: %s does not exist" % ID)
            elif o["status"] != None:
                raise Exception("Object: %s not active" % ID)

        # now make all objects inactif    
        for ID in transaction["inputIDs"]:
            self.active.update({"status": Tx_ID}, self.query.id == ID)
            
        # register new objects
        for ID, obj in zip(Output_IDs, transaction["outputs"]):
            self.data.insert({"id" : ID, "object" : obj})
            self.active.insert({"id" : ID, "status" : None})

        # setup as hashchain: update the log
        self.update_log({"id" : Tx_ID, "transaction" : transaction})

        # return the transaction and object's output ID
        return transaction["returns"]

        
        
    # ---------------------------------------------
    # check_format
    # check the transaction's format
    # ---------------------------------------------
    def check_format(self, transaction, store):
        try:
            # loop over all inputs' and reference inputs' ID
            for ID in transaction["inputIDs"] + transaction["referenceInputIDs"]:
                # get object from db
                objectDB = self.data.get(self.query.id == ID)
                if objectDB == None:
                    raise Exception("Malformed key-value store")

                # look for object in store
                objectStore = None
                for item in store:
                    if item["key"] == ID:
                        objectStore = item["value"]
                        if H(objectDB["object"]) != H(objectStore):
                            raise Exception("Object: %s in the store does not match the database" % ID)

                # if the object is not in the store
                if objectStore == None:
                    raise Exception("Object: %s is not in the store" % ID)
        except KeyError as e:
            raise Exception("Malformed key-value store")


    # ---------------------------------------------
    # make_packet_for_checker
    # format a packet to be sent to the checker
    # ---------------------------------------------
    def make_packet_for_checker(self, transaction, store):
    	# get inputs from the dabatase
        inputs = []
        referenceInputs = []
        try:
            for ID in transaction["inputIDs"]:
                for item in store:
                    if item["key"] == ID:
                        inputs.append(item["value"])
            for ID in transaction["referenceInputIDs"]:
                for item in store:
                	if item["key"] == ID:
                		inputs.append(item["value"])
        except KeyError as e:
            raise Exception("Malformed key-value store")
        
        # create packet for checker
        return {
            "contractID"        : transaction["contractID"],
            "inputs"       	    : inputs,
            "referenceInputs"   : referenceInputs,
            "parameters"        : transaction["parameters"],
            "returns"           : transaction["returns"],
            "outputs"           : transaction["outputs"],
            "dependencies"      : transaction["dependencies"]
        }




###################################################
# webapp
###################################################
from flask import Flask, request

# the state of the infrastructure
app     = Flask(__name__)
app.cs  = ChainSpace()


# -------------------------------------------------
# /
# test the server's connection
# -------------------------------------------------
@app.route("/", methods=['GET', 'POST'])
def index():
    return dumps({"status": "OK", "message": "Hello, world!"})

# -------------------------------------------------
# /dump
# serve the database content
# -------------------------------------------------
@app.route("/dump", methods=['GET', 'POST'])
def dump():
    return dumps({
        "db"     : app.cs.data.all(), 
        "active" : app.cs.active.all(), 
        "log"    : app.cs.log.all(), 
        "head"   : app.cs.head.all()
    })

# -------------------------------------------------
# /process
# process a transaction 
# -------------------------------------------------
@app.route("/process", methods=['GET', 'POST'])
def process():
    if request.method == "POST":
        try:
        	returns = app.cs.apply_transaction(request.data)
        	return dumps({"status" : "OK", "returns" : returns})
        except Exception as e:
            return dumps({
                "status"  : "Error", 
                "message" : e.args
            })
    else:
        return dumps({"status":"ERROR", "message":"Use POST method."})


###################################################
# execute
###################################################
if __name__ == "__main__":
    app.run(host="127.0.0.1", port="5000") 


###################################################