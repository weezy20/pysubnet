import os
import re
import shutil
import subprocess
import sys
from enum import Enum
from pathlib import Path
import tempfile
import time
from typing import Any, Dict, List, TYPE_CHECKING

import docker
from pydantic import BaseModel, model_validator
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

if TYPE_CHECKING:
    from pysubnet.cli import CliConfig

from .process import is_valid_public_key, parse_subkey_output, run_command
import json as json_lib

console = Console()


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

            # Check if image already exists locally
            try:
                client.images.get(source_ref)
                console.print(
                    f"[green]✓ Found Docker image '{source_ref}' locally[/green]"
                )
            except docker.errors.ImageNotFound:
                console.print(f"Searching Docker image '{source_ref}'...")
                progress = Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                    transient=True,
                )
                with progress:
                    task = progress.add_task(
                        "Connecting to Docker daemon...", start=False
                    )
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
            console.print(
                Panel.fit(
                    "[bold red]Error: Invalid Substrate binary or image[/bold red]",
                    subtitle=f"[dim]{source_ref}[/dim]",
                )
            )
            console.print("[yellow]Potential solutions:[/yellow]")
            console.print("- Check if the binary exists at the specified path")
            console.print("- Ensure the file is executable (try 'chmod +x <file>')")
            console.print("- Provide --bin <path/to/your/node>")
            console.print("- Use -i to select a binary interactively")
            console.print(
                "- Use --docker image:tag to pull a substrate node from docker registry"
            )
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
    def is_docker(self) -> bool:
        return self.exec_type == ExecType.DOCKER

    @property
    def is_bin(self) -> bool:
        return self.exec_type == ExecType.BIN

    @property
    def source(self) -> str:
        return self.config.source

    def __repr__(self):
        return f"<Substrate source={self.source!r} exec_type={self.exec_type.value}>"

    def run_command(self, command_args: List[str], cwd=None, json=False):
        if self.exec_type == ExecType.BIN:
            result = run_command([self.source, *command_args], cwd=cwd)
            if json:
                try:
                    return json_lib.loads(result.stdout)
                except json_lib.JSONDecodeError:
                    raise ValueError(f"Failed to parse JSON output: {result.stdout}")
            return {
                "stdout": result.stdout,
                "stderr": result.stderr if hasattr(result, "stderr") else "",
            }
        if self.exec_type == ExecType.DOCKER:
            client = docker.from_env()

            if json:
                # Prepare tmp.json path
                tmp_json_path = "tmp.json"
                if cwd:
                    tmp_json_path = os.path.join(cwd, "tmp", "tmp.json")
                    os.makedirs(os.path.dirname(tmp_json_path), exist_ok=True)
                else:
                    tmp_json_path = os.path.abspath(tmp_json_path)

                docker_mount_path = "/workspace"
                docker_tmp_mount_path = "/workspace/tmp"
                docker_json_path = f"{docker_tmp_mount_path}/tmp.json"

                # Get default entrypoint
                image_info = client.api.inspect_image(self.source)
                default_entrypoint = image_info.get("Config", {}).get("Entrypoint", [])

                # Compose the command for shell redirection
                cmd = (
                    " ".join([*default_entrypoint, *command_args])
                    + f" > {docker_json_path}"
                )

                try:
                    # Prepare volumes
                    volumes = {}
                    if cwd:
                        volumes[os.path.abspath(cwd)] = {
                            "bind": docker_mount_path,
                            "mode": "rw",
                        }
                        volumes[os.path.dirname(tmp_json_path)] = {
                            "bind": docker_tmp_mount_path,
                            "mode": "rw",
                        }
                    else:
                        volumes[os.path.dirname(tmp_json_path)] = {
                            "bind": docker_tmp_mount_path,
                            "mode": "rw",
                        }

                    # Run with shell as entrypoint to allow redirection
                    container = client.containers.run(
                        image=self.source,
                        entrypoint=["/bin/sh", "-c"],
                        command=[cmd],
                        volumes=volumes,
                        working_dir=docker_mount_path if cwd else docker_tmp_mount_path,
                        detach=True,
                    )
                    result = container.wait()
                    exit_code = result.get("StatusCode", 0)
                    container.remove()

                    if exit_code != 0:
                        raise RuntimeError(f"Container exited with code {exit_code}")

                    # Read and parse JSON
                    with open(tmp_json_path, "r") as f:
                        json_data = json_lib.load(f)
                    os.remove(tmp_json_path)
                    return json_data

                except Exception as e:
                    # Clean up tmp.json if it exists
                    if os.path.exists(tmp_json_path):
                        os.remove(tmp_json_path)
                    raise e
            else:
                # For non-JSON output, run container normally
                result = client.containers.run(
                    self.source,
                    command_args,
                    remove=True,
                    stdout=True,
                    stderr=True,
                    volumes={cwd: {"bind": "/workspace", "mode": "rw"}}
                    if cwd
                    else None,
                    working_dir="/workspace" if cwd else None,
                )
                return {"stdout": result.decode("utf-8")}

    def _display_network_status(self, config: "CliConfig"):
        """Show network status with rich table"""
        console.print(
            Panel.fit(
                "[bold green]🚀 Network is running![/bold green]",
                subtitle="[dim]Press [bold yellow]Ctrl+C[/bold yellow] to stop[/dim]",
            )
        )

        table = Table(title="Node Information", show_lines=True)
        table.add_column("Node", style="cyan", justify="center")
        table.add_column("Log File", style="magenta")
        table.add_column("Explorer Link", style="green")

        for node in config.nodes:
            log_path = os.path.join(
                config.root_dir, node["name"], f"{node['name']}.log"
            )
            explorer_link = f"https://polkadot.js.org/apps/?rpc=ws%3A%2F%2F127.0.0.1%3A{node['rpc-port']}#/explorer"
            table.add_row(
                node["name"], log_path, f"[link={explorer_link}]{explorer_link}[/link]"
            )

        console.print(table)

    def _start_network_bin(self, config: "CliConfig"):
        """Start network using local binary"""
        node_procs = []
        start_messages = []

        with Progress() as progress:
            task = progress.add_task("[cyan]Starting nodes...", total=len(config.nodes))

            for node in config.nodes:
                # Ensure node directory exists
                os.makedirs(f"{config.root_dir}/{node['name']}", exist_ok=True)

                cmd = [
                    self.source,
                    "--base-path",
                    node["name"],
                    "--chain",
                    config.raw_chainspec,
                    "--port",
                    str(node["p2p-port"]),
                    "--rpc-port",
                    str(node["rpc-port"]),
                    "--validator",
                    "--name",
                    node["name"],
                    "--node-key-file",
                    f"{node['name']}/{node['name']}-node-private-key",
                    "--rpc-cors",
                    "all",
                    "--prometheus-port",
                    str(node["prometheus-port"]),
                ]

                log_file = open(
                    f"{config.root_dir}/{node['name']}/{node['name']}.log", "w"
                )
                err_log_file = open(
                    f"{config.root_dir}/{node['name']}/{node['name']}.error.log", "w"
                )
                self.open_files.extend([log_file, err_log_file])

                p = subprocess.Popen(
                    cmd, stdout=err_log_file, stderr=log_file, cwd=config.root_dir
                )

                node_procs.append(
                    {
                        "process": p,
                        "log_file": log_file,
                        "err_log_file": err_log_file,
                        "name": node["name"],
                    }
                )

                progress.update(
                    task, advance=1, description=f"[cyan]Starting {node['name']}..."
                )
                start_messages.append(
                    f"\t[dim]Started {node['name']} (PID: [yellow]{p.pid}[/yellow])[/dim]"
                )

            progress.update(
                task,
                description="[bold green]✓ All nodes started successfully[/bold green]",
            )

        for msg in start_messages:
            console.print(msg, soft_wrap=True)

        self.running_nodes = node_procs
        self._display_network_status(config)

    def _start_network_containers(self, config: "CliConfig"):
        """Start network using Docker containers"""
        client = docker.from_env()
        start_messages = []

        with Progress() as progress:
            task = progress.add_task("[cyan]Starting nodes...", total=len(config.nodes))

            for node in config.nodes:
                # Ensure node directory exists
                os.makedirs(f"{config.root_dir}/{node['name']}", exist_ok=True)
                P2P_DEFAULT, RPC_DEFAULT, PROM_DEFAULT = 30333, 9944, 9615
                container = client.containers.run(
                    self.source,
                    command=[
                        "--base-path",
                        "/data",
                        "--chain",
                        f"/chainspec/{os.path.basename(config.raw_chainspec)}",
                        "--port",
                        str(P2P_DEFAULT),
                        "--rpc-port",
                        str(RPC_DEFAULT),
                        "--validator",
                        "--name",
                        node["name"],
                        "--node-key-file",
                        f"/data/{node['name']}-node-private-key",
                        "--rpc-cors",
                        "all",
                        "--prometheus-port",
                        str(PROM_DEFAULT),
                    ],
                    detach=True,
                    remove=True,
                    ports={
                        f"{P2P_DEFAULT}/tcp": node["p2p-port"],
                        f"{RPC_DEFAULT}/tcp": node["rpc-port"],
                        f"{PROM_DEFAULT}/tcp": node["prometheus-port"],
                    },
                    volumes={
                        os.path.join(config.root_dir, node["name"]): {
                            "bind": "/data",
                            "mode": "rw",
                        },
                        os.path.dirname(config.raw_chainspec): {
                            "bind": "/chainspec",
                            "mode": "ro",
                        },
                    },
                    name=node["name"],
                )

                self.running_containers.append(container)
                progress.update(
                    task, advance=1, description=f"[cyan]Starting {node['name']}..."
                )
                start_messages.append(
                    f"\t[dim]Started {node['name']} (Container ID: [yellow]{container.id[:12]}[/yellow])[/dim]"
                )

            progress.update(
                task,
                description="[bold green]✓ All nodes started successfully[/bold green]",
            )

        for msg in start_messages:
            console.print(msg, soft_wrap=True)

        self._display_network_status(config)

    def _stop_network_bin(self):
        """Stop network running as local processes"""
        print()
        console.print(Panel.fit("[bold red]🛑 Stopping network[/bold red]"))

        with Progress() as progress:
            task = progress.add_task(
                "[cyan]Stopping nodes...", total=len(self.running_nodes)
            )

            for node_proc in self.running_nodes:
                self._cleanup_node(node_proc)
                progress.update(task, advance=1)

        console.print("[bold green]✓ All nodes stopped successfully[/bold green]")
        self.running_nodes = []

    def _stop_network_containers(self):
        """Stop network running as Docker containers"""
        print()
        console.print(Panel.fit("[bold red]🛑 Stopping network[/bold red]"))

        with Progress() as progress:
            task = progress.add_task(
                "[cyan]Stopping nodes...", total=len(self.running_containers)
            )

            for container in self.running_containers:
                try:
                    container.stop()
                    progress.update(task, advance=1)
                except Exception as e:
                    console.print(
                        f"[red]Error stopping container {container.name}: {e}[/red]"
                    )

        console.print("[bold green]✓ All containers stopped successfully[/bold green]")
        self.running_containers = []

    def _cleanup_node(self, node_proc: Dict[str, Any]):
        """Cleanup node process and log files"""
        node_proc["process"].terminate()
        try:
            node_proc["process"].wait(timeout=2)
        except subprocess.TimeoutExpired:
            node_proc["process"].kill()
            node_proc["process"].wait()
        node_proc["log_file"].close()
        node_proc["err_log_file"].close()

    def start_network(self, config: "CliConfig"):
        """Spawns a substrate node network"""
        console.print(
            Panel.fit(
                f"[bold cyan]Starting network with {len(config.nodes)} nodes[/bold cyan]",
                subtitle="[dim]This may take a moment...[/dim]",
            )
        )

        if self.exec_type == ExecType.BIN:
            self._start_network_bin(config)
        else:
            self._start_network_containers(config)

        try:
            while True:
                time.sleep(1.5)
        except KeyboardInterrupt:
            self.stop_network()

    def stop_network(self):
        """Stops the running network"""
        if self.exec_type == ExecType.BIN:
            self._stop_network_bin()
        else:
            self._stop_network_containers()

        # Close any remaining open files
        for file in self.open_files:
            try:
                file.close()
            except Exception:
                pass
        self.open_files = []


if __name__ == "__main__":
    ref = sys.argv[1] if len(sys.argv) > 1 else "substrate"
    sub = Substrate(ref)
    print(sub)
    print(f"Type: {sub.exec_type}, Source: {sub.source}")
