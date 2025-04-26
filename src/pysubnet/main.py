import os
import json
from pathlib import Path
import sys
import shutil

from rich.console import Console
from rich.progress import Progress
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Confirm, Prompt

from pysubnet.chainspec import Chainspec, ChainspecType
from pysubnet.helpers.substrate import Substrate

from .helpers import (
    l2_seg,
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
            SUBSTRATE.run_command(
                [
                    "key",
                    "generate-node-key",
                    "--file",
                    f"{node['name']}-node-private-key",
                ],
                cwd=f"{node['base_path']}",
            )
            node["libp2p-public-key"] = SUBSTRATE.run_command(
                [
                    "key",
                    "inspect-node-key",
                    "--file",
                    f"{node['name']}-node-private-key",
                ],
                cwd=f"{node['base_path']}",
            )["stdout"].strip()
            with open(
                f"{ROOT_DIR}/{node['name']}/{node['name']}-node-private-key", "r"
            ) as key_file:
                node["libp2p-private-key"] = key_file.read().strip()

            # Generate AURA keys (Sr25519)
            aura_result = SUBSTRATE.run_command(
                ["key", "generate", "--scheme", "Sr25519"],
                cwd=f"{node['base_path']}",
            )
            aura = parse_subkey_output(aura_result["stdout"])
            node["aura-public-key"] = aura["public_key"]
            node["aura-private-key"] = aura["secret"]
            node["aura-secret-phrase"] = aura["secret_phrase"]
            node["aura-ss58"] = aura["ss58_address"]

            # Generate Grandpa keys (Ed25519)
            grandpa_result = SUBSTRATE.run_command(
                ["key", "generate", "--scheme", "Ed25519"],
                cwd=f"{node['base_path']}",
            )
            grandpa = parse_subkey_output(grandpa_result["stdout"])
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
                validator_result = SUBSTRATE.run_command(
                    ["key", "generate", "--scheme", "Sr25519"],
                    cwd=f"{node['base_path']}",
                )
                validator = parse_subkey_output(validator_result["stdout"])
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


def insert_keystore(chainspec: Chainspec, alternate=None):
    """Insert Aura/Grandpa session keys into keystore for a particular Chainspec instance.
    Args:
        chainspec (Chainsepc): Instance of Chainspec to use
        alternate (str, optional): Move generated keys to alternate path, a different "chain_id" directory
    """

    original_chainid = chainspec.get_chainid_with(SUBSTRATE)
    with Progress() as progress:
        task = progress.add_task(
            "[cyan]Inserting keys into keystore...", total=len(NODES) * 2
        )

        for node in NODES:
            # Insert AURA keys
            SUBSTRATE.run_command(
                [
                    "key",
                    "insert",
                    "--base-path",
                    node["name"],
                    "--chain",
                    str(chainspec),
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
            SUBSTRATE.run_command(
                [
                    "key",
                    "insert",
                    "--base-path",
                    node["name"],
                    "--chain",
                    str(chainspec),
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
        for node in NODES:
            orginal_keystore = Path(
                os.path.join(
                    ROOT_DIR, node["name"], "chains", original_chainid, "keystore"
                )
            )
            alternate_chain_dir = Path(
                os.path.join(ROOT_DIR, node["name"], "chains", alternate)
            )

            # Ensure the target directory exists
            alternate_chain_dir.mkdir(parents=True, exist_ok=True)

            try:
                # Move the keystore directory into the alternate chain directory
                # shutil.move needs string paths
                shutil.move(orginal_keystore, alternate_chain_dir)

                # Remove the original parent directory ('.../chains/<original_chainid>')
                # original_keystore_p.parent gets the directory containing 'keystore'
                shutil.rmtree(orginal_keystore.parent)

            except Exception as e:
                console.print(
                    f"[bold red]Error processing keystore move for {node['name']}: {e}[/bold red]"
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


def init_bootnodes_chainspec(chainspec: Chainspec, config: CliConfig) -> Chainspec:
    """Generate chainspec with rich output"""
    console.print(
        Panel.fit(
            "[bold cyan]Generating chainspec[/bold cyan] "
            f"[dim]Using template: {chainspec}[/dim]"
        )
    )

    c = chainspec.load_json()  # In-memory chainspec buffer
    if isinstance(chainspec.value, ChainspecType):
        console.print(f"[dim]Generating new [{chainspec}] chainspec...[/dim]")
        c = SUBSTRATE.run_command(
            [
                "build-spec",
                "--chain",
                str(chainspec),
                "--disable-default-bootnode",
            ],
            cwd=ROOT_DIR,
            json=True,
        )

    # Set bootnodes
    if config.substrate.is_bin:
        c["bootNodes"] = [
            f"/ip4/127.0.0.1/tcp/{n['p2p-port']}/p2p/{n['libp2p-public-key']}"
            for n in NODES
        ]
    elif config.substrate.is_docker:
        c["bootNodes"] = [
            f"/ip4/{n['docker-ip']}/tcp/{30333}/p2p/{n['libp2p-public-key']}"
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


def generate_raw_chainspec(chainspec_path: Path) -> Path:
    console.print(Panel.fit("[bold cyan]Generating raw chainspec[/bold cyan]"))

    raw_chainspec_path = os.path.join(ROOT_DIR, "raw_chainspec.json")
    with console.status("[cyan]Building raw chainspec...[/cyan]"):
        if SUBSTRATE.is_docker:
            # Use just the filename for Docker, since ROOT_DIR is mounted
            chainspec_filename = os.path.basename(chainspec_path)
            result = SUBSTRATE.run_command(
                [
                    "build-spec",
                    "--chain",
                    chainspec_filename,
                    "--raw",
                ],
                cwd=ROOT_DIR,
                json=True,
            )
        else:
            result = SUBSTRATE.run_command(
                [
                    "build-spec",
                    "--chain",
                    chainspec_path,
                    "--raw",
                ],
                cwd=ROOT_DIR,
                json=True,
            )

        with open(raw_chainspec_path, "w") as f:
            f.write(json.dumps(result, indent=2))

    console.print(
        Panel.fit(
            "[green]Raw chainspec generated[/green]\n"
            f"[dim]{l2_seg(raw_chainspec_path)}[/dim]",
        )
    )
    return raw_chainspec_path


def main():
    config = parse_args()
    global INTERACTIVE, RUN_NETWORK, ROOT_DIR, SUBSTRATE, CHAINSPEC, NODES
    INTERACTIVE = config.interactive
    RUN_NETWORK = config.run_network
    ROOT_DIR = config.root_dir
    SUBSTRATE = config.substrate
    CHAINSPEC = config.chainspec
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

    # Validate SUBSTRATE
    if config.substrate is None:
        if INTERACTIVE:
            console.print(
                "[yellow]⚠ Substrate binary/docker image not specified[/yellow]"
            )
            config.substrate = Substrate(
                Prompt.ask(
                    "Path to substrate binary or <docker image>:<tag>",
                    default="./substrate",
                    show_default=True,
                )
            )
            SUBSTRATE = config.substrate
        elif not INTERACTIVE:
            console.print("Using default substrate binary path: ./substrate")
            config.substrate = Substrate(os.path.join(os.getcwd(), "substrate"))
            SUBSTRATE = config.substrate

    # Interactive mode for account type
    match (config.account_key_type, INTERACTIVE):
        case (None, True):  # no --account + -i
            config.account_key_type = AccountKeyType.from_string(
                Prompt.ask(
                    "Select account key type",
                    choices=["ecdsa", "sr25519"],
                    default="ecdsa",
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
    if SUBSTRATE.is_docker:
        summary.append("Substrate docker image: ", style="dim")
        summary.append(f"{str(SUBSTRATE)}\n", style="green")
    else:
        summary.append("Substrate binary: ", style="dim")
        summary.append(f"{str(SUBSTRATE.source)}\n", style="green")
    summary.append("Root directory: ", style="dim")
    summary.append(f"{ROOT_DIR}\n", style="yellow")
    summary.append("Account key type: ", style="dim")
    summary.append(f"{config.account_key_type.value}", style="magenta")

    # Print as a single panel
    console.print(
        Panel.fit(
            summary,
            title="[bold cyan]-- Pysubnet Config --[/bold cyan]",
            padding=(1, 2),
        )
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
    insert_keystore(CHAINSPEC, alternate=customChainId)

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
                SUBSTRATE.start_network(config)
            else:
                console.print("[yellow]Aborting network start[/yellow]")
                sys.exit(0)
        else:
            SUBSTRATE.start_network(config)


if __name__ == "__main__":
    main()
