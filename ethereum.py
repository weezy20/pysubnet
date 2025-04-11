from pprint import pprint
from eth_keys import keys
from eth_utils import to_checksum_address
import secrets


def generate_ethereum_keypair():
    """
    Generates an Ethereum key pair and address.

    This function creates a new Ethereum private key using a cryptographically
    secure random number generator. It then derives the corresponding public key
    and Ethereum address.

    Returns:
        dict: A dictionary containing the private key in hexadecimal format
              ('private_key_hex'), the public key in hexadecimal format
              ('public_key_hex'), and the Ethereum address ('ethereum_address').
    """

    private_key_bytes = secrets.token_bytes(32)
    private_key = keys.PrivateKey(private_key_bytes)

    # Derive the public key and Ethereum address
    public_key = private_key.public_key
    address = to_checksum_address(public_key.to_address())

    return {
        "private_key": private_key.to_hex(),
        "public_key": public_key.to_hex(),
        "ethereum_address": address,
    }


if __name__ == "__main__":
    print("Ethereum keypair generated:")
    pprint(generate_ethereum_keypair())
