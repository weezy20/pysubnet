from enum import Enum


class AccountKeyType(Enum):
    AccountId32 = "AccountId32"  # Uses subkey to generate AccountID keys
    AccountId20 = "AccountId20"  # Uses moonkey to generate AccountID keys
