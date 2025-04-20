import os
import re
from enum import Enum
from pathlib import Path

import docker
from pydantic import BaseModel, model_validator
from .process import is_valid_public_key, parse_subkey_output, run_command
import sys


class ExecType(str, Enum):
    BIN = "bin"
    DOCKER = "docker"


class SubstrateType(BaseModel):
    source: str
    type: ExecType

    @model_validator(mode="before")
    def validate(cls, values):
        source_ref = values.get("source")
        if source_ref is None:
            raise ValueError("Missing source")
        command = ["key", "generate", "--scheme", "sr25519"]
        # Check if it's a filesystem path
        path_obj = Path(source_ref).expanduser()
        if path_obj.exists():
            abs_path = str(path_obj.resolve())
            if not path_obj.is_file():
                raise ValueError(f"Expected file but {source_ref} is not a file")
            if not os.access(abs_path, os.X_OK):
                raise ValueError(f"{source_ref} is not executable")
            # Test to see if this is a valid substrate node
            proc = run_command([abs_path, *command])
            output = proc.stdout
            data = parse_subkey_output(output)
            values["source"] = abs_path
            values["type"] = ExecType.BIN

        # Otherwise treat as Docker image name:tag
        elif re.match(r"^[\w./-]+:[\w.-]+$", source_ref):
            client = docker.from_env()
            try:
                # Test to see if this is a valid substrate node image
                output = client.containers.run(
                    source_ref,
                    command=command,
                    remove=True,
                    stdout=True,
                    stderr=False,
                )
            except docker.errors.ImageNotFound:
                raise ValueError(f"Docker image '{source_ref}' not found")
            if isinstance(output, bytes):
                output = output.decode()
            data = parse_subkey_output(output)
            values["type"] = ExecType.DOCKER

        else:
            f"'{source_ref}' is neither an existing executable path nor a valid Docker image <name:tag>"

        # Validate public_key is 32-byte hex
        pub = data.get("public_key")
        if not pub or not is_valid_public_key(pub):
            raise ValueError(
                f"Invalid sr25519 public key generated using provided executable {source_ref}: {pub}"
                f"Command ran: {command}"
                f"Output: {data}"
                "If your node is a custom build and this is not expected, please report this issue on https://github.com/weezy20/pysubnet/issues"
            )

        return values


class Substrate:
    """
    Represents a Substrate runtime interface either via a local binary or Docker image.
    """

    def __init__(self, source_ref: str):
        # Determine absolute path for filesystem binaries
        path_obj = Path(source_ref)
        if path_obj.exists():
            source = str(path_obj.resolve())
        else:
            source = source_ref

        self.source = source
        # Construct and validate the SubstrateType
        self.type = SubstrateType(source=source)

    def __repr__(self):
        return f"<Substrate source={self.source!r} type={self.type.type.value}>"


if __name__ == "__main__":
    source_ref = sys.argv[1] if len(sys.argv) > 1 else "substrate"
    substrate = Substrate(source_ref)
    print(f"Substrate instance: {substrate}")
    print(f"SubstrateType instance: {substrate.type}")
    print(f"ExecType instance: {substrate.type.type}")
    print(f"ExecType value: \"{substrate.type.type.value}\"")
