
---

# PySubnet 
### Quick & easy mutli-node substrate network setup

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
pip install pysubnet # (Coming soon)
```
Or get the latest version from github:

```sh
pip install git+https://github.com/weezy20/pysubnet.git
```
Or run it without installing anything using `pipx` or `uvx`:
### ⚡ Using `uv` by [astral.sh](https://docs.astral.sh/uv/) (recommended):
```sh
uvx git+https://github.com/weezy20/pysubnet.git
```

Or create a virutalenv with `python >=3.10` and install it inside it using pip, uv, etc.

```sh
# Create virtualenv with python >=3.10
python -m venv venv
source venv/bin/activate 
# or if using uv
uv venv test
source test/.venv/bin/activate
# Windows: `venv\Scripts\activate`
```
Then install it
```sh
pip install git+https://github.com/weezy20/pysubnet.git
# or if using uv
uv pip install git+https://github.com/weezy20/pysubnet.git
```

> **Note:** If you're on a system without Python development headers (like `Python.h`), and see missing header errors during install you would need to install them:
>
> - On **Debian/Ubuntu**, run: `sudo apt install python3-dev`
> - On **RedHat/Fedora**, run: `sudo dnf install python3-devel`
> - On **Mac**, make sure Xcode Command Line Tools are installed: `xcode-select --install`

---

## 🚀 Usage

### ✅ Pre-requisites
- **Substrate Binary** (required):  
    A compiled Substrate binary. By default, pysubnet looks for a binary named `substrate`. If your binary has a different name or is located elsewhere, you can specify its path using the `--bin` flag.

- **Chainspec File** (optional):  
    A `chainspec.json` file can be provided as a base template for your network configuration.

---

### 📦 Basic Command

```sh
pysubnet
```
or 
```sh
pysubnet -i # Recommended
```

This uses the default settings:
- Chainspec: `"dev"`
- Root directory: `./network`
- Substrate binary: `./substrate`

You can use all flags with `-i`. The main reason for having flags is to use in non-interactive setups where developers need quick network startup
A developer might create a substrate node with their custom chainspec edits in the `custom_network_config()` function in [chainspec_handlers.py](./src/pysubnet/chainspec_handlers.py) file and then may run 

```sh
pysubnet -c # (clean existing root-dir if present) 
         -r # (invoke start_network())
         --bin <custom bin> # (provide a custom bin)
``` 
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
pysubnet --chainspec dev # default option equivalent to running without --chainspec flag

```
or
```sh
pysubnet --chainspec local
```
`PySubnet` will inject generated bootnodes into the chainspec, and based on one of `custom_network_config()` [Default] or `enable_poa()`[`--poa`] will inject authorities to the genesis. It will then generate a raw_chainspec file and use that to spawn of  the network in `start_network()`

---

`-r` or `--run` will invoke `start_network()` to start the network. This will:

- Spawn each node in a separate process.
- Use the generated keystores and updated chainspec.
- Write logs to `<node-name>.log` located inside each node's directory.

Generate keys, insert keys, update chainspec, generate raw chainspec and launch the network in one step:
```sh
pysubnet -icr # interactive
or 
pysubnet -cr # non-interactive
```
It's helpful to use `-c` as often you'll be using the same `<ROOT_DIR>`

---

### 🧑‍⚖️ Enable Proof-of-Authority (PoA) Mode

For Substrate-node-template based chains (Simple Aura+Grandpa session keys), you can enable Proof-of-Authority (PoA) mode, which assigns all authorities equal weight in the chainspec and inserts their Aura-SS58 & Grandpa-SS58 keys. This is useful for testing and development purposes when starting out learning substrate. Also works for `frontier/template` or any node that has a "aura" and "grandpa" in their runtime-genesis["patch"] section.
]
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
- Make sure your node uses the same account type as the `--account` you pass to pysubnet. Not doing so will result in a runtime error
- Chainspecs are automatically modified in-place with new authority and bootnodes + libp2p identity. All editors are defined in [chainspec_handlers.py](./src/pysubnet/chainspec_handlers.py) and inserted before `start_network()` call.
- Do not pass `-r` if you just want to prepare base-paths for a multi-node network.
- Sometimes CTRL-C might give you an error. This is because we use a sleep timer for 2 seconds in `main.py` to reduce CPU interuppts. This is easily fixed by tapping CTRL-C in succession.

---
