# Changelog

### v2.2.1
- Handle null tokenDecimals when used with non-null balances
- Add support for balances using either hex or ss58 addresses
- Add support for injecting ss58 chainId (number) into chainspec. Not to be confused with chain-id which is a string value for chain directory.

## v2.0.0

### 🚀 **Major Features**
- **5 Comprehensive Consensus Options**: We now support upto 5 network consensus configurations!
  - **PoA (Basic)**: AURA + GRANDPA for simple development networks
  - **PoA + ValidatorSet + Sessions**: AURA + GRANDPA with substrate-validator-set (dynamic aura authorities) pallet
  - **BABE + GRANDPA**: Production-ready consensus (Polkadot-style)
  - **BABE + GRANDPA + Sessions + Staking**: Standard Polkadot production setup with staking and sessions pallet
  - **Development Mode**: Single node with instant finality for rapid development

- **Interactive Consensus Selection**: Rich, colorful CLI interface with detailed descriptions
- **Flexible Keystore Management**: Intelligent key insertion based on selected consensus mechanism
- **Smart Substrate Detection**: Automatically switches to interactive mode if substrate binary not found in cwd
- **Modular Chainspec Handlers**: Separate functions for each consensus type
- **Enhanced Session Management**: Proper session key configuration for all consensus types

---

## Previous Versions

### v1.1.2
- Fixed start_network(). Wasn't being passed the correct chainspec file.

### v1.1.1
- Fixed account key type matching bug (do not use v1.1.0)