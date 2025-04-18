import os
import json
from pathlib import Path
import subprocess
import time
import sys
import shutil

from rich.console import Console
from rich.table import Table
from rich.progress import Progress
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Confirm, Prompt

from pysubnet.chainspec import Chainspec

from .helpers import (
    l2_seg,
    run_command,
    parse_subkey_output,
)
from .accounts import AccountKeyType
from .chainspec_handlers import custom_network_config, enable_poa
from .cli import parse_args, CliConfig
from .ethereum import generate_ethereum_keypair

console = Console()
global INTERACTIVE, RUN_NETWORK, SUBSTRATE, ROOT_DIR, CHAINSPEC, NODES


def generate_keys(account_key_type: AccountKeyType):
    """
    Generates keys for the nodes:

    - Generates libp2p node-key
    - Generates AURA sr25519 key
    - Generates Grandpa ed25519 key
    - Generates validator account keys based on `account_key_type`

    Args:
        account_key_type (AccountKeyType): Type of account key to use for validator account id.
            Depends on the chain you're using
    """
    with console.status("[bold green]Generating keys for nodes...[/bold green]"):
        # Define consistent field widths for alignment
        key_type_width = 25
        value_width = 60

        for node in NODES:
            console.print(
                Panel.fit(
                    f"[bold cyan]Setting up {node['name']}[/bold cyan]",
                    subtitle=f"[dim]{l2_seg(node['base_path'])}[/dim]",
                )
            )
            # Generate node key and peer ID
            result = run_command(
                [
                    SUBSTRATE,
                    "key",
                    "generate-node-key",
                    "--file",
                    f"{node['name']}-node-private-key",
                ],
                cwd=f"{node['base_path']}",
            )
            node["libp2p-public-key"] = result.stderr.strip()
            with open(
                f"{ROOT_DIR}/{node['name']}/{node['name']}-node-private-key", "r"
            ) as key_file:
                node["libp2p-private-key"] = key_file.read().strip()

            # Generate AURA keys (Sr25519)
            aura_result = run_command(
                [SUBSTRATE, "key", "generate", "--scheme", "Sr25519"]
            )
            aura = parse_subkey_output(aura_result.stdout)
            node["aura-public-key"] = aura["public_key"]
            node["aura-private-key"] = aura["secret"]
            node["aura-secret-phrase"] = aura["secret_phrase"]
            node["aura-ss58"] = aura["ss58_address"]

            # Generate Grandpa keys (Ed25519)
            grandpa_result = run_command(
                [SUBSTRATE, "key", "generate", "--scheme", "Ed25519"]
            )
            grandpa = parse_subkey_output(grandpa_result.stdout)
            node["grandpa-public-key"] = grandpa["public_key"]
            node["grandpa-private-key"] = grandpa["secret"]
            node["grandpa-secret-phrase"] = grandpa["secret_phrase"]
            node["grandpa-ss58"] = grandpa["ss58_address"]

            # Generate account keys
            if account_key_type == AccountKeyType.AccountId20:
                validator = generate_ethereum_keypair()
                node["validator-accountid20-private-key"] = validator["private_key"]
                node["validator-accountid20-public-key"] = validator["ethereum_address"]
            else:
                validator_result = run_command(
                    [SUBSTRATE, "key", "generate", "--scheme", "Sr25519"]
                )
                validator = parse_subkey_output(validator_result.stdout)
                node["validator-accountid32-private-key"] = validator["secret"]
                node["validator-accountid32-public-key"] = validator["public_key"]
                node["validator-accountid32-ss58"] = validator["ss58_address"]

            # Display all keys in aligned format
            console.print(
                f"\t[dim]{'Libp2p node key':<{key_type_width}}[/dim] [cyan]{node['libp2p-public-key']:<{value_width}}[/cyan]"
            )
            console.print(
                f"\t[dim]{'Aura public key    (ss58)':<{key_type_width}}[/dim] [green]{node['aura-ss58']:<{value_width}}[/green]"
            )
            console.print(
                f"\t[dim]{'Grandpa public key (ss58)':<{key_type_width}}[/dim] [yellow]{node['grandpa-ss58']:<{value_width}}[/yellow]"
            )

            if account_key_type == AccountKeyType.AccountId20:
                console.print(
                    f"\t[dim]{'Validator AccountId20':<{key_type_width}}[/dim] [magenta]{node['validator-accountid20-public-key']:<{value_width}}[/magenta]"
                )
            else:
                console.print(
                    f"\t[dim]{'Validator AccountId32':<{key_type_width}}[/dim] [blue]{node['validator-accountid32-ss58']:<{value_width}}[/blue]"
                )

    # Write node configuration to a JSON file
    with open(os.path.join(ROOT_DIR, "pysubnet.json"), "w") as f:
        json.dump(NODES, f, indent=4)
    console.print(
        f"\n[bold green]✓ Node configuration saved to [cyan]{ROOT_DIR}/pysubnet.json[/cyan][/bold green]"
    )


def insert_keystore(chainspec: str, alternate=None):
    """Insert keys with rich progress
    Args:
        chainspec (str): chain_id to use
        alternate (str, optional): Move generated keys to alternate path, a different "chain_id" directory
    """
    with Progress() as progress:
        task = progress.add_task(
            "[cyan]Inserting keys into keystore...", total=len(NODES) * 2
        )

        for node in NODES:
            # Insert AURA keys
            run_command(
                [
                    SUBSTRATE,
                    "key",
                    "insert",
                    "--base-path",
                    node["name"],
                    "--chain",
                    chainspec,
                    "--scheme",
                    "Sr25519",
                    "--key-type",
                    "aura",
                    "--suri",
                    node["aura-private-key"],
                ],
                cwd=ROOT_DIR,
            )
            progress.update(
                task,
                advance=1,
                description=f"[cyan]Inserting AURA keys for {node['name']}",
            )

            # Insert Grandpa Keys
            run_command(
                [
                    SUBSTRATE,
                    "key",
                    "insert",
                    "--base-path",
                    node["name"],
                    "--chain",
                    chainspec,
                    "--scheme",
                    "Ed25519",
                    "--key-type",
                    "gran",
                    "--suri",
                    node["grandpa-private-key"],
                ],
                cwd=ROOT_DIR,
            )
            progress.update(
                task,
                advance=1,
                description=f"[cyan]Inserting Grandpa keys for {node['name']}",
            )
    if alternate is not None:
        original_path = os.path.join(node["name"], "chains", chainspec, "keystore")
        alternate_path = os.path.join(node["name"], "chains", alternate, "keystore")
        # Move generated keys to the keystore directory
        for node in NODES:
            shutil.move(
                original_path,
                alternate_path,
            )
    console.print("[bold green]✓ All keys inserted successfully[/bold green]")


def setup_dirs():
    """Create directories with rich output"""
    console.print(Panel.fit("[bold cyan]Setting up directory structure[/bold cyan]"))

    os.makedirs(ROOT_DIR, exist_ok=True)
    non_empty_exception = Exception(
        "Non-empty <ROOT_DIR>. Using existing non-empty <ROOT_DIR> is unsupported.",
        "Exiting program. Run with `--clean` or `--i` to clear ROOT_DIR or select a new root directory with --root",
        ROOT_DIR,
    )

    if len(os.listdir(ROOT_DIR)) > 0:  # ROOT_dir is not empty
        if INTERACTIVE:
            console.print(
                f"[yellow]⚠ Warning:[/yellow] Root directory [cyan]{ROOT_DIR}[/cyan] is not empty."
            )
            if Confirm.ask("Clear it out?", default=True):
                with console.status("[red]Cleaning directory...[/red]"):
                    shutil.rmtree(ROOT_DIR)
                    os.makedirs(ROOT_DIR, exist_ok=True)
                console.print("[green]✓ Directory cleaned[/green]")
            else:
                raise non_empty_exception
        else:  # non-interactive mode
            raise non_empty_exception

    # Create directories
    with console.status("[cyan]Creating node directories...[/cyan]"):
        for node in NODES:
            os.makedirs(f"{ROOT_DIR}/{node['name']}", exist_ok=False)
            node["base_path"] = f"{ROOT_DIR}/{node['name']}"
            console.print(
                f"\t[dim][green]✓[/green] Created directory for[/dim] [cyan]{node['name']}[/cyan]"
            )

    console.print("[bold green]✓ Directory structure ready[/bold green]")


def init_bootnodes_chainspec(chainspec: str, config: CliConfig) -> Path:
    """Generate chainspec with rich output"""
    console.print(
        Panel.fit(
            "[bold cyan]Generating chainspec[/bold cyan] "
            f"[dim]Using template: {chainspec}[/dim]"
        )
    )

    c: str = None  # In-memory chainspec buffer
    if chainspec in ["dev", "local"]:
        console.print(f"[dim]Generating new {chainspec} chainspec...[/dim]")
        c = json.loads(
            run_command(
                [
                    SUBSTRATE,
                    "build-spec",
                    "--chain",
                    chainspec,
                    "--disable-default-bootnode",
                ],
                cwd=ROOT_DIR,
            ).stdout
        )
    elif os.path.isfile(chainspec):
        try:
            with open(chainspec, "r") as f:
                c = json.load(f)
            console.print(f"[dim]Loaded chainspec from:[/dim] [cyan]{chainspec}[/cyan]")
        except json.JSONDecodeError:
            raise ValueError(f"File exists but is not valid JSON: {chainspec}")

    # Set bootnodes
    c["bootNodes"] = [
        f"/ip4/127.0.0.1/tcp/{n['p2p-port']}/p2p/{n['libp2p-public-key']}"
        for n in NODES
    ]
    chainspec_path = os.path.join(ROOT_DIR, "chainspec.json")

    if config.apply_chainspec_customizations:
        chainspec_config = config.network.chain
        if chainspec_config.chain_name:
            c["name"] = chainspec_config.chain_name
        if chainspec_config.chain_id:
            c["id"] = chainspec_config.chain_id
        if chainspec_config.chain_type:
            c["chainType"] = chainspec_config.chain_type

    with open(chainspec_path, "w") as f:
        json.dump(c, f, indent=2)

    console.print(
        Panel.fit(
            "[green]Chainspec generated successfully[/green]",
            subtitle=f"[dim]{l2_seg(chainspec_path)}[/dim]",
        )
    )
    return chainspec_path


def generate_raw_chainspec(chainspec: Path) -> Path:
    """Generate raw chainspec with rich output"""
    console.print(Panel.fit("[bold cyan]Generating raw chainspec[/bold cyan]"))

    raw_chainspec_path = os.path.join(ROOT_DIR, "raw_chainspec.json")
    try:
        with console.status("[cyan]Building raw chainspec...[/cyan]"):
            result = subprocess.run(
                [
                    SUBSTRATE,
                    "build-spec",
                    "--chain",
                    chainspec,
                    "--raw",
                ],
                cwd=ROOT_DIR,
                capture_output=True,
                text=True,
                check=True,
            )
            with open(raw_chainspec_path, "w") as f:
                f.write(result.stdout)

        console.print(
            Panel.fit(
                "[green]Raw chainspec generated[/green]\n"
                f"[dim]{l2_seg(raw_chainspec_path)}[/dim]",
            )
        )
        return raw_chainspec_path
    except subprocess.CalledProcessError as e:
        console.print("[bold red]Failed to generate raw chainspec[/bold red]")
        raise Exception(f"Failed to generate raw chainspec: {e.stderr}")


def display_network_status():
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

    for node in NODES:
        log_path = os.path.join(ROOT_DIR, node["name"], f"{node['name']}.log")
        explorer_link = f"https://polkadot.js.org/apps/?rpc=ws%3A%2F%2F127.0.0.1%3A{node['rpc-port']}#/explorer"
        table.add_row(
            node["name"], log_path, f"[link={explorer_link}]{explorer_link}[/link]"
        )

    console.print(table)


def stop_network(node_procs: list):
    """Stop network with rich progress"""
    print("\n")  # To make space for interrupt
    console.print(Panel.fit("[bold red]🛑 Stopping network[/bold red]"))

    with Progress() as progress:
        task = progress.add_task("[cyan]Stopping nodes...", total=len(NODES))

        for node in node_procs:
            cleanup_node(node)
            progress.update(task, advance=1)

    console.print("[bold green]✓ All nodes stopped successfully[/bold green]")


def start_network(config: CliConfig):
    """Start network with rich output"""
    console.print(
        Panel.fit(
            f"[bold cyan]Starting network with {len(NODES)} nodes[/bold cyan]",
            subtitle="[dim]This may take a moment...[/dim]",
        )
    )
    node_procs = []
    start_messages = []  # Store messages here

    with Progress() as progress:
        task = progress.add_task("[cyan]Starting nodes...", total=len(NODES))

        for i, node in enumerate(NODES):
            cmd = [
                SUBSTRATE,
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

            log_file = open(f"{ROOT_DIR}/{node['name']}/{node['name']}.log", "w")
            err_log_file = open(
                f"{ROOT_DIR}/{node['name']}/{node['name']}.error.log", "w"
            )

            p = subprocess.Popen(
                cmd, stdout=err_log_file, stderr=log_file, cwd=ROOT_DIR
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
            # Store the message instead of printing immediately
            start_messages.append(
                f"\t[dim]Started {node['name']} (PID: [yellow]{p.pid}[/yellow])[/dim]"
            )
        progress.update(
            task,
            description="[bold green]✓ All nodes started successfully[/bold green]",
        )

    # Print all collected messages after the progress bar finishes
    for msg in start_messages:
        console.print(msg, soft_wrap=True)

    display_network_status()
    try:
        while True:
            time.sleep(1.5)
    except KeyboardInterrupt:
        stop_network(node_procs)


def cleanup_node(node_proc: dict):
    """Cleanup node process and log files"""
    node_proc["process"].terminate()
    try:
        node_proc["process"].wait(timeout=2)
    except subprocess.TimeoutExpired:
        node_proc["process"].kill()
        node_proc["process"].wait()
    node_proc["log_file"].close()
    node_proc["err_log_file"].close()


def main():
    config = parse_args()
    # global INTERACTIVE, RUN_NETWORK, ROOT_DIR, SUBSTRATE, CHAINSPEC, NODES
    INTERACTIVE: bool = config.interactive
    RUN_NETWORK: bool = config.run_network
    ROOT_DIR = config.root_dir
    SUBSTRATE: Path = config.bin
    CHAINSPEC: Chainspec = config.chainspec
    NODES = config.nodes

    # Print header
    console.print(Panel.fit("[bold blue]PySubnet Network Manager[/bold blue]"))

    # Validate root-dir
    if not os.path.exists(config.root_dir):
        os.makedirs(config.root_dir, exist_ok=True)
    if not os.path.isdir(config.root_dir):
        raise Exception(f"Root path is not a directory: {config.root_dir}")

    # Run --clean
    if config.clean:
        console.print(
            Panel.fit(
                "[bold red]Cleaning up root directory[/bold red] "
                f"[dim]{config.root_dir}[/dim]",
            )
        )
        shutil.rmtree(config.root_dir)

    # Validate SUBSTRATE binary
    if INTERACTIVE and config.bin is None:
        console.print("[yellow]⚠ Substrate binary not specified[/yellow]")
        config.bin = Prompt.ask(
            "Path to substrate binary", default="./substrate", show_default=True
        )
        SUBSTRATE = os.path.abspath(config.bin)
    elif not INTERACTIVE and config.bin is None:
        config.bin = os.path.join(os.getcwd(), "substrate")
        SUBSTRATE = os.path.abspath(config.bin)
    else:
        SUBSTRATE = os.path.abspath(config.bin)

    # Validate SUBSTRATE
    if not os.path.isfile(SUBSTRATE) or not os.access(SUBSTRATE, os.X_OK):
        console.print(
            Panel.fit(
                "[bold red]Error: Invalid Substrate binary[/bold red]",
                subtitle=f"[dim]{SUBSTRATE}[/dim]",
            )
        )
        console.print("[yellow]Potential solutions:[/yellow]")
        console.print("1. Check if the binary exists at the specified path")
        console.print("2. Ensure the file is executable (try 'chmod +x <file>')")
        console.print("3. Provide --bin <path/to/your/node>")
        console.print("4. Use -i to select a binary interactively")
        raise Exception(f"Substrate binary not found or not executable: {SUBSTRATE}")

    # Interactive mode for account type
    match (config.account_key_type, INTERACTIVE):
        case (None, True):  # no --account + -i
            config.account_key_type = AccountKeyType.from_string(
                Prompt.ask(
                    "Select account key type",
                    choices=["ecdsa", "sr25519"],
                    default="sr25519",
                )
            )
        case (None, False):  # non-interactive mode without --account, default to ecdsa
            config.account_key_type = AccountKeyType.AccountId20
        case (account, _) if account is not None:  # --account specified, skip prompt
            config.account_key_type = account
        case _:  # Unreachable
            pass

    # Print configuration summary
    summary = Text()
    summary.append("Chainspec: ", style="dim")
    summary.append(f"{CHAINSPEC}\n", style="cyan")
    summary.append("Substrate binary: ", style="dim")
    summary.append(f"{SUBSTRATE}\n", style="green")
    summary.append("Root directory: ", style="dim")
    summary.append(f"{ROOT_DIR}\n", style="yellow")
    summary.append("Account key type: ", style="dim")
    summary.append(f"{config.account_key_type.value}", style="magenta")

    # Print as a single panel
    console.print(
        Panel.fit(summary, title="[bold cyan]-- Using --[/bold cyan]", padding=(1, 2))
    )

    # Setup directory tree for NODEs
    setup_dirs()

    # Generate keys and setup nodes
    generate_keys(account_key_type=config.account_key_type)

    customChainId = None
    if config.apply_chainspec_customizations:
        customChainId = config.network.chain.chain_id
        if customChainId:
            console.print(
                f"[dim]Using custom chain id from config file: {customChainId}[/dim]",
                style="bold yellow",
            )

    if INTERACTIVE:
        if not Confirm.ask("Keys generated. Proceed to insert?", default=True):
            console.print("[yellow]Aborting key insertion[/yellow]")
            return
        insert_keystore(CHAINSPEC)
    else:
        insert_keystore(CHAINSPEC)

    # Modified chainspec with bootnodes inserted
    chainspec = init_bootnodes_chainspec(CHAINSPEC, config)

    if INTERACTIVE and not config.poa:
        proceed = Confirm.ask(
            "Proceed with standard Aura/Grandpa authorities injection? (Proof-of-Authority)?\n"
            "[dim]Select no if you're using a custom setup defined in custom_network_config()\n[/dim]"
            "[dim]Yes -> Enable POA (standard) | No -> Custom setup [/dim]",
            default=True,
        )
        if proceed:
            enable_poa(chainspec, config)
        else:
            custom_network_config(chainspec, config)
    else:
        if config.poa:
            enable_poa(chainspec, config)
        else:
            custom_network_config(chainspec, config)

    # Generate raw chainspec
    config.raw_chainspec = generate_raw_chainspec(chainspec)

    if RUN_NETWORK:
        if INTERACTIVE:
            if Confirm.ask("Start substrate network?", default=True):
                start_network(config)
            else:
                console.print("[yellow]Aborting network start[/yellow]")
                sys.exit(0)
        else:
            start_network(config)


if __name__ == "__main__":
    main()
