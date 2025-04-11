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

    def get_vkey(self) -> str:
        """
        Returns the vkey string based on the AccountKeyType instance.
        The vkey is a string key used to identify ValidatorId which here is either
        the ecdsa pub key or ss58 address
        """
        match self:
            case AccountKeyType.AccountId20:
                return "validator-accountid20-public-key"
            case AccountKeyType.AccountId32:
                return "validator-accountid32-ss58"
            case _:
                raise ValueError(f"Unsupported AccountKeyType: {self}")
