import os
import json
from pathlib import Path
from pprint import pprint
import subprocess
import time
import sys
import shutil

from .helpers import (
    prompt_bool,
    prompt_path,
    run_command,
    parse_subkey_output,
    prompt_str,
)
from .accounts import AccountKeyType
from .chainspec_handlers import custom_network_config, enable_poa
from .config import parse_args, Config
from .ethereum import generate_ethereum_keypair

global INTERACTIVE, RUN_NETWORK, SUBSTRATE, ROOT_DIR, CHAINSPEC, NODES


def generate_keys(account_key_type: AccountKeyType):
    """Generate keys
    Generates keys for the nodes:
    - Generates libp2p node-key
    - Generates AURA sr25519 key
    - Generates Grandpa ed25519 key
    - Generates validator account keys based on `account_type`
    """
    for node in NODES:
        print(f"Setting up {node['name']} @ {node['base_path']}...")
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
        print("\tLibp2p node key: ", node["libp2p-public-key"], "\n")

        # Generate Aura keys (Sr25519)
        aura_result = run_command([SUBSTRATE, "key", "generate", "--scheme", "Sr25519"])
        aura = parse_subkey_output(aura_result.stdout)
        print("\tAura public key (ss58):", aura["ss58_address"], "\n")
        node["aura-public-key"] = aura["public_key"]
        node["aura-private-key"] = aura["secret"]
        node["aura-secret-phrase"] = aura["secret_phrase"]
        node["aura-ss58"] = aura["ss58_address"]

        # Generate Grandpa keys (Ed25519)
        grandpa_result = run_command(
            [SUBSTRATE, "key", "generate", "--scheme", "Ed25519"]
        )
        grandpa = parse_subkey_output(grandpa_result.stdout)
        print("\tGrandpa public key (ss58):", grandpa["ss58_address"], "\n")
        node["grandpa-public-key"] = grandpa["public_key"]
        node["grandpa-private-key"] = grandpa["secret"]
        node["grandpa-secret-phrase"] = grandpa["secret_phrase"]
        node["grandpa-ss58"] = grandpa["ss58_address"]

        # Generate account keys
        match account_key_type:
            case AccountKeyType.AccountId20:
                validator = generate_ethereum_keypair()
                node["validator-accountid20-private-key"] = validator["private_key"]
                node["validator-accountid20-public-key"] = validator["ethereum_address"]
                print(
                    "\tValidator AccountId20 (ecdsa) public-key",
                    node["validator-accountid20-public-key"],
                    "\n",
                )
            case AccountKeyType.AccountId32:
                validator_result = run_command(
                    [SUBSTRATE, "key", "generate", "--scheme", "Sr25519"]
                )
                validator = parse_subkey_output(validator_result.stdout)
                node["validator-accountid32-private-key"] = validator["secret"]
                node["validator-accountid32-public-key"] = validator["public_key"]
                node["validator-accountid32-ss58"] = validator["ss58_address"]
                print(
                    "\tValidator AccountId32 (sr25519) public-key",
                    node["validator-accountid32-ss58"],
                    "\n",
                )
        # pprint(node)
    # Write node configuration to a JSON file
    with open(os.path.join(ROOT_DIR, "pysubnet.json"), "w") as f:
        json.dump(NODES, f, indent=4)
    with open(f"{ROOT_DIR}/pysubnet.json", "w") as f:
        json.dump(NODES, f, indent=4)


def insert_keystore(chainspec: str):
    """Insert AURA + Grandpa private keys into node keystore"""
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


def setup_dirs():
    """
    Should be called before any other function
    Creates the directory structure for the nodes
    """
    # Create root-dir, if exists, prompt to clean, otherwise exit program
    os.makedirs(ROOT_DIR, exist_ok=True)
    non_empty_exception = Exception(
        "Non-empty <ROOT_DIR>. Using existing non-empty <ROOT_DIR> is unsupported.",
        "Exiting program. Run with `--clean` or `--i` to clear ROOT_DIR or select a new root directory with --root",
        ROOT_DIR,
    )
    if len(os.listdir(ROOT_DIR)) > 0:  # ROOT_dir is not empty
        if INTERACTIVE:
            if prompt_bool(
                "Root directory is not empty. Clear it out? (yes/y/yay/no)",
                default=True,
            ):
                shutil.rmtree(ROOT_DIR)  # Runs with --clean
                os.makedirs(ROOT_DIR, exist_ok=True)
            else:
                raise non_empty_exception
        else:  # non-interactive mode
            raise non_empty_exception
    # Create directories
    for node in NODES:
        os.makedirs(f"{ROOT_DIR}/{node['name']}", exist_ok=False)  # Prevent overwrites
        node["base_path"] = f"{ROOT_DIR}/{node['name']}"


def init_bootnodes_chainspec(chainspec: str) -> Path:
    """Generate a new chainspec @ <ROOT_DIR>/chainspec.json and insert bootnodes into it
    If chainspec file is provided as arg, that's used as template.
    This function is required to be called before other chainspec editing functions
    to ensure that they work properly with ROOTDIR/chainspec.json
    """
    c: str = None  # In-memory chainspec buffer
    # Generate initial chainspec
    if chainspec in ["dev", "local"]:  # No explicit file passed
        print(f"Generating new {chainspec} chainspec...")
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
        except json.JSONDecodeError:  # Redundant check, but good practice
            raise ValueError(f"File exists but is not valid JSON: {chainspec}")
    # Set bootnodes
    c["bootNodes"] = [
        f"/ip4/127.0.0.1/tcp/{n['p2p-port']}/p2p/{n['libp2p-public-key']}"
        for n in NODES
    ]
    chainspec_path = os.path.join(ROOT_DIR, "chainspec.json")
    with open(chainspec_path, "w") as f:
        json.dump(c, f, indent=2)
    print(f"Chainspec written to      -> [{chainspec_path}]")
    return chainspec_path


def generate_raw_chainspec(chainspec: Path) -> Path:
    """
    Generates a raw chainspec file and writes it to ROOT_DIR/raw_chainspec.json.

    Args:
        chainspec (Path): The chain specification to use. This is the generated chainspec file from `init_bootnodes_chainspec()`

    Returns:
        Path: The path to the generated raw chainspec file.
    """
    raw_chainspec_path = os.path.join(ROOT_DIR, "raw_chainspec.json")
    try:
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
        print(f"Raw chainspec written to  -> [{raw_chainspec_path}]")
        return raw_chainspec_path
    except subprocess.CalledProcessError as e:
        raise Exception(f"Failed to generate raw chainspec: {e.stderr}")


def start_network(config: Config):
    print(f"Starting network with {len(NODES)} nodes...")
    # Start nodes
    node_procs = []
    for i, node in enumerate(NODES):
        # Should be executed inside ROOT_DIR
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
            # "--rpc-external", # is an error to run with --validator
        ]
        log_file = open(f"{ROOT_DIR}/{node['name']}/{node['name']}.log", "w")
        err_log_file = open(f"{ROOT_DIR}/{node['name']}/{node['name']}.error.log", "w")
        # This is not a mistake. Substrate nodes write normal logs to stderr. Weird.
        p = subprocess.Popen(cmd, stdout=err_log_file, stderr=log_file, cwd=ROOT_DIR)
        node_procs.append(
            {
                "process": p,
                "log_file": log_file,
                "err_log_file": err_log_file,
                "name": node["name"],
            }
        )
        print(f"Started {node['name']} (PID: {p.pid})")

    print("\nNetwork is running! Press Ctrl+C to stop")
    print("Check logs: ")
    pprint(
        [os.path.join(ROOT_DIR, node["name"], node["name"] + ".log") for node in NODES],
    )
    try:
        while True:
            time.sleep(1.5)  # 1.5 second sleep to reduce CPU usage.
    except KeyboardInterrupt:
        print("\nStopping nodes...")
        # Step 1: Send SIGTERM to all processes
        for node_proc in node_procs:
            node_proc["process"].terminate()
        # Step 2: Wait for processes to terminate, with a timeout
        for node_proc in node_procs:
            p = node_proc["process"]
            try:
                p.wait(timeout=2)  # Wait up to 2 seconds
            except subprocess.TimeoutExpired:
                print(
                    f"Process {p.pid} ({node_proc['name']}) did not terminate in time, killing it."
                )
                p.kill()  # Forcefully terminate with SIGKILL
                p.wait()  # Ensure it’s fully terminated
        # Step 3: Close all log files
        for node_proc in node_procs:
            node_proc["log_file"].close()
            node_proc["err_log_file"].close()
        print("All nodes stopped and log files closed.")


def main():
    config = parse_args()
    global INTERACTIVE, RUN_NETWORK, ROOT_DIR, SUBSTRATE, CHAINSPEC, NODES
    INTERACTIVE = config.interactive
    RUN_NETWORK = config.run_network
    ROOT_DIR = config.root_dir
    SUBSTRATE = config.bin
    CHAINSPEC = config.chainspec
    NODES = config.nodes

    # Validate root-dir
    if not os.path.exists(config.root_dir):
        os.makedirs(config.root_dir, exist_ok=True)
    if not os.path.isdir(config.root_dir):
        raise Exception(f"Root path is not a directory: {config.root_dir}")

    # Run --clean
    if config.clean:
        print(f"Cleaning up {config.root_dir}...")
        shutil.rmtree(config.root_dir)

    # Validate SUBSTRATE points to a file on the system and is executable
    if INTERACTIVE:
        if config.bin is None:  # -i without --bin
            # Prompt user for path to substrate binary
            print(
                f"Substrate binary not found in cwd or not executable: {config.bin}\n"
                "Please provide the path to the substrate binary:"
            )
            config.bin = prompt_path(
                "Path to substrate binary",
                default="./substrate",
            )
        SUBSTRATE = os.path.abspath(config.bin)
    elif (
        not INTERACTIVE and config.bin is None
    ):  # neither -i nor --bin, Default to `./substrate`
        config.bin = os.path.join(os.getcwd(), "substrate")
        SUBSTRATE = os.path.abspath(config.bin)

    # Validate SUBSTRATE
    if not os.path.isfile(config.bin) or not os.access(config.bin, os.X_OK):
        raise Exception(
            f"Substrate binary not found or not executable: {config.bin}\n"
            "Potential Solutions:\n"
            '1. Check if a substrate bin named "substrate" is present in cwdpath.\n'
            "2. Ensure the file is executable.\n"
            "3. Provide --bin <path/to/your/node> to specify a different binary. Such as --bin ./target/release/substrate-node-template\n"
            "4. Use -i to select a binary interactively.\n"
        )

    # Validate chainspec if it's a valid json file or one of "dev", "local"
    if os.path.isfile(config.chainspec):
        try:
            with open(config.chainspec, "r") as f:
                json.load(f)
            CHAINSPEC = os.path.abspath(config.chainspec)
            config.chainspec = CHAINSPEC
        except json.JSONDecodeError:
            raise Exception(f"Chainspec file is not valid JSON: {config.chainspec}")
    elif config.chainspec in ["dev", "local"]:
        pass
    else:
        raise Exception(f"Invalid chainspec argument: {config.chainspec}")

    # Interactive mode for account type
    match (config.account_key_type, INTERACTIVE):
        case (None, True):  # no --account and -i
            config.account_key_type = AccountKeyType.from_string(
                prompt_str(
                    "Select account key type (ecdsa, sr25519)", default="sr25519"
                )
            )
        case (None, False):  # non-interactive mode without --account, default to ecdsa
            config.account_key_type = AccountKeyType.AccountId20
        case (account, _) if account is not None:  # --account specified, skip prompt
            # Validation is taken care of by argparse itself
            config.account_key_type = account
        case _:  # Unreachable
            pass

    print(f"Using chainspec        -> [{CHAINSPEC}]")
    print(f"Using substrate binary -> [{SUBSTRATE}]")
    print(f"Using ROOT_DIR         -> [{ROOT_DIR}]")
    print(f"Using AccountKeyType   -> [{config.account_key_type.value}]")
    # Setup directory tree for NODEs
    setup_dirs()
    # Generate keys and setup nodes
    generate_keys(account_key_type=config.account_key_type)
    if INTERACTIVE:
        # Prompt user to proceed with key insertion
        if not prompt_bool(
            "Keys generated. Proceed to insert? (yes/y/yay/no/n)", default=True
        ):
            print("Aborting key insertion and exiting pysubnet.")
            return
        insert_keystore(CHAINSPEC)
    else:
        insert_keystore(CHAINSPEC)
    # Modified chainspec with bootnodes inserted
    chainspec = init_bootnodes_chainspec(
        CHAINSPEC
    )  # Initializes ROOT_DIR/chainspec.json
    # Generate raw chainspec
    config.raw_chainspec = generate_raw_chainspec(chainspec)
    if INTERACTIVE and not config.poa:
        proceed = prompt_bool(
            "Does your node only require Aura/Grandpa authorities (Proof-of-Authority node as in node-template/frontier-template)?\n"
            "Select no if you're using a custom_network_config with pallet-sessions or some other setup\n"
            "Yes -> enable_poa (standard) | No -> custom_network_config handler() (yes/yay/y/no/n/nay)",
            default=False,
        )
        if proceed:
            # Compatible with substrate proof-of-authority type setups where session key is (aura, grandpa)
            enable_poa(chainspec, config)
        else:
            custom_network_config(chainspec, config)
    else:
        if config.poa:
            enable_poa(chainspec, config)
        else:
            custom_network_config(chainspec, config)

    if RUN_NETWORK:
        if INTERACTIVE:
            if prompt_bool("Start substrate network? (yes/y/yay/no/n)", default=True):
                start_network(config)
            else:
                print("Aborting network start.")
                sys.exit(0)
        else:
            start_network(config)


if __name__ == "__main__":
    main()
