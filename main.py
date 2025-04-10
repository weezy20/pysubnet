import os
import json
import subprocess
import time
import sys
import shutil
from pprint import pprint
from accounts import AccountKeyType
from chainspec_handlers import edit_vs_ss_authorities
from ethereum import generate_ethereum_keypair

INTERACTIVE = False
RUN_NETWORK = False
SUBSTRATE = os.path.abspath("substrate")  # your substrate node binary
ROOT_DIR = os.path.abspath("./network")  # Default root_dir
NODES = [
    {"name": "alice", "p2p_port": 30333, "rpc_port": 9944},
    {"name": "bob", "p2p_port": 30334, "rpc_port": 9945},
    {"name": "charlie", "p2p_port": 30335, "rpc_port": 9946},
]


def run_command(command, cwd=None):
    """
    Runs a command in a given directory
    """
    result = subprocess.run(command, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        raise Exception(f"Command failed: {' '.join(command)}\n{result.stderr}")
    return result


def parse_subkey_output(output):
    """Parses subkey output"""
    return {
        "secret_phrase": " ".join(
            output.split("Secret phrase:")[1].split()[:12]
        ).strip()
        if "Secret phrase:" in output
        else None,
        "secret": output.split("Secret seed:")[1].split()[0].strip(),
        "public_key": output.split("Public key (hex):")[1].split()[0].strip(),
        "ss58_address": output.split("Public key (SS58):")[1].split()[0].strip(),
        "account_id": output.split("Account ID:")[1].split()[0].strip(),
    }


def generate_keys(account_type=AccountKeyType.AccountId20):
    """Generate keys
    Generates keys for the nodes:
    - Generates libp2p node-key
    - Generates AURA sr25519 key
    - Generates Grandpa ed25519 key
    - Generates validator account keys based on `account_type`
    """

    for node in NODES:
        print(f"Setting up {node['name']}...")
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
        print("\tAura public key:", aura["public_key"], "\n")
        node["aura-public-key"] = aura["public_key"]
        node["aura-private-key"] = aura["secret"]
        node["aura-secret-phrase"] = aura["secret_phrase"]
        node["aura-ss58"] = aura["ss58_address"]

        # Generate Grandpa keys (Ed25519)
        grandpa_result = run_command(
            [SUBSTRATE, "key", "generate", "--scheme", "Ed25519"]
        )
        grandpa = parse_subkey_output(grandpa_result.stdout)
        print("\tGrandpa public key:", grandpa["public_key"], "\n")
        node["grandpa-public-key"] = grandpa["public_key"]
        node["grandpa-private-key"] = grandpa["secret"]
        node["grandpa-secret-phrase"] = grandpa["secret_phrase"]
        node["grandpa-ss58"] = grandpa["ss58_address"]

        # Generate account keys
        match account_type:
            case AccountKeyType.AccountId20:
                validator = generate_ethereum_keypair()
                node["validator-accountid20-private-key"] = validator["private_key"]
                node["validator-accountid20-public-key"] = validator["ethereum_address"]
            case AccountKeyType.AccountId32:
                validator_result = run_command(
                    [SUBSTRATE, "key", "generate", "--scheme", "Sr25519"]
                )
                validator = parse_subkey_output(validator_result.stdout)
                node["validator-accountid32-private-key"] = validator["secret"]
                node["validator-accountid32-public-key"] = validator["public_key"]
        # pprint(node)
    # Write node configuration to a JSON file
    print("Saving network contents to -> ", f"{ROOT_DIR}/pysubnet.json")
    with open(f"{ROOT_DIR}/pysubnet.json", "w") as f:
        json.dump(NODES, f, indent=4)


def insert_keystore(chainspec):
    """Insert keys into keystore"""

    # Insert keys into keystore
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
    # Create root-dir, if exists, prompt to clean, otherwise exit program
    os.makedirs(ROOT_DIR, exist_ok=True)
    if len(os.listdir(ROOT_DIR)) > 0 and INTERACTIVE:
        clear_root = (
            input("Root directory is not empty. Clear it out? yes/y/yay/no? ")
            .lower()
            .strip()
        )
        if clear_root in ["y", "yes", "yay"]:
            shutil.rmtree(ROOT_DIR)
            os.makedirs(ROOT_DIR, exist_ok=False)
        else:
            print(
                "Exiting program. Run with `clean` or `i` to clear ROOT_DIR -> ",
                ROOT_DIR,
            )
            sys.exit(1)

    elif len(os.listdir(ROOT_DIR)) > 0:
        raise Exception(
            "Exiting program. Run with `clean` or `i` to clear ROOT_DIR -> ",
            ROOT_DIR,
        )
    # Create directories
    for node in NODES:
        os.makedirs(f"{ROOT_DIR}/{node['name']}", exist_ok=False)  # Prevent overwrites
        node["base_path"] = f"{ROOT_DIR}/{node['name']}"


def init_chainspec(chainspec):
    """Generate a new chainspec and insert bootnodes into it
    If chainspec file is provided as arg, that's used as template instead of generating a new one.
    This function is required to be called before other chainspec editing functions
    to ensure that they work properly with ROOTDIR/chainspec.json
    """
    c = None
    # Generate initial chainspec
    if chainspec in ["dev", "local"]:  # No explicit file passed
        print("Generating new local chainspec...")
        c = json.loads(
            run_command(
                [
                    SUBSTRATE,
                    "build-spec",
                    "--chain",
                    "local",
                    "--disable-default-bootnode",
                ],
                cwd=ROOT_DIR,
            ).stdout
        )
    elif isinstance(chainspec, str) and os.path.isfile(chainspec):
        try:
            with open(chainspec, "r") as f:
                c = json.load(f)
        except json.JSONDecodeError:
            raise ValueError(f"File exists but is not valid JSON: {chainspec}")
    # Set bootnodes
    c["bootNodes"] = [
        f"/ip4/127.0.0.1/tcp/{n['p2p_port']}/p2p/{n['libp2p-public-key']}"
        for n in NODES
    ]

    with open(f"{ROOT_DIR}/chainspec.json", "w") as f:
        json.dump(c, f, indent=2)
    print("Chainspec written to", f"{ROOT_DIR}/chainspec.json")
    return f"{ROOT_DIR}/chainspec.json"


def generate_raw_chainspec(chainspec: str) -> str:
    """
    Generates a raw chainspec file and writes it to ROOT_DIR/raw_chainspec.json.

    Args:
        chainspec (str): The chain specification to use (e.g., "dev", "local", filesystem path).

    Returns:
        str: The path to the generated raw chainspec file.
    """
    raw_chainspec_path = f"{ROOT_DIR}/raw_chainspec.json"
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
        print(f"Raw chainspec written to {raw_chainspec_path}")
        return raw_chainspec_path
    except subprocess.CalledProcessError as e:
        raise Exception(f"Failed to generate raw chainspec: {e.stderr}")


def start_network(chainspec):
    print(f"Starting network with {len(NODES)} nodes...")
    # Generate raw chainspec
    raw_chainspec = generate_raw_chainspec(chainspec)

    # Start nodes
    node_procs = []
    for i, node in enumerate(NODES):
        # Should be executed inside ROOT_DIR
        cmd = [
            SUBSTRATE,
            "--base-path",
            node["name"],
            "--chain",
            raw_chainspec,
            "--port",
            str(node["p2p_port"]),
            "--rpc-port",
            str(node["rpc_port"]),
            "--validator",
            "--name",
            node["name"],
            "--node-key-file",
            f"{node['name']}/{node['name']}-node-private-key",
            "--rpc-cors",
            "all",
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
    try:
        while True:
            time.sleep(2)  # 2 second sleep to reduce CPU usage.
    except KeyboardInterrupt:
        print("\nStopping nodes...")
        # Step 1: Send SIGTERM to all processes
        for node_proc in node_procs:
            node_proc["process"].terminate()
        # Step 2: Wait for processes to terminate, with a timeout
        for node_proc in node_procs:
            p = node_proc["process"]
            try:
                p.wait(timeout=10)  # Wait up to 10 seconds
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


def main(chainspec_path_or_str="dev"):
    print(f"Using chainspec -> {chainspec_path_or_str}")
    print(f"Using substrate binary -> {SUBSTRATE}")
    print(f"Using ROOT_DIR -> {ROOT_DIR}")
    # Setup directory tree for NODEs
    setup_dirs()
    # Generate keys and setup nodes
    generate_keys(account_type=AccountKeyType.AccountId20)
    if INTERACTIVE:
        # Prompt user to proceed with key insertion
        while True:
            proceed = (
                input("Keys generated. Proceed to insert? (yes/no): ").strip().lower()
            )
            if proceed in ["n", "no", "nay"]:
                print("Aborting key insertion.")
                return
            elif proceed in ["y", "yes", "yay"]:
                insert_keystore(chainspec_path_or_str)
                break
    # Modified chainspec with bootnodes inserted
    chainspec = init_chainspec(
        chainspec_path_or_str
    )  # Initializes ROOT_DIR/chainspec.json
    edit_vs_ss_authorities(
        chainspec, NODES
    )  # Custom handler for a particular chain using substrate-validator-set and pallet-session
    if RUN_NETWORK:
        if INTERACTIVE:
            proceed = (
                input("Start substrate network? (yes/y/yay/no/n): ").strip().lower()
            )
            if proceed in ["y", "yes", "yay"]:
                start_network(chainspec)
            else:
                print("Aborting network start.")
                sys.exit(0)
        else:
            start_network(chainspec)


if __name__ == "__main__":
    if any(arg in sys.argv for arg in ["i", "interactive"]):
        INTERACTIVE = True
    if any(arg in sys.argv for arg in ["r", "run"]):
        RUN_NETWORK = True
    if any(arg in sys.argv for arg in ["clean", "c"]):
        if os.path.exists(ROOT_DIR):
            print(f"Cleaning up {ROOT_DIR}...")
            shutil.rmtree(ROOT_DIR)
    if "--chainspec" in sys.argv:
        try:
            chainspec_index = sys.argv.index("--chainspec")
            chainspec = sys.argv[chainspec_index + 1]
            main(chainspec_path_or_str=os.path.abspath(chainspec))
        except IndexError:
            raise Exception("Missing path after --chainspec argument")
    else:
        main()
