import os
import json
import subprocess
import time
import sys
import shutil
from pprint import pprint

SUBSTRATE = "substrate"
ROOT_DIR = "./substrate-testnet"
NODES = [
    {"name": "alice", "p2p_port": 30333, "rpc_port": 9944},
    {"name": "bob", "p2p_port": 30334, "rpc_port": 9945},
    {"name": "charlie", "p2p_port": 30335, "rpc_port": 9946},
]


def run_command(command, cwd=None):
    result = subprocess.run(command, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        raise Exception(f"Command failed: {' '.join(command)}\n{result.stderr}")
    return result


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


def parse_moonkey_output(output):
    return {
        "private_key": output.split("Priate Key:")[1].split()[0].strip(),
        "public_key": output.split("Address:")[1].split()[0].strip(),
    }


def main(chainspec="dev"):
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

    # Generate keys and setup nodes
    for node in NODES:
        print(f"Setting up {node['name']}...")
        # Generate node key and peer ID
        result = run_command(
            [
                "subkey",
                "generate-node-key",
                "--file",
                f"{node['name']}-node-private-key",
            ],
            cwd=f"{node['base_path']}",
        )
        node["libp2p-public-key"] = result.stderr.strip()
        print("\tLibp2p node key: ", node["libp2p-public-key"], "\n")
        
        # Generate Aura keys (Sr25519)
        aura_result = run_command(["subkey", "generate", "--scheme", "Sr25519"])
        aura = parse_subkey_output(aura_result.stdout)
        print("\tAura public key:", aura["public_key"], "\n")
        node["aura-public-key"] = aura["public_key"]
        node["aura-private-key"] = aura["secret"]
        node["aura-secret-phrase"] = aura["secret_phrase"]

        # Generate Grandpa keys (Ed25519)
        grandpa_result = run_command(["subkey", "generate", "--scheme", "Ed25519"])
        grandpa = parse_subkey_output(grandpa_result.stdout)
        print("\tGrandpa public key:", grandpa["public_key"], "\n")
        node["grandpa-public-key"] = grandpa["public_key"]
        node["grandpa-private-key"] = grandpa["secret"]
        node["grandpa-secret-phrase"] = grandpa["secret_phrase"]
        pprint(node)
    # Prompt user to proceed with key insertion
    while (True):
        proceed = input("Keys generated. Proceed to insert? (yes/no): ").strip().lower()
        if proceed in ["n", "no", "nay"]:
            print("Aborting key insertion.")
            return
        elif proceed in ["y", "yes", "yay"]:
            break
    #     # Insert keys into keystore
    #     run_command([
    #         "SUBSTRATE", "key", "insert",
    #         "--base-path", node["name"],
    #         "--scheme", "Sr25519",
    #         "--type", "aura",
    #         "--suri", aura["secret_phrase"]
    #     ])

    #     run_command([
    #         "SUBSTRATE", "key", "insert",
    #         "--base-path", node["name"],
    #         "--scheme", "Ed25519",
    #         "--type", "gran",
    #         "--suri", grandpa["secret_phrase"]
    #     ])

    #     node_data.append({
    #         "peer_id": peer_id,
    #         "aura_pub": aura["public_key"],
    #         "grandpa_pub": grandpa["public_key"],
    #         "ss58_address": aura["ss58_address"],
    #         "p2p_port": node["p2p_port"]
    #     })

    # # Generate initial chainspec
    # print("Generating chainspec...")
    # run_command([
    #     "SUBSTRATE", "build-spec",
    #     "--chain", "local",
    #     "--disable-default-bootnode"
    # ], stdout=open("chainspec.json", "w"))

    # # Modify chainspec
    # with open("chainspec.json", "r") as f:
    #     chainspec = json.load(f)

    # # Set authorities
    # chainspec["genesis"]["runtime"]["aura"]["authorities"] = [n["aura_pub"] for n in node_data]
    # chainspec["genesis"]["runtime"]["grandpa"]["authorities"] = [[n["grandpa_pub"], 1] for n in node_data]
    # chainspec["genesis"]["runtime"]["sudo"]["key"] = node_data[0]["ss58_address"]

    # # Set bootnodes
    # chainspec["bootNodes"] = [
    #     f"/ip4/127.0.0.1/tcp/{n['p2p_port']}/p2p/{n['peer_id']}" for n in node_data
    # ]

    # with open("chainspec.json", "w") as f:
    #     json.dump(chainspec, f, indent=2)

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
    chainspec = None
    if "--chainspec" in sys.argv:
        try:
            chainspec_index = sys.argv.index("--chainspec")
            chainspec = sys.argv[chainspec_index + 1]
        except IndexError:
            raise Exception("Missing path after --chainspec argument")
    main(chainspec)
