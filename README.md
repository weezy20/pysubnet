
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

## 🚀 Usage

### ✅ Pre-requisites

- A compiled **Substrate binary**. Default name expected is `substrate`, but you can pass a custom path using the `--bin` flag.
- A **chainspec**, or use the default `"dev"` or `"local"` ones to bootstrap.

---

### 📦 Basic Command

```sh
python main.py
```

This uses the default settings:
- Chainspec: `"dev"`
- Root directory: `./network`
- Substrate binary: `./substrate`

---

### 🧹 Clean Start

By default, PySubnet **won’t overwrite an existing root directory** if it has contents. To clear it before launching:

```sh
python main.py --clean 
or 
python main.py -c 
```

---

### 📁 Custom Root Directory

```sh
python main.py --root ./my_custom_dir
```

All generated keys, node information, and chain specs will be stored under this directory, and a `pysubnet.json` file will be generated that holds all keys, ports, flags required to run your network:
```
<ROOT_DIR>/pysubnet.json
```

---

### 📜 Custom Chainspec

Pass in your own chainspec file:

```sh
python main.py --chainspec ./my_chainspec.json
```

Or use the default embedded options:
```sh
python main.py --chainspec dev
```
or
```sh
python main.py --chainspec local
```

---

### 🧑‍💻 Interactive Mode

If you want to manually control the node setup flow (e.g., decide how many nodes to generate, or tweak the keys):

```sh
python main.py -i
```
or
```sh
python main.py --interactive
```

---

### 🔌 Run a Local Network

After generating keys and chainspecs, you can launch the network:

```sh
python main.py --run
```
or
```sh
python main.py -r
```

This will:
- Spawn each node in a separate process.
- Use the generated keystores and updated chainspec.
- Write logs to <node-name>.log located inside each node's directory.

Or generate keys, insert keys, and launch the network in one step:
```sh
python main.py -ir -c # interactive
or 
python main.py -i -c # non-interactive
```
It's helpful to use `-c` as often you'll be using the same `<ROOT_DIR>`

---

### 🛠️ Custom Substrate Binary

If your Substrate node binary isn't named `substrate`, pass in the path like so:

```sh
python main.py --bin ./target/release/my-custom-node
```

---

## 🧾 Full Argument Reference

| Flag | Description | Example |
|------|-------------|---------|
| `-i`, `--interactive` | Run in interactive mode | `python main.py -i` |
| `--run`, `--start`, `-r` | Launch network after key/chainspec generation | `python main.py --run` |
| `--root` | Set custom root directory for network artifacts | `python main.py --root ./my-net` |
| `-c`, `--clean` | Clean the root directory before starting | `python main.py -c` |
| `--chainspec` | Provide a chainspec file to use as a starter template or use `dev` / `local` | `--chainspec dev` or `--chainspec ./custom.json` |
| `--bin` | Path to Substrate binary | `--bin ./target/release/node-template` |

---

## 🧠 Notes

- All node data (crypto keys, Account keys, libp2p keys, node IDs) is stored in `pysubnet.json`.
- The script auto-generates keystores compatible with Substrate’s expected format.
- You can choose between `AccountId20` or `AccountId32` for your AccountId (validator account keys)
- Chainspecs are automatically modified in-place with new authority and bootnodes + libp2p identity. All editors are defined in [chainspec_handlers.py](./chainspec_handlers.py) and inserted before `start_network()` call.
- Do not pass `-r` if you just want to prepare base-paths for a multi-node network.
- Sometimes CTRL-C might give you an error. This is because we use a sleep timer for 2 seconds in `main.py` to reduce CPU interuppts. This is easily fixed by tapping CTRL-C in succession.

---
