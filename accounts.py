from enum import Enum


class AccountKeyType(Enum):
    AccountId32 = "AccountId32"  # Uses substrate node's built in subkey to generate AccountID keys
    AccountId20 = "AccountId20"  # Uses ethereum keys
