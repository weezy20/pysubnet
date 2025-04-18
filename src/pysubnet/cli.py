import argparse
import os
from dataclasses import dataclass, field
from pathlib import Path
from pprint import pprint
from typing import List, Dict
from rich.console import Console

from pysubnet.helpers.config import NetworkConfig, load_config, load_nodes_from_config

from .accounts import AccountKeyType
from .chainspec import ChainSpec, ChainSpecType


@dataclass
class CliConfig:
    network: NetworkConfig = None
    apply_chainspec_customizations: bool = False
    interactive: bool = False
    run_network: bool = False
    root_dir: str = "./network"
    clean: bool = False
    chainspec: ChainSpec = ChainSpec.local()
    raw_chainspec: Path = None  # Is generated by us so is a fs path
    bin: Path = None
    account_key_type: AccountKeyType = None
    poa: bool = False
    nodes: List[Dict] = field(
        default_factory=lambda: [
            {
                "name": "alice",
                "p2p-port": 30333,
                "rpc-port": 9944,
                "prometheus-port": 9615,
            },
            {
                "name": "bob",
                "p2p-port": 30334,
                "rpc-port": 9945,
                "prometheus-port": 9616,
            },
            {
                "name": "charlie",
                "p2p-port": 30335,
                "rpc-port": 9946,
                "prometheus-port": 9617,
            },
            {
                "name": "david",
                "p2p-port": 30336,
                "rpc-port": 9947,
                "prometheus-port": 9618,
            },
        ]
    )


def parse_args() -> CliConfig:
    parser = argparse.ArgumentParser(description="PySubnet launcher")
    parser.add_argument(
        "--config",
        "-f",
        dest="config_file",
        type=Path,
        help="Path to the configuration file",
    )
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
        help="Path to chainspec file or 'dev' | 'local'",
    )
    parser.add_argument("--bin", type=Path, help="Path to substrate binary")
    parser.add_argument(
        "--account",
        type=AccountKeyType.from_string,
        choices=list(AccountKeyType),
        help="Type of account key ('ecdsa' for Ethereum-style, 'sr25519' for Substrate-style)",
    )
    parser.add_argument(
        "--poa",
        action="store_true",
        default=False,
        help="Enable Substrate-node-template PoA mode, i.e. assign all authorities equal weight in chainspec",
    )
    # !! WARNING: argsparse will actually set non-supplied flags to None! This works for boolean values but
    # for others it can lead to uncaught bugs! Hence use + <default value> unless a default is provided
    # in argsparse itself. We explicitly specify defaults for argparse itself so `or <default_val>` not required here
    args = parser.parse_args()

    config = CliConfig(
        interactive=args.interactive,
        run_network=args.run_network,
        root_dir=os.path.abspath(args.root),
        clean=args.clean,
        chainspec=args.chainspec,
        bin=args.bin,
        account_key_type=args.account,
        poa=args.poa,
    )
    if args.config_file is not None:
        pysubnetConfig = load_config(args.config_file)
        config.nodes = load_nodes_from_config(pysubnetConfig)
        if pysubnetConfig.network is not None:
            config.network = pysubnetConfig.network
            config.apply_chainspec_customizations = True
            if pysubnetConfig.network.chain is not None:
                chain_id = pysubnetConfig.network.chain.chain_id
                config.chainspec = ChainSpec(value=chain_id)
    # --chainspec overrides the config file chainspec & disables customizations defined under [network]
    elif args.chainspec is not None:
        config.chainspec = ChainSpec(value=args.chainspec)
        config.apply_chainspec_customizations = False
    return config


if __name__ == "__main__":
    config = parse_args()
    pprint(config)
