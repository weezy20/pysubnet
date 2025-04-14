from pathlib import Path
from pprint import pprint
from typing import List, Optional
from pydantic import BaseModel, Field
import json
import pydantic
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
    rpc_port: int = Field(..., alias="rpc-port", ge=1, le=65535)
    prometheus_port: int = Field(..., alias="prometheus-port", ge=1, le=65535)
    p2p_port: int = Field(..., alias="p2p-port", ge=1, le=65535)
    # Final balance is this multiplied by 10^token_decimal
    balance: Optional[int] = 0


class PySubnetConfig(BaseModel):
    network: NetworkConfig
    nodes: List[NodeConfig]

    @pydantic.model_validator(mode="after")
    def validate_unique_node_attributes(cls, values):
        nodes = values.nodes if values.nodes else []
        if nodes:
            seen_names = set()
            seen_rpc_ports = set()
            seen_p2p_ports = set()
            seen_prometheus_ports = set()

            for node in nodes:
                if node.name in seen_names:
                    raise ValueError(f"Duplicate node name found: {node.name}")
                if node.rpc_port in seen_rpc_ports:
                    raise ValueError(f"Duplicate rpc-port found: {node.rpc_port}")
                if node.p2p_port in seen_p2p_ports:
                    raise ValueError(f"Duplicate p2p-port found: {node.p2p_port}")
                if node.prometheus_port in seen_prometheus_ports:
                    raise ValueError(
                        f"Duplicate prometheus-port found: {node.prometheus_port}"
                    )

                seen_names.add(node.name)
                seen_rpc_ports.add(node.rpc_port)
                seen_p2p_ports.add(node.p2p_port)
                seen_prometheus_ports.add(node.prometheus_port)

        return values


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
