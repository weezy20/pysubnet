import json
import os
from pathlib import Path
from enum import Enum
from typing import Union, Optional
from pydantic import BaseModel, field_validator

from pysubnet.helpers.process import run_command
from pysubnet.helpers.substrate import Substrate


class ChainspecType(str, Enum):
    LOCAL = "local"
    DEV = "dev"


class Chainspec(BaseModel):
    value: Union[Path, ChainspecType] = ChainspecType.LOCAL

    @field_validator("value", mode="before")
    def parse_value(
        cls, v: Optional[Union[str, Path, ChainspecType]]
    ) -> Union[Path, ChainspecType]:
        if v is None:
            return ChainspecType.LOCAL
        if isinstance(v, ChainspecType):
            return v
        if isinstance(v, Path):
            return cls._validate_path(v)
        if isinstance(v, str):
            if v.lower() in ("local", "dev"):
                return ChainspecType(v.lower())
            return cls._validate_path(Path(v))
        raise ValueError(f"Invalid chainspec value: {v}")

    @classmethod
    def _validate_path(cls, path: Path) -> Path:
        """Validate the path points to a valid chainspec file."""
        if not path.is_file():
            raise ValueError(f"'{path}' is not a valid file path")

        try:
            with path.open("r") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in chainspec file '{path}': {e}")
        except OSError as e:
            raise ValueError(f"Error reading chainspec file '{path}': {e}")

        # Validate chainspec structure
        missing = [key for key in ["name", "id"] if key not in data]
        if missing:
            raise ValueError(f"Chainspec missing required fields: {missing}")

        if "genesis" not in data or "runtimeGenesis" not in data["genesis"]:
            raise ValueError("Chainspec missing genesis.runtimeGenesis configuration")

        return os.path.abspath(path)

    def __str__(self) -> str:
        if isinstance(self.value, Path):
            return str(self.value)
        return self.value.value

    @classmethod
    def local(cls) -> "Chainspec":
        return cls(value=ChainspecType.LOCAL)

    @classmethod
    def dev(cls) -> "Chainspec":
        return cls(value=ChainspecType.DEV)

    @classmethod
    def from_path(cls, path: Union[str, Path]) -> "Chainspec":
        return cls(value=Path(os.path.abspath(path)))

    def get_chainid(self) -> str:
        """Get the chain ID from the chainspec. Uses hardcoded values as present in default substrate node.
        Use `get_chainid_with(bin)` to get the chain ID from a generated chainspec file."""

        if isinstance(self.value, ChainspecType):
            match self.value:
                case ChainspecType.LOCAL:
                    return (
                        "local_testnet"  # As appears on most chains local_config() fn
                    )
                case ChainspecType.DEV:
                    return "dev"  # As appears on most chains development_config() fn

        elif isinstance(self.value, Path):
            try:
                with self.value.open("r") as f:
                    data = json.load(f)
                return data.get("id", "unknown")
            except (json.JSONDecodeError, OSError) as e:
                # Pydantic will prevent this from happening, but just in case
                raise ValueError(f"Error reading chainspec file '{self.value}': {e}")

        raise ValueError("Invalid chainspec value")

    def get_chainid_with(self, substrate: Substrate) -> str:
        """Get the chain ID directly from a generated chainspec file."""
        c = substrate.run_command(
            [
                "build-spec",
                "--chain",
                str(self),
                "--disable-default-bootnode",
            ],
            json=True,
        )

        chain_id = c.get("id")
        if not chain_id:
            raise ValueError(
                f"Chain ID not found in generated chainspec with binary: {substrate.source} using chainspec: {self}"
            )
        return chain_id

    def load_json(self) -> str | None:
        """Load the chainspec file into memory only if it's a path. Returns None otherwise."""
        if isinstance(self.value, Path):
            try:
                with self.value.open("r") as f:
                    data = json.load(f)
                return data
            except (json.JSONDecodeError, OSError) as e:
                # Pydantic will prevent this from happening, but just in case
                raise ValueError(f"Error reading chainspec file '{self.value}': {e}")
        return None


if __name__ == "__main__":
    # Default is local
    spec = Chainspec()
    print(spec)  # "local"

    # From enum value
    spec = Chainspec(value=ChainspecType.DEV)
    print(spec)  # "dev"

    # From string
    spec = Chainspec(value="dev")
    print(spec)  # "dev"

    # From path string
    # Try to provide a file path to a invalid chainspec file to checkout the field_validator in action
    spec = Chainspec(value="network/chainspec.json")
    print(spec)  # "/path/to/chainspec.json"

    # From Path object
    spec = Chainspec(value=Path("network/chainspec.json"))
    print(spec)  # "/path/to/chainspec.json"

    # Convenience constructors
    spec = Chainspec.local()  # same as Chainspec()
    spec = Chainspec.dev()
    spec = Chainspec.from_path("network/chainspec.json")
