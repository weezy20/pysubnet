import os
import json
import subprocess
import time
import sys
import shutil
from pprint import pprint
from accounts import AccountKeyType

SUBSTRATE = os.path.abspath("substrate")  # your substrate node binary
ROOT_DIR = os.path.abspath("./substrate-network")  # Default root_dir
NODES = [
    {"name": "alice", "p2p_port": 30333, "rpc_port": 9944},
    {"name": "bob", "p2p_port": 30334, "rpc_port": 9945},
    {"name": "charlie", "p2p_port": 30335, "rpc_port": 9946},
]
"""
Runs a command in a given directory
"""


def run_command(command, cwd=None):
    result = subprocess.run(command, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        raise Exception(f"Command failed: {' '.join(command)}\n{result.stderr}")
    return result


"""Parses subkey output"""


def parse_subkey_output(output):
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


"""
Parses moonkey output, a subkey like tool but for Ethereum accounts
"""


def parse_moonkey_output(output):
    return {
        "private_key": output.split("Private Key:")[1].split()[0].strip(),
        "public_key": output.split("Address:")[1].split()[0].strip(),
    }


"""Generate keys
Generates keys for the nodes:
- Generates libp2p node-key
- Generates AURA sr25519 key
- Generates Grandpa ed25519 key
- Generates validator account keys based on `account_type`
"""


def generate_keys(account_type=AccountKeyType.AccountId20):
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

        # Generate Grandpa keys (Ed25519)
        grandpa_result = run_command(
            [SUBSTRATE, "key", "generate", "--scheme", "Ed25519"]
        )
        grandpa = parse_subkey_output(grandpa_result.stdout)
        print("\tGrandpa public key:", grandpa["public_key"], "\n")
        node["grandpa-public-key"] = grandpa["public_key"]
        node["grandpa-private-key"] = grandpa["secret"]
        node["grandpa-secret-phrase"] = grandpa["secret_phrase"]

        # Generate account keys
        match account_type:
            case AccountKeyType.AccountId20:
                validator_result = run_command(["moonkey"])
                validator = parse_moonkey_output(validator_result.stdout)
                node["validator-accountid20-private-key"] = validator["private_key"]
                node["validator-accountid20-public-key"] = validator["public_key"]
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


"""Insert keys into keystore"""


def insert_keystore(chainspec):
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
    if os.listdir(ROOT_DIR):
        raise Exception(
            "Root directory is not empty. Please clean or choose a different directory."
        )
    # Create directories
    for node in NODES:
        os.makedirs(f"{ROOT_DIR}/{node['name']}", exist_ok=False)  # Prevent overwrites
        node["base_path"] = f"{ROOT_DIR}/{node['name']}"


"""Generate a new chainspec with bootnodes populated into it
Final output is at ROOTDIR/chainspec.json"""


def insert_bootnodes(chainspec):
    c = None
    # Generate initial chainspec
    if chainspec in ["dev", "local"]: # No explicit file passed
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
            with open(chainspec, 'r') as f:
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

def main(chainspec="dev"):
    print("Using chainspec -> ", chainspec)
    # Setup directory tree for NODEs
    setup_dirs()
    # Generate keys and setup nodes
    generate_keys(account_type=AccountKeyType.AccountId20)
    # Prompt user to proceed with key insertion
    while True:
        proceed = input("Keys generated. Proceed to insert? (yes/no): ").strip().lower()
        if proceed in ["n", "no", "nay"]:
            print("Aborting key insertion.")
            return
        elif proceed in ["y", "yes", "yay"]:
            insert_keystore(chainspec)
            break
    insert_bootnodes(chainspec)  # Ignore main(chainspec) for the moment...

    # # Generate raw chainspec
    # run_command([
    #     "SUBSTRATE", "build-spec",
    #     "--chain", "chainspec.json",
    #     "--raw",
    #     "--disable-default-bootnode"
    # ], stdout=open("chainspec_raw.json", "w"))

    # # Start nodes
    # processes = []
    # for i, node in enumerate(NODES):
    #     cmd = [
    #         "SUBSTRATE",
    #         "--base-path", node["name"],
    #         "--chain", "chainspec_raw.json",
    #         "--port", str(node["p2p_port"]),
    #         "--rpc-port", str(node["rpc_port"]),
    #         "--ws-port", str(node["ws_port"]),
    #         "--validator",
    #         "--name", node["name"],
    #         "--node-key-file", f"{node['name']}/node-key",
    #         "--telemetry-url", "ws://telemetry.polkadot.io:1024 0",
    #         "--rpc-cors", "all",
    #         "--unsafe-rpc-external",
    #         "--unsafe-ws-external",
    #     ]
    #     log_file = open(f"{node['name']}.log", "w")
    #     processes.append(subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT))
    #     print(f"Started {node['name']} (PID: {processes[-1].pid})")

    # print("\nNetwork is running! Press Ctrl+C to stop")
    # try:
    #     while True:
    #         time.sleep(1)
    # except KeyboardInterrupt:
    #     print("\nStopping nodes...")
    #     for p in processes:
    #         p.terminate()
    #     for p in processes:
    #         p.wait()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "clean":
        if os.path.exists(ROOT_DIR):
            print(f"Cleaning up {ROOT_DIR}...")
            shutil.rmtree(ROOT_DIR)
    if "--chainspec" in sys.argv:
        try:
            chainspec_index = sys.argv.index("--chainspec")
            chainspec = sys.argv[chainspec_index + 1]
            main(chainspec=chainspec)
        except IndexError:
            raise Exception("Missing path after --chainspec argument")
    else:
        main()
