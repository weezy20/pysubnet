import os
import re
import sys
from enum import Enum
from pathlib import Path
from typing import List

import docker
from pydantic import BaseModel, model_validator
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from pysubnet.cli import CliConfig

from .process import is_valid_public_key, parse_subkey_output, run_command


class ExecType(str, Enum):
    BIN = "bin"
    DOCKER = "docker"


class SubstrateType(BaseModel):
    """
    Validates and represents a Substrate runtime interface
    via a local binary or Docker image.

    Attributes:
        source (str): Resolved path or image name:tag
        exec_type (ExecType): BIN for local binaries, DOCKER for containers
    """

    source: str
    exec_type: ExecType

    @model_validator(mode="before")
    def validate(cls, values):
        source_ref = values.get("source")
        if not source_ref:
            raise ValueError("`source` is required and cannot be empty")

        command = ["key", "generate", "--scheme", "sr25519"]
        data = None

        # Try filesystem binary first
        path = Path(source_ref).expanduser()
        if path.exists():
            resolved = str(path.resolve())
            if not path.is_file():
                raise ValueError(f"Not a file: {resolved}")
            if not os.access(resolved, os.X_OK):
                raise ValueError(f"Not executable: {resolved}")
            proc = run_command([resolved, *command])
            data = parse_subkey_output(proc.stdout)
            values["source"] = resolved
            values["exec_type"] = ExecType.BIN

        # Otherwise, expect Docker image name:tag
        elif re.fullmatch(r"[\w./-]+:[\w.-]+", source_ref):
            console = Console()
            client = docker.from_env()
            console.print(f"Searching Docker image '{source_ref}'...")
            progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            )
            with progress:
                task = progress.add_task("Connecting to Docker daemon...", start=False)
                for line in client.api.pull(source_ref, stream=True, decode=True):
                    status = line.get("status")
                    detail = line.get("progress") or line.get("progressDetail")
                    desc = status
                    if detail:
                        desc = f"{status} {detail}"
                    progress.update(task, description=desc)
                    progress.start_task(task)
            container = client.containers.run(
                source_ref, command, remove=True, stdout=True, stderr=True
            )
            data = parse_subkey_output(container.decode("utf-8"))
            values["exec_type"] = ExecType.DOCKER

        else:
            raise ValueError(
                f"Invalid source '{source_ref}': must be an existing executable path "
                "or a valid Docker image name:tag"
            )

        # Ensure public key is valid sr25519 hex (32 bytes)
        pub = data.get("public_key")
        if not pub or not is_valid_public_key(pub):
            src = values.get("source", source_ref)
            raise ValueError(
                f"Invalid sr25519 public key generated using provided executable {src}: {pub}\n"
                f"Command ran: {command}\n"
                f"Output: {data}\n"
                "If your node is a custom build and this is not expected, "
                "please report this issue on https://github.com/weezy20/pysubnet/issues"
            )

        return values


class Substrate:
    """
    High-level wrapper for a Substrate interface.

    On initialization, validates the provided source,
    and exposes the exec_type and resolved source.
    """

    def __init__(self, source: str):
        # Delegate validation and resolution to SubstrateType
        self.config = SubstrateType(source=source)
        self.running_nodes = []  # For use with BIN
        self.running_containers = []  # For use with DOCKER
        self.open_files = []  # For log and log.error files

    @property
    def exec_type(self) -> ExecType:
        return self.config.exec_type

    @property
    def source(self) -> str:
        return self.config.source

    def __repr__(self):
        return f"<Substrate source={self.source!r} exec_type={self.exec_type.value}>"

    def run_command(self, command_args: List[str], cwd=None):
        if self.exec_type == ExecType.BIN:
            return run_command([self.source, *command_args], cwd=cwd)
        if self.exec_type == ExecType.DOCKER:
            client = docker.from_env()
            return client.containers.run(
                self.source,
                command_args,
                remove=True,
                stdout=True,
                stderr=True,
                working_dir=cwd,
            )

    def start_network(self, config: CliConfig):
        """Spawns a substrate node"""
        pass


if __name__ == "__main__":
    ref = sys.argv[1] if len(sys.argv) > 1 else "substrate"
    sub = Substrate(ref)
    print(sub)
    print(f"Type: {sub.exec_type}, Source: {sub.source}")
