#!/bin/python3

import base64
import sys
import json

from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
import eth_abi

mrenclave_offset = 112
mrsigner_offset = 176
payload_offset = 368
quote_body_length = 432

def build_quote_body(mre, mrs, payload) -> bytes:
    assert len(mre) == 32
    assert len(mrs) == 32
    assert len(payload) <= 64
    body_bytes = bytes(mrenclave_offset) + mre
    body_bytes += bytes(mrsigner_offset - len(body_bytes)) + mrs
    body_bytes += bytes(payload_offset - len(body_bytes)) + payload
    body_bytes += bytes(64 - len(payload)) # pad extra bytes with 0s
    assert len(body_bytes) == quote_body_length 
    return body_bytes

def mock_evidence(mrenclave, mrsigner, payload):
    quote_body = build_quote_body(mrenclave, mrsigner, payload)
    assert mrenclave == bytes(quote_body[mrenclave_offset:mrenclave_offset+32])
    assert mrsigner == bytes(quote_body[mrsigner_offset:mrsigner_offset+32])
    assert payload == bytes(quote_body[payload_offset:payload_offset+len(payload)])

    quote_body = base64.b64encode(quote_body).decode('utf-8')

    evidence = {
        "id":"142090828149453720542199954221331392599",
        "timestamp":"2023-02-15T01:24:57.989456",
        "version":4,
        "epidPseudonym":"EbrM6X6YCH3brjPXT23gVh/I2EG5sVfHYh+S54fb0rrAqVRTiRTOSfLsWSVTZc8wrazGG7oooGoMU7Gj5TEhsvsDIV4aYpvkSk/E3Tsb7CaGd+Iy1cEhLO4GPwdmwt/PXNQQ3htLdy3aNb7iQMrNbiFcdkVdV/tepdezMsSB8Go=",
        "advisoryURL":"https://security-center.intel.com",
        "advisoryIDs":["INTEL-SA-00334","INTEL-SA-00615"],
        "isvEnclaveQuoteStatus":"OK",
        "isvEnclaveQuoteBody": f"{quote_body}"
    }
    return evidence 

def prepare_values(e: dict) -> bytes:
        vs = []
        for v in e.values():
            if type(v) != str:
                # handle lists and integers
                vs.append(json.dumps(v).replace(" ", "").encode('utf-8'))
            else:
                vs.append(v.encode('utf-8'))
        values_payload = eth_abi.encode(['bytes'] * len(vs), vs)
        return values_payload


def sign(fname, message) -> bytes:
    # Load the private key from a file
    with open(fname, 'rb') as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())

    signature = private_key.sign(message, padding.PKCS1v15(), hashes.SHA256())
    return signature


def main():
    # Pad inputs
    stripped_mre = sys.argv[1].lstrip('0x')
    stripped_mrs = sys.argv[2].lstrip('0x')
    stripped_payload = sys.argv[3].lstrip('0x')

    mrenclave = '0' * (64 - len(stripped_mre)) + stripped_mre
    mrsigner = '0' * (64 - len(stripped_mrs)) + stripped_mrs
    payload = '0' * (128 - len(stripped_payload)) + stripped_payload
    mrenclave = bytes.fromhex(mrenclave)
    mrsigner = bytes.fromhex(mrsigner)
    payload = bytes.fromhex(payload)

    # mock json report
    evidence = mock_evidence(mrenclave, mrsigner, payload)

    # json -> bytes to sign (ignoring whitespace)
    evidence_bytes = json.dumps(evidence).replace(" ", "").encode('utf-8')

    # sign json bytes
    fname = sys.argv[4]
    signature = sign(fname, evidence_bytes)

    # convert JSON values to abi-encoded bytes to send to contract 
    values_payload = prepare_values(evidence)

    # abi encode bytes
    ffi_payload = eth_abi.encode(['bytes', 'bytes'], [signature, values_payload])
    
    # print for ffi interface
    print(ffi_payload.hex())

if __name__ == "__main__":
    main()