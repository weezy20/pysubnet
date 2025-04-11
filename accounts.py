import argparse
from enum import Enum


class AccountKeyType(Enum):
    AccountId32 = (
        "sr25519"  # Uses substrate node's built in subkey to generate AccountID keys
    )
    AccountId20 = "ecdsa"  # Uses ethereum keys

    # Make the enum case-insensitive for command line input
    @classmethod
    def from_string(cls, s):
        try:
            return cls(s.lower())
        except ValueError:
            raise argparse.ArgumentTypeError(
                f"Invalid account type. Choose from: {', '.join([e.value for e in cls])}"
            )
