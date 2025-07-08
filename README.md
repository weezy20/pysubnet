
# PySubnet

[![PyPI version](https://badge.fury.io/py/pysubnet.svg)](https://badge.fury.io/py/pysubnet) [![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/) [![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-yellow.svg)](https://opensource.org/licenses/Apache-2.0)

### The easiest way to develop deploy test a multi-node substrate network


---

## 🚀 **What is PySubnet?**

PySubnet is a **beginner-friendly tool** that automates the complex process of setting up multi-node Substrate blockchain networks. Whether you're a blockchain developer learning Substrate or deploying production networks, PySubnet handles all the tedious setup work for you.

### ✨ **What PySubnet Does for You:**

- 🔑 **Generates all cryptographic keys** for your validator authorities (AURA, BABE, GRANDPA)
- 📁 **Creates proper directory structure** for your network nodes
- ⚙️ **Prepares a chainspec** with bootnodes and validator keys 
- 🔗 **Sets up p2p keys** (libp2p keys for bootnodes list)
- 💸 **Funds** starting balances for any number of accounts for you without having to manually edit chainspec files. (See example in [nodes.toml](./config-examples/nodes.toml))
- 🏃‍♂️ **Launches your network** with a single command (`-r`)
- 🎨 **Interactive CLI** with beautiful, colorful output (`-i`)

---

## **Crafted For:**

- **Blockchain Developers** learning the Substrate framework with multi-node setups
- **DevOps Teams** for managing multiple sets of keys for separate nodes
- **Rapid Prototyping** of blockchain applications

---

## 📦 **Installation**

### **Option 1: Install with uv pip (Recommended)**
```bash
uv pip install pysubnet
# or install it as a tool
uv tool install pysubnet
```

### **Option 2: Latest from GitHub**
```bash
pip install git+https://github.com/weezy20/pysubnet.git
```

### **Option 3: Run without installing (using uvx)**
```bash
uvx git+https://github.com/weezy20/pysubnet.git
```

> **💡 Tip:** If you get Python header errors during installation:
> - **Ubuntu/Debian**: `sudo apt install python3-dev`
> - **RHEL/Fedora**: `sudo dnf install python3-devel`
> - **macOS**: `xcode-select --install`



### **Step 2: Run PySubnet**
```bash
pysubnet
```
*That's it! PySubnet will automatically start in interactive mode and guide you through the setup.*

### **Step 3: Choose Your Network Type**
PySubnet will present you with **5** commonly used consensus options:

1. **🟢 PoA (Proof-of-Authority)** - Perfect for learning and simple development
2. **🟡 PoA + ValidatorSet** - PoA with sessions pallet and [substrate-validator-pallet](https://github.com/web3gautam/substrate-validator-set) for dynamic authority management
`Note: To use this pallet (substrate-validator-set) it's recommended to clone it locally and add it to your runtime because as of this writing, it's dependecies seem outdated, but its functionality is unaffected` 
3. **🔵 BABE + GRANDPA** - Production-ready consensus (like Polkadot)
4. **🟣 BABE + GRANDPA + Staking** - Full production setup with economic security
5. **🔴 Development Mode** - Single node for rapid development

---

## 🎮 **Interactive Mode Features**

When you run `pysubnet`, it automatically detects if you have a substrate binary and provides:

- 🎨 **Beautiful CLI interface** with colors and progress bars
- 🤖 **Smart substrate detection** - automatically switches to interactive mode if no binary found
- ❓ **Helpful prompts** - clear explanations for each option
- 🔧 **Flexible configuration** - choose exactly what you need
- 📊 **Real-time feedback** - see your network being built step by step

---



## 🔧 **Advanced Usage**

### **Non-Interactive Mode**
```bash
# Quick setup with defaults
pysubnet --clean --run
# Or a shorter version
pysubnet -cr

# Custom binary location
pysubnet --bin ./target/release/my-node --run

# Using Docker
pysubnet --docker substrate:latest --run

# Custom chainspec
pysubnet --chainspec ./my-chainspec.json --run
```

### **Configuration File**
Create advanced network configurations:
```bash
pysubnet --config ./network-config.toml --run
```
See [docs/config.md](docs/config.md) for configuration examples.

### **Directory Structure**
PySubnet creates organized directories:
```
./network/                    # Default root directory
├── pysubnet.json            # Network configuration & keys
├── chainspec.json           # Generated chainspec
├── raw_chainspec.json       # Raw chainspec for nodes
├── alice/                   # Node directories
│   ├── alice-node-private-key
│   └── chains/<chain folder based on running chainspec>/keystore/
├── bob/
└── charlie/
```

---

## 📊 **Complete Flag Reference**

| Flag | Description | Example |
|------|-------------|---------|
| `-i`, `--interactive` | Force interactive mode (default when no substrate binary) | `pysubnet -i` |
| `-r`, `--run` | Launch network after setup | `pysubnet -r` |
| `-c`, `--clean` | Clean existing network directory | `pysubnet -c` |
| `--root` | Custom network directory | `--root ./my-network` |
| `--bin` | Path to substrate binary | `--bin ./substrate` |
| `--docker` | Use Docker image | `--docker substrate:latest` |
| `--chainspec` | Base chainspec (`dev`, `local`, or file path) | `--chainspec dev` |
| `--config` | Network configuration file | `--config ./config.toml` |
| `--account` | Account type (`ecdsa` or `sr25519`) | `--account ecdsa` |
| `--poa` | Force basic PoA mode (bypass interactive selection) | `--poa` |

---

## 🎓 **Learning Resources**

### **New to Substrate?**

The first tutorial on substrate is about running a PoA node with 2 or 3 nodes. You can replicate that entire tutorial with pysubnet by running `pysubnet -icr --poa --bin <your poa enabled node>`.



---

## 🤝 **Getting Help**

- 🐛 **Issues:** [GitHub Issues](https://github.com/weezy20/pysubnet/issues)
- 💬 **Discussions:** [GitHub Discussions](https://github.com/weezy20/pysubnet/discussions)

---

- All node data (crypto keys, Account keys, libp2p keys, node IDs) is stored in `pysubnet.json`.
- The script auto-generates keystores compatible with Substrate’s expected format.
## 💡 **Tips & Best Practices**

- **🧹 Always use `--clean/-c`** when restarting development to avoid issues.
- **📝 Save your pysubnet.json** - After having a proper setup, save this file for your future reference, it contains all your network keys and configuration
---

## 📈 **What's New in v2.0**

- 🎯 **5 Consensus Options** (upgraded from 2)
- 🎨 **Enhanced Interactive Mode** with beautiful CLI
- 🤖 **Smart Binary Detection** with automatic fallback
- 📦 **Modular Architecture** for easier customization

---

*Made with ❤️ for the Substrate community*
