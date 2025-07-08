from pathlib import Path
from pprint import pprint
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, ValidationInfo
import json
import pydantic
import tomli
import sys
import re


# class ChainTypeEnum(Enum):
#     DEVELOPMENT = "Development"
#     LOCAL = "Local"
#     LIVE = "Live"


class ChainConfig(BaseModel):
    """
    Configuration for chain
    """

    chain_name: str = Field(..., alias="name")
    chain_id: str = Field(..., alias="chain-id")
    chain_type: str = Field(..., alias="chain-type")


class BalanceConfig(BaseModel):
    """
    Balance configuration for injecting custom balances into the chainspec.
    Supports both hex (ECDSA) and SS58 (SR25519) address formats.
    """
    
    hex: Optional[Dict[str, int]] = Field(default_factory=dict)
    """Hex addresses (ECDSA) with their balance amounts in token units."""
    
    ss58: Optional[Dict[str, int]] = Field(default_factory=dict)
    """SS58 addresses (SR25519) with their balance amounts in token units."""

    def normalize_hex_addresses(self) -> Dict[str, int]:
        """
        Normalize hex addresses by ensuring they all start with '0x'.
        Returns a dict with normalized addresses.
        """
        normalized = {}
        if not self.hex:
            return normalized
            
        for address, balance in self.hex.items():
            # Remove any existing 0x prefix and add it back
            clean_address = address.lower().replace('0x', '')
            normalized_address = f'0x{clean_address}'
            normalized[normalized_address] = balance
            
        return normalized

    def validate_hex_address(self, address: str) -> bool:
        """
        Validate that a hex address is a valid ECDSA address format.
        Should be 40 hex characters (20 bytes) optionally prefixed with 0x.
        """
        clean_address = address.lower().replace('0x', '')
        return bool(re.match(r'^[0-9a-f]{40}$', clean_address))

    def validate_ss58_address(self, address: str) -> bool:
        """
        Basic validation for SS58 address format.
        SS58 addresses start with specific characters and have a checksum.
        """
        # Basic check - SS58 addresses are typically 47-48 characters long
        # and contain alphanumeric characters (base58)
        return bool(re.match(r'^[1-9A-HJ-NP-Za-km-z]{47,48}$', address))


class NetworkConfig(BaseModel):
    """
    Chainspec customizations loaded from a config file
    """

    chain: ChainConfig = Field(..., alias="chain")
    token_symbol: Optional[str] = Field(None, alias="token-symbol", min_length=1, max_length=12)
    token_decimal: Optional[int] = Field(None, alias="token-decimal")
    remove_existing_balances: bool = Field(False, alias="remove-existing-balances")
    balances: Optional[BalanceConfig] = Field(default_factory=BalanceConfig, alias="balances")


class NodeConfig(BaseModel):
    """
    Information for a validator node
    """

    name: str
    """The name of the node."""

    rpc_port: int = Field(..., alias="rpc-port", ge=1024, le=49151)
    """The RPC port for the node, used for client communication. Must be between 1024 and 49151."""

    prometheus_port: int = Field(..., alias="prometheus-port", ge=1024, le=49151)
    """The Prometheus port for the node, used for metrics monitoring. Must be between 1024 and 49151."""

    p2p_port: int = Field(..., alias="p2p-port", ge=1024, le=49151)
    """The P2P port for the node, used for peer-to-peer communication. Must be between 1024 and 49151."""
    # Final balance is this multiplied by 10^token_decimal
    balance: Optional[int] = 0


class PySubnetConfig(BaseModel):
    network: NetworkConfig
    nodes: List[NodeConfig]

    @pydantic.model_validator(mode="after")
    def validate_unique_node_attributes(cls, values, info: ValidationInfo):
        nodes = values.nodes if values.nodes else []
        skip_same_port_validation = info.context and info.context.get(
            "skip_port_validation", True
        )
        if nodes:
            seen_names = set()
            seen_rpc_ports = set()
            seen_p2p_ports = set()
            seen_prometheus_ports = set()

            for node in nodes:
                if node.name in seen_names:
                    raise ValueError(f"Duplicate node name found: {node.name}")
                if skip_same_port_validation:
                    continue
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


def load_config(config_file_path: Path, ctx: Optional[Dict]) -> PySubnetConfig:
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
    return PySubnetConfig.model_validate(raw_data, context=ctx)


def load_nodes_from_config(pysubnet_config: PySubnetConfig) -> List[Dict]:
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
    return [node.model_dump(by_alias=True) for node in pysubnet_config.nodes]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise ValueError("Please provide config file path as first argument")

    config_file_path = Path(sys.argv[1])
    if not config_file_path.exists():
        raise FileNotFoundError(f"File not found: {config_file_path}")

    try:
        config = load_config(config_file_path, ctx=None)
        print("Nodes:")
        pprint([node.model_dump() for node in config.nodes])
        print("Network:")
        pprint(config.network.model_dump())

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
