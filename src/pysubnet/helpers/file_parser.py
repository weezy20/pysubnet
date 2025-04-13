from pathlib import Path
from pprint import pprint
from typing import List, Optional
from pydantic import BaseModel, Field, conint
import json
import tomli
import sys


class NetworkConfig(BaseModel):
    name: str
    chain: str
    chain_id: conint(ge=0, le=2**32 - 1) = Field(..., alias='chain-id')
    token_symbol: str = Field(..., alias="token-symbol")
    token_decimal: int = Field(..., alias="token-decimal")


class NodeConfig(BaseModel):
    name: str
    p2p_port: int = Field(..., alias="p2p-port")
    rpc_port: int = Field(..., alias="rpc-port")
    prometheus_port: int = Field(..., alias="prometheus-port")
    balance: Optional[int] = 0


class PySubnetConfig(BaseModel):
    network: NetworkConfig
    nodes: List[NodeConfig]

def _parse_config_file(config_file_path: Path):
    """Parse JSON or TOML config file"""
    try:
        config_file = config_file_path.read_text(encoding="utf-8")
        if config_file_path.suffix == ".json":
            return json.loads(config_file)
        if config_file_path.suffix == ".toml":
            return tomli.loads(config_file)
        raise ValueError(f"Unsupported config format: {config_file_path.suffix}")
    except (json.JSONDecodeError, tomli.TOMLDecodeError) as e:
        raise ValueError(f"Invalid config file syntax: {e}")

def load_config(path: str) -> PySubnetConfig:
    with open(path, "r") as f:
        raw_data = json.load(f)
    return PySubnetConfig.model_validate(raw_data)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise ValueError("Please provide config file path as first argument")

    config_file_path = Path(sys.argv[1])
    if not config_file_path.exists():
        raise FileNotFoundError(f"File not found: {config_file_path}")

    try:
        nodes = load_nodes_from_file(config_file_path)
        pprint([node.model_dump() for node in nodes]) 
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
