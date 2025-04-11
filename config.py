import argparse
import os
from dataclasses import dataclass

from accounts import AccountKeyType


@dataclass
class Config:
    interactive: bool = False
    run_network: bool = False
    root_dir: str = "./network"
    clean: bool = False
    chainspec: str = "dev"
    bin: str = "substrate"
    account_key_type: AccountKeyType = AccountKeyType.AccountId20


def parse_args() -> Config:
    parser = argparse.ArgumentParser(description="PySubnet launcher")
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        default=False,
        help="Run in interactive mode",
    )
    parser.add_argument(
        "--run",
        "--start",
        "-r",
        dest="run_network",
        action="store_true",
        default=False,
        help="Run the network after generating keys and chainspecs",
    )
    parser.add_argument(
        "--root", type=str, default="./network", help="Root directory for network"
    )
    parser.add_argument(
        "-c",
        "--clean",
        action="store_true",
        default=False,
        help="Clean the root directory before starting",
    )
    parser.add_argument(
        "--chainspec",
        type=str,
        default="dev",
        help="Path to chainspec file or 'dev' | 'local'",
    )
    parser.add_argument(
        "--bin", type=str, default="substrate", help="Path to substrate binary"
    )
    parser.add_argument(
        "--account",
        type=AccountKeyType.from_string,
        choices=list(AccountKeyType),
        default=AccountKeyType.AccountId20,
        help="Type of account key ('ecdsa' for Ethereum-style, 'sr25519' for Substrate-style)",
    )

    args = parser.parse_args()
    # !! WARNING: argsparse will actually set non-supplied flags to None! This works for boolean values but
    # for others it its a very annoying runtime error! Hence use + <default value> unless a default is provided
    # in argsparse itself. We explicitly specify defaults for argparse itself so `or <default_val>` not required here
    return Config(
        interactive=args.interactive,
        run_network=args.run_network,
        root_dir=os.path.abspath(args.root),
        clean=args.clean,
        chainspec=args.chainspec,
        bin=os.path.abspath(args.bin),
        account_key_type=args.account
    )
