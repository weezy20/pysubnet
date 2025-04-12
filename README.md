
---

# PySubnet

## 🔧 Description

**PySubnet** automates the process generating, inserting and updating chainspecs for multi-node setups. Like:

- Generating **Aura** and **Grandpa** keys (or any other keys that you wish to use as session keys).
- Inserting them into the **keystore** for each node's `--base-path`
- Generating **libp2p** node keys to use for running the node using `--node-key-file`.
- Updating the **chainspec** with all relevant key and network information.
- Extending chainspec edit process using custom chainspec_handlers defined in [chainspec_handlers.py](./chainspec_handlers.py) file

Currently, it supports **Aura + Grandpa** based Substrate chains. You can adapt the logic to support different key types as needed.

It also supports key generations for AccountIds using built-in subkey in the substrate binary provided or using ECDSA keys generated using the [ethereum](./ethereum.py) module.

---

## 📦 Installation

### 🔌 Using `pip`:

```sh
pip install pysubnet
```

### Using `uv` by astral.sh:
```sh
uvx git+https://github.com/weezy20/pysubnet.git
```

> **Note:** If you're on a system without Python development headers (like `Python.h`), and see errors during install:
>
> - On **Debian/Ubuntu**, run: `sudo apt install python3-dev`
> - On **RedHat/Fedora**, run: `sudo dnf install python3-devel`
> - On **Mac**, make sure Xcode Command Line Tools are installed: `xcode-select --install`

You can also install directly from GitHub (for the latest version):

```sh
pip install git+https://github.com/weezy20/pysubnet.git
```

---

## 🚀 Usage

### ✅ Pre-requisites

- A compiled **Substrate binary**. Default name expected is `substrate`, but you can pass a custom path using the `--bin` flag.
- A **chainspec**, or use the default `"dev"` or `"local"` ones to bootstrap.

---

### 📦 Basic Command

```sh
pysubnet
```

This uses the default settings:
- Chainspec: `"dev"`
- Root directory: `./network`
- Substrate binary: `./substrate`

---

### 🧹 Clean Start

By default, PySubnet **won’t overwrite an existing root directory** if it has contents. To clear it before launching:

```sh
pysubnet --clean 
or 
pysubnet -c 
```

---

### 📁 Custom Root Directory

```sh
pysubnet --root ./my_custom_dir
```

All generated keys, node information, and chain specs will be stored under this directory, and a `pysubnet.json` file will be generated that holds all keys, ports, flags required to run your network:
```
<ROOT_DIR>/pysubnet.json
```

---

### 📜 Custom Chainspec

Pass in your own chainspec file:

```sh
pysubnet --chainspec ./my_chainspec.json
```

Or use the default embedded options:
```sh
pysubnet --chainspec dev
```
or
```sh
pysubnet --chainspec local
```

---

### 🧑‍💻 Interactive Mode

If you want to manually control the node setup flow (e.g., decide how many nodes to generate, or tweak the keys):

```sh
pysubnet -i
```
or
```sh
pysubnet --interactive
```

---

### 🔌 Run a Local Network

After generating keys and chainspecs, you can launch the network:

```sh
pysubnet --run
```
or
```sh
pysubnet -r
```

This will:
- Spawn each node in a separate process.
- Use the generated keystores and updated chainspec.
- Write logs to <node-name>.log located inside each node's directory.

Or generate keys, insert keys, and launch the network in one step:
```sh
pysubnet -ir -c # interactive
or 
pysubnet -i -c # non-interactive
```
It's helpful to use `-c` as often you'll be using the same `<ROOT_DIR>`

---

### 🛠️ Custom Substrate Binary

If your Substrate node binary isn't named `substrate`, pass in the path like so:

```sh
pysubnet --bin ./target/release/my-custom-node
```

---

### 🧑‍⚖️ Enable Proof-of-Authority (PoA) Mode

For Substrate-node-template based chains (Simple Aura+Grandpa session keys), you can enable Proof-of-Authority (PoA) mode, which assigns all authorities equal weight in the chainspec and inserts their Aura-SS58 & Grandpa-SS58 keys. This is useful for testing and development purposes when starting out learning substrate. Also works for `frontier/template`
as it's same in consensus to the default `substrate-node-template`

```sh
pysubnet --poa -r 
# Automates the tutorial "Start a private network with 3 nodes" that used to be in the now gone substrate.io website
```

---

## 🧾 Full Argument Reference

| Flag | Description | Example |
|------|-------------|---------|
| `-i`, `--interactive` | Run in interactive mode | `pysubnet -i` |
| `--run`, `--start`, `-r` | Launch network after key/chainspec generation | `pysubnet --run` |
| `--root` | Set custom root directory for network artifacts | `pysubnet --root ./my-net` |
| `-c`, `--clean` | Clean the root directory before starting | `pysubnet -c` |
| `--chainspec` | Provide a chainspec file to use as a starter template or use `dev` / `local` | `--chainspec dev` or `--chainspec ./custom.json` |
| `--bin` | Path to Substrate binary | `--bin ./target/release/node-template` |
| `--account` | AccountId type to use for ValidatorId, "ecdsa" or "sr25519" | `--account ecdsa` or `--account sr25519"` |
| `--poa` | Enable POA. Absence of this flag branches code into `custom_network_config` which is user defined | `pysubnet --poa --run` |

---

## 🧠 Notes

- All node data (crypto keys, Account keys, libp2p keys, node IDs) is stored in `pysubnet.json`.
- The script auto-generates keystores compatible with Substrate’s expected format.
- You can choose between `AccountId20` or `AccountId32` for your AccountId (validator account keys)
- Chainspecs are automatically modified in-place with new authority and bootnodes + libp2p identity. All editors are defined in [chainspec_handlers.py](./chainspec_handlers.py) and inserted before `start_network()` call.
- Do not pass `-r` if you just want to prepare base-paths for a multi-node network.
- Sometimes CTRL-C might give you an error. This is because we use a sleep timer for 2 seconds in `main.py` to reduce CPU interuppts. This is easily fixed by tapping CTRL-C in succession.

---
