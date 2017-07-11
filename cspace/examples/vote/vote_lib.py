## An implementation of an additivelly homomorphic 
## ECC El-Gamal scheme, used in Privex.

from petlib.bn import Bn
from petlib.ec import EcGroup
from hashlib import sha256
from binascii import hexlify, unhexlify
import pytest

def setup(nid=713):
    """ Generates the Cryptosystem Parameters. """
    G = EcGroup()
    g = G.hash_to_point(b"g")
    hs = [G.hash_to_point(("h%s" % i).encode("utf8")) for i in range(4)]
    o = G.order()
    return (G, g, hs, o)


def key_gen(params):
   """ Generate a private / public key pair. """
   (G, g, hs, o) = params
   priv = o.random()
   pub = priv * g
   return (priv, pub)


def to_challenge(elements):
    """ Generates a Bn challenge by hashing a number of EC points """
    Cstring = b",".join([hexlify(x.export()) for x in elements])
    Chash =  sha256(Cstring).digest()
    return Bn.from_binary(Chash)


def binencrypt(params, pub, m):
    """ Encrypt a binary value m under public key pub """
    assert m in [0, 1]
    (G, g, (h0, h1, h2, h3), o) = params
    
    k = o.random()
    a = k * g
    b = k * pub + m * h0
    return (a, b, k)


def enc_side(params, pub, counter):
    """Encrypts the values of a small counter"""
    assert -2**8 < counter < 2**8
    (G, g, (h0, h1, h2, h3), o) = params

    k = o.random()
    a = k * g
    b = k * pub + counter * h0
    return (a, b, k)


def add(c1, c2):
    """Add two encrypted counters"""
    a1, b1 = c1
    a2, b2 = c2
    return (a1 + a2, b1 + b2)

def sub(c1, c2):
    """Add two encrypted counters"""
    a1, b1 = c1
    a2, b2 = c2
    return (a1 - a2, b1 - b2)

def mul(c1, val):
    """Multiplies an encrypted counter by a public value"""
    a1, b1 = c1
    return (val*a1, val*b1)

def randomize(params, pub, c1):
    """Rerandomize an encrypted counter"""
    zero = enc_side(params, pub, 0)
    return add(c1, zero)

def make_table(params):
    """Make a decryption table"""
    (G, g, hs, o) = params
    table = {}
    for i in range(-1000, 1000):
        table[i * g] = i
    return table

def dec(params, table, priv, c1):
    """Decrypt an encrypted counter"""
    (G, g, hs, o) = params
    a, b = c1
    plain = b + (-priv * a)
    return table[plain] 


##
##
##
def provebin(params, pub, Ciphertext, k, m):
    # Unpack the arguments
    (G, g, (h0, h1, h2, h3), o) = params
    (a, b) = Ciphertext

    # Create the witnesses
    wk = o.random()
    wm = o.random()

    # Calculate the witnesses commitments
    Aw = wk * g
    Bw = wk * pub + wm * h0
    Dw = wk * g + (m*(1-m)) * h1

    # Create the challenge
    c = to_challenge([g, h0, h1, a, b, Aw, Bw, Dw])

    # Create responses for k and m
    rk = (wk - c * k) % o
    rm = (wm - c * m) % o

    # Return the proof
    return (c, (rk, rm))

##
##
##
def verifybin(params, pub, Ciphertext, proof):
    # Unpack the arguments
    (G, g, (h0, h1, h2, h3), o) = params
    a, b = Ciphertext
    (c, (rk, rm)) = proof

    # Calculate the commitment primes
    Ck_prime = c * a + rk * g
    Cm_prime = c * b + rk * pub + rm * h0
    Cd_prime = c * a  + rk * g + 0 * h1

    # Calculate the challenge prime
    c_prime = to_challenge([g, h0, h1, a, b, Ck_prime, Cm_prime, Cd_prime])

    # Return True or False
    return c_prime == c


##
##
##
def proveone(params, pub, Ciphertext, k):
    # Unpack the arguments
    (G, g, (h0, h1, h2, h3), o) = params
    (a, b) = Ciphertext

    # Create the witnesses
    wk = o.random()
    wm = o.random()

    # Calculate the witnesses commitments
    Aw = wk * g
    Bw = wk * pub + wm * h0
    Dw = wk * g + 1 * h1

    # Create the challenge
    c = to_challenge([g, h0, h1, a, b, Aw, Bw, Dw])

    # Create responses for k and m
    rk = (wk - c * k) % o
    rm = (wm - c * 1) % o

    # Return the proof
    return (c, (rk, rm))

##
##
##
def verifyone(params, pub, Ciphertext, proof):
   # Unpack the arguments
    (G, g, (h0, h1, h2, h3), o) = params
    a, b = Ciphertext
    (c, (rk, rm)) = proof

    # Calculate the commitment primes
    Ck_prime = c * a + rk * g
    Cm_prime = c * b + rk * pub + rm * h0
    Cd_prime = c * a + rk * g + 1 * h1

    # Calculate the challenge prime
    c_prime = to_challenge([g, h0, h1, a, b, Ck_prime, Cm_prime, Cd_prime])

    # Return True or False
    return c_prime == c


##
##
##
def provezero(params, pub, Ciphertext, k):
    # Unpack the arguments
    (G, g, (h0, h1, h2, h3), o) = params
    (a, b) = Ciphertext

    # Create the witnesses
    wk = o.random()

    # Calculate the witnesses commitments
    Aw = wk * g
    Bw = wk * pub + 0 * h0

    # Create the challenge
    c = to_challenge([g, h0, h1, a, b, Aw, Bw])

    # Create responses for k and m
    rk = (wk - c * k) % o

    # Return the proof
    return (c, rk)

##
##
##
def verifyzero(params, pub, Ciphertext, proof):
    # Unpack the arguments
    (G, g, (h0, h1, h2, h3), o) = params
    a, b = Ciphertext
    (c, rk) = proof

    # Calculate the commitment primes
    Ck_prime = c * a + rk * g
    Cm_prime = c * b + rk * pub

    # Calculate the challenge prime
    c_prime = to_challenge([g, h0, h1, a, b, Ck_prime, Cm_prime])

    # Return True or False
    return c_prime == c


