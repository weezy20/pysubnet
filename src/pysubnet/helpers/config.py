from pathlib import Path
from pprint import pprint
from typing import List, Optional
from pydantic import BaseModel, Field
import json
import tomli
import sys


class NetworkConfig(BaseModel):
    """
    Chainspec customizations loaded from a config file
    """

    name: str
    chain: str
    chain_id: str = Field(..., alias="chain-id")
    token_symbol: str = Field(..., alias="token-symbol")
    token_decimal: int = Field(..., alias="token-decimal")


class NodeConfig(BaseModel):
    """
    Information for a validator node
    """

    name: str
    p2p_port: int = Field(..., alias="p2p-port")
    rpc_port: int = Field(..., alias="rpc-port")
    prometheus_port: int = Field(..., alias="prometheus-port")
    # Final balance is this multiplied by 10^token_decimal
    balance: Optional[int] = 0


class PySubnetConfig(BaseModel):
    network: NetworkConfig
    nodes: List[NodeConfig]


def load_config(config_file_path: Path) -> PySubnetConfig:
    """Load and parse a config file, returning a PySubnetConfig object."""

    def _parse_config_file(config_file_path: Path):
        """Parse JSON or TOML config file."""
        try:
            config_file = config_file_path.read_text(encoding="utf-8")
            if config_file_path.suffix == ".json":
                return json.loads(config_file)
            if config_file_path.suffix == ".toml":
                return tomli.loads(config_file)
            raise ValueError(f"Unsupported config format: {config_file_path.suffix}")
        except (json.JSONDecodeError, tomli.TOMLDecodeError) as e:
            raise ValueError(f"Invalid config file syntax: {e}")

    raw_data = _parse_config_file(config_file_path)
    return PySubnetConfig.model_validate(raw_data)


def load_nodes_from_config(pysubnet_config: PySubnetConfig) -> List[NodeConfig]:
    """
    Load nodes from a PySubnetConfig object. Makes sure len(nodes) > 0
    Args:
        pysubnet_config (PySubnetConfig): The PySubnetConfig object to load nodes from.
    Returns:
        List[NodeConfig]: A list of NodeConfig objects.
    Raises:
        ValueError: If no nodes are found in the config.
    """
    if not pysubnet_config.nodes:
        raise ValueError("Cannot start network with zero nodes")
    return pysubnet_config.nodes


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise ValueError("Please provide config file path as first argument")

    config_file_path = Path(sys.argv[1])
    if not config_file_path.exists():
        raise FileNotFoundError(f"File not found: {config_file_path}")

    try:
        config = load_config(config_file_path)
        print("Nodes:")
        pprint([node.model_dump() for node in config.nodes])
        print("Network:")
        pprint(config.network.model_dump())
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
