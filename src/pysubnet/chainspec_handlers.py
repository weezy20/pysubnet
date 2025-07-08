"""
Definitions for handling chainspec files.
Define your chainspec editors here.
Use `load_chainspec` & `write_chainspec` for loading and writing chainspec files.
Your editor looks like : <load_chainspec><your edits><write_chainspec>
Then include your handler in the main script before `start_network()` is called
"""

import json

from .accounts import AccountKeyType
from .cli import CliConfig


def load_chainspec(chainspec: str):
    """
    Load chainspec from a JSON file.
    Chainspec is expected to be an os.path at this stage
    """
    with open(chainspec, "r") as f:
        data = json.load(f)
    return data


def write_chainspec(chainspec: str, data):
    """
    Write chainspec to a JSON file.
    """
    with open(chainspec, "w") as f:
        json.dump(data, f, indent=2)


def edit_vs_ss_authorities(
    chainspec: str, NODES: list[dict], account_key_type: AccountKeyType
):
    """
    NOTE: This will overwrite `chainspec` passed in as argument.
    A handler to edit a chainspec with the substrate-validator-set pallet + pallet-sessions
    This will insert the necessary keys into the genesis config of pallet-sessions and substrate-validator-set pallet

    For example, this is how pallet-sessions key would look like:
    "session": {
              "keys": [
                [
                  "0xe04cc55ebee1cbce552f250e85c57b70b2e2625b",
                  "0xe04cc55ebee1cbce552f250e85c57b70b2e2625b",
                  {
                    "aura": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
                    "grandpa": "5FA9nQDVg267DEd8m1ZypXLBnvN7SFxYwV7ndqSYGiN9TTpu"
                  }
                ], ../
            }
    And this is how validator-set-pallet genesis looks:

    "validatorSet": {
              "initialValidators": [
                "0xe04cc55ebee1cbce552f250e85c57b70b2e2625b",
                "0x25451a4de12dccc2d166922fa938e900fcc4ed24"
              ]
            }
    """
    data = load_chainspec(chainspec)
    genesis = data["genesis"]["runtimeGenesis"]["patch"]
    session = genesis["session"]
    validatorSet = genesis["validatorSet"]
    # Remove existing keys
    session["keys"] = []
    validatorSet["initialValidators"] = []
    vkey = account_key_type.get_vkey()
    # Insert keys into pallet-sessions
    for node in NODES:
        # Make entry for pallet-sessions
        entry_sessions = [
            node[vkey],
            node[vkey],
            {"aura": node["aura-ss58"], "grandpa": node["grandpa-ss58"]},
        ]
        session["keys"].append(entry_sessions)
        # Make entry for substrate-validator-set pallet
        entry_validatorSet = node[vkey]
        validatorSet["initialValidators"].append(entry_validatorSet)

    # Write the modified data back to the original file
    write_chainspec(chainspec, data)


def inject_validator_balances(
    data,  # In memory chainspec data
    NODES: list[dict],
    account_key_type: AccountKeyType,
    removeExisting=False,
    tokenDecimals=18,
    amount=500,
    # Includes balances defined in nodes themselves which are populated as part of --config <file>
    includeNodeBalances=False,
):
    """
    Modify the balances pallet in the chainspec for validator accounts.

    Parameters:
    - removeExisting (bool): If True, clears all existing balances. Defaults to False.
    - amount (int): The number of tokens to allocate to each account.
      This value is multiplied by tokenDecimals properties.
      Defaults to 500 tokens w/ 18 decimal places if not defined in template chainspec.
    - includeNodeBalances (bool): If True, includes balances defined in the nodes themselves.
      This is specified using the `balance` key in the node dictionary of the config file.
    By default, existing balances are retained, and the specified amount is added for each node.
    """
    balances = data["genesis"]["runtimeGenesis"]["patch"]["balances"]["balances"]

    unit = 10**tokenDecimals
    vkey = account_key_type.get_vkey()

    # print(balances, type(balances))
    if removeExisting:
        balances = []
    # Add initial balances for each node
    for node in NODES:
        current_amount = amount
        if includeNodeBalances:
            # Check if node has a balance defined
            if node.get("balance") is not None:
                current_amount = node["balance"]
        final_balance = current_amount * unit
        entry = [
            node[vkey],
            final_balance,
        ]
        balances.append(entry)
        print(f"✅ {node[vkey]} --> {current_amount} tokens ({final_balance:,} units)")
    data["genesis"]["runtimeGenesis"]["patch"]["balances"]["balances"] = balances


def enable_poa(chainspec: str, config: CliConfig):
    """
    Inject AURA and GRANDPA authorities into the chainspec.
    Additionally apply customizations from the config file if customizations are enabled.
    """
    data = load_chainspec(chainspec)
    try:
        # Add PoA specific configurations
        aura_authorities = []
        gran_authorities = []
        for node in config.nodes:
            entry_aura = node["aura-ss58"]
            aura_authorities.append(entry_aura)
            entry_grandpa = [node["grandpa-ss58"], 1]
            gran_authorities.append(entry_grandpa)

        data["genesis"]["runtimeGenesis"]["patch"]["aura"]["authorities"] = (
            aura_authorities
        )
        data["genesis"]["runtimeGenesis"]["patch"]["grandpa"]["authorities"] = (
            gran_authorities
        )
        apply_config_customizations(data, config)
    except KeyError as e:
        print(
            f"KeyError: {e}. Please ensure the node and chainspec has the correct structure for PoA."
        )
        return
    # Write the modified data back to the original file
    write_chainspec(chainspec, data)


def enable_poa_with_validator_set(chainspec: str, config: CliConfig):
    """
    Enhanced PoA configuration that includes AURA + GRANDPA authorities
    plus ValidatorSet and Sessions configuration.
    This ensures compatibility with substrate-validator-set and session pallets.
    """
    # First, apply the validator set and sessions configuration
    edit_vs_ss_authorities(chainspec, config.nodes, config.account_key_type)

    # Load the chainspec to add AURA and GRANDPA authorities
    data = load_chainspec(chainspec)

    try:
        # Add AURA and GRANDPA authorities (essential for consensus)
        aura_authorities = []
        gran_authorities = []

        for node in config.nodes:
            entry_aura = node["aura-ss58"]
            aura_authorities.append(entry_aura)
            entry_grandpa = [node["grandpa-ss58"], 1]
            gran_authorities.append(entry_grandpa)

        # Ensure AURA and GRANDPA authorities are set
        data["genesis"]["runtimeGenesis"]["patch"]["aura"]["authorities"] = aura_authorities
        data["genesis"]["runtimeGenesis"]["patch"]["grandpa"]["authorities"] = gran_authorities

        # Check if tokenDecimals is defined, if not use 18 decimals as default
        tokenDecimals = data["properties"].get("tokenDecimals", 18)

        # Set validator balances
        inject_validator_balances(
            data,
            config.nodes,
            config.account_key_type,
            removeExisting=True,  # Remove existing balances
            amount=5234,  # Balance amount
            tokenDecimals=tokenDecimals,
        )

        # Apply any config customizations
        apply_config_customizations(data, config)

    except KeyError as e:
        print(
            f"KeyError: {e}. Please ensure the chainspec has the correct structure for PoA with ValidatorSet."
        )
        return

    # Write the modified data back to the original file
    write_chainspec(chainspec, data)


def custom_network_config(chainspec: str, config: CliConfig):
    """
    Modify the chainspec for custom network configuration.
    Use this function to write one for your own chain.
    """
    edit_vs_ss_authorities(
        chainspec, config.nodes, config.account_key_type
    )  # Custom handler for a particular chain using substrate-validator-set and pallet-session
    data = load_chainspec(chainspec)
    # Check if tokenDecimals is defined, if not use 18 decimals as default
    tokenDecimals = data["properties"].get("tokenDecimals", 18)
    inject_validator_balances(
        data,
        config.nodes,
        config.account_key_type,
        removeExisting=True,  # Remove Existing balances
        amount=5234,  # Balance
        tokenDecimals=tokenDecimals,
    )  # Custom handler for setting balances genesis
    apply_config_customizations(data, config)
    write_chainspec(chainspec, data)


def apply_config_customizations(data, config: CliConfig):
    if not config.apply_chainspec_customizations:
        return
    fetched_tokenSymbol = data["properties"].get("tokenSymbol", None)
    fetched_tokenDecimals = data["properties"].get("tokenDecimals", None)
    network = config.network
    if network is not None:
        # config file customizations are selected thus we use them
        tokenDecimals = network.token_decimal or fetched_tokenSymbol
        tokenSymbol = network.token_symbol or fetched_tokenDecimals
        data["properties"]["tokenDecimals"] = (
            tokenDecimals or 18
        )  # Neither defined in chainspec or config -- unlikely but we cover it
        data["properties"]["tokenSymbol"] = tokenSymbol or "DOT"  # same as above
        inject_validator_balances(
            data,
            config.nodes,
            config.account_key_type,
            removeExisting=network.remove_existing_balances,
            tokenDecimals=tokenDecimals,
            includeNodeBalances=True,
        )
        # Inject custom balances from config file
        inject_config_balances(data, config)


def enable_babe_grandpa(chainspec: str, config: CliConfig):
    """
    Inject BABE and GRANDPA authorities into the chainspec for production consensus.
    BABE (Blind Assignment for Blockchain Extension) is more suitable for larger validator sets.
    """
    data = load_chainspec(chainspec)
    try:
        # Add BABE specific configurations
        babe_authorities = []
        gran_authorities = []

        for node in config.nodes:
            # BABE authorities use the BABE keys
            entry_babe = [node["babe-ss58"], 1]  # [authority_id, weight]
            babe_authorities.append(entry_babe)

            # GRANDPA authorities remain the same
            entry_grandpa = [node["grandpa-ss58"], 1]
            gran_authorities.append(entry_grandpa)

        data["genesis"]["runtimeGenesis"]["patch"]["babe"]["authorities"] = babe_authorities
        data["genesis"]["runtimeGenesis"]["patch"]["grandpa"]["authorities"] = gran_authorities

        # BABE specific configuration - set epoch duration (in blocks)
        if "epochDuration" not in data["genesis"]["runtimeGenesis"]["patch"]["babe"]:
            data["genesis"]["runtimeGenesis"]["patch"]["babe"]["epochDuration"] = 2400  # ~4 hours with 6s blocks
        
        # BABE epoch configuration - required for proper BABE consensus
        if "epochConfig" not in data["genesis"]["runtimeGenesis"]["patch"]["babe"]:
            data["genesis"]["runtimeGenesis"]["patch"]["babe"]["epochConfig"] = {
                "allowed_slots": "PrimaryAndSecondaryPlainSlots",
                "c": [1, 4]
            }

        apply_config_customizations(data, config)

    except KeyError as e:
        print(
            f"KeyError: {e}. Please ensure the chainspec has the correct structure for BABE + GRANDPA."
        )
        return

    # Write the modified data back to the original file
    write_chainspec(chainspec, data)


def enable_babe_grandpa_with_staking(chainspec: str, config: CliConfig):
    """
    BABE + GRANDPA configuration with staking pallet and sessions.
    This is the standard Substrate production setup used in polkadot-sdk.
    Uses the staking pallet instead of substrate-validator-set for validator management.
    """
    data = load_chainspec(chainspec)
    
    try:
        # Add BABE and GRANDPA authorities (essential for consensus)
        babe_authorities = []
        gran_authorities = []
        
        for node in config.nodes:
            entry_babe = [node["babe-ss58"], 1]  # [authority_id, weight]
            babe_authorities.append(entry_babe)
            entry_grandpa = [node["grandpa-ss58"], 1]
            gran_authorities.append(entry_grandpa)

        # Set BABE and GRANDPA authorities
        data["genesis"]["runtimeGenesis"]["patch"]["babe"]["authorities"] = babe_authorities
        data["genesis"]["runtimeGenesis"]["patch"]["grandpa"]["authorities"] = gran_authorities
        
        # BABE specific configuration
        if "epochDuration" not in data["genesis"]["runtimeGenesis"]["patch"]["babe"]:
            data["genesis"]["runtimeGenesis"]["patch"]["babe"]["epochDuration"] = 2400
        
        # BABE epoch configuration - required for proper BABE consensus
        if "epochConfig" not in data["genesis"]["runtimeGenesis"]["patch"]["babe"]:
            data["genesis"]["runtimeGenesis"]["patch"]["babe"]["epochConfig"] = {
                "allowed_slots": "PrimaryAndSecondaryPlainSlots",
                "c": [1, 4]
            }
        
        # Configure sessions with BABE keys
        configure_sessions_for_staking(data, config.nodes, config.account_key_type)
        
        # Configure staking pallet
        configure_staking_genesis(data, config.nodes, config.account_key_type)
        
        # Check if tokenDecimals is defined, if not use 18 decimals as default
        tokenDecimals = data["properties"].get("tokenDecimals", 18)
        
        # Set validator balances (they need enough tokens to stake)
        inject_validator_balances(
            data,
            config.nodes,
            config.account_key_type,
            removeExisting=True,
            amount=100000,  # Higher amount for staking (100k tokens)
            tokenDecimals=tokenDecimals,
        )
        
        apply_config_customizations(data, config)
        
    except KeyError as e:
        print(
            f"KeyError: {e}. Please ensure the chainspec has the correct structure for BABE + GRANDPA + Staking."
        )
        return
    
    # Write the modified data back to the original file
    write_chainspec(chainspec, data)


def configure_sessions_for_staking(data, NODES: list[dict], account_key_type: AccountKeyType):
    """
    Configure sessions pallet for staking-based validator management.
    Sets up session keys with BABE instead of AURA.
    """
    genesis = data["genesis"]["runtimeGenesis"]["patch"]
    if "session" not in genesis:
        genesis["session"] = {}
    
    session = genesis["session"]
    session["keys"] = []
    vkey = account_key_type.get_vkey()
    
    # Insert session keys with BABE
    for node in NODES:
        entry_sessions = [
            node[vkey],  # validator account
            node[vkey],  # session account (can be the same)
            {"babe": node["babe-ss58"], "grandpa": node["grandpa-ss58"]},
        ]
        session["keys"].append(entry_sessions)


def configure_staking_genesis(data, NODES: list[dict], account_key_type: AccountKeyType):
    """
    Configure staking pallet genesis with initial validators and their stakes.
    This is the standard setup for production Substrate networks.
    """
    genesis = data["genesis"]["runtimeGenesis"]["patch"]
    if "staking" not in genesis:
        genesis["staking"] = {}
    
    staking = genesis["staking"]
    vkey = account_key_type.get_vkey()
    
    # Set staking configuration
    stake_amount = 10000 * (10 ** 18)  # 10k tokens with 18 decimals
    
    # Initialize validators and nominators
    staking["validatorCount"] = len(NODES)
    staking["minimumValidatorCount"] = max(1, len(NODES) // 2)  # At least half need to be online
    staking["invulnerables"] = []  # No invulnerable validators initially
    staking["forceEra"] = "NotForcing"
    staking["slashRewardFraction"] = 1000000000  # 10% in perbill (10^9 = 100%)
    staking["canceledSlashPayout"] = 1000000000  # 10% in perbill
    staking["historyDepth"] = 336  # ~1.4 days with 6s blocks (84 eras)
    
    # Set up initial validators with their stakes
    staking["stakers"] = []
    for node in NODES:
        validator_entry = [
            node[vkey],  # validator account
            node[vkey],  # controller account (same as validator for simplicity)
            stake_amount,  # stake amount
            "Validator"   # staker type
        ]
        staking["stakers"].append(validator_entry)


def edit_babe_vs_ss_authorities(
    chainspec: str, NODES: list[dict], account_key_type: AccountKeyType
):
    """
    Handler to edit a chainspec with BABE + substrate-validator-set pallet + pallet-sessions.
    Similar to edit_vs_ss_authorities but uses BABE instead of AURA for session keys.
    """
    data = load_chainspec(chainspec)
    genesis = data["genesis"]["runtimeGenesis"]["patch"]
    session = genesis["session"]
    validatorSet = genesis["validatorSet"]

    # Remove existing keys
    session["keys"] = []
    validatorSet["initialValidators"] = []
    vkey = account_key_type.get_vkey()

    # Insert keys into pallet-sessions with BABE
    for node in NODES:
        # Make entry for pallet-sessions with BABE instead of AURA
        entry_sessions = [
            node[vkey],
            node[vkey],
            {"babe": node["babe-ss58"], "grandpa": node["grandpa-ss58"]},
        ]
        session["keys"].append(entry_sessions)

        # Make entry for substrate-validator-set pallet
        entry_validatorSet = node[vkey]
        validatorSet["initialValidators"].append(entry_validatorSet)

    # Write the modified data back to the original file
    write_chainspec(chainspec, data)


def enable_dev_mode(chainspec: str, config: CliConfig):
    """
    Configure chainspec for development mode with instant finality.
    Uses only the first node as a single authority.
    """
    data = load_chainspec(chainspec)

    try:
        # Use only the first node for development
        first_node = config.nodes[0]

        # Set single authority for both AURA and GRANDPA
        data["genesis"]["runtimeGenesis"]["patch"]["aura"]["authorities"] = [
            first_node["aura-ss58"]
        ]
        data["genesis"]["runtimeGenesis"]["patch"]["grandpa"]["authorities"] = [
            [first_node["grandpa-ss58"], 1]
        ]

        # Set development mode specific configurations
        if "properties" not in data:
            data["properties"] = {}
        data["properties"]["isEthereum"] = False

        # Apply config customizations
        apply_config_customizations(data, config)

    except (KeyError, IndexError) as e:
        print(
            f"Error: {e}. Please ensure at least one node is configured for development mode."
        )
        return

    # Write the modified data back to the original file
    write_chainspec(chainspec, data)


def inject_config_balances(data, config: CliConfig):
    """
    Inject custom balances from config file into the chainspec.
    Supports both hex (ECDSA) and SS58 (SR25519) address formats.
    Validates addresses and provides warnings for invalid ones.
    """
    if not config.network or not config.network.balances:
        return

    balance_config = config.network.balances
    balances = data["genesis"]["runtimeGenesis"]["patch"]["balances"]["balances"]
    tokenDecimals = data["properties"].get("tokenDecimals", 18)
    unit = 10 ** tokenDecimals

    # Print colored warnings
    def print_warning(message):
        print(f"\033[93m⚠️  Warning: {message}\033[0m")

    # Process hex addresses (ECDSA)
    if balance_config.hex:
        normalized_hex = balance_config.normalize_hex_addresses()
        
        for address, balance_amount in normalized_hex.items():
            if not balance_config.validate_hex_address(address):
                print_warning(f"Invalid hex address format: {address}. Skipping.")
                continue
            
            # Check if address is compatible with account type
            if config.account_key_type != AccountKeyType.AccountId20:
                print_warning(f"Hex address {address} provided but account type is {config.account_key_type.value}. Address may not be compatible.")
            
            # Convert hex to lowercase for consistency
            final_address = address.lower()
            final_balance = balance_amount * unit
            
            # Add to balances
            entry = [final_address, final_balance]
            balances.append(entry)
            print(f"✅ {final_address} --> {balance_amount} tokens ({final_balance:,} units)")

    # Process SS58 addresses (SR25519)
    if balance_config.ss58:
        for address, balance_amount in balance_config.ss58.items():
            if not balance_config.validate_ss58_address(address):
                print_warning(f"Invalid SS58 address format: {address}. Skipping.")
                continue
            
            # Check if address is compatible with account type
            if config.account_key_type != AccountKeyType.AccountId32:
                print_warning(f"SS58 address {address} provided but account type is {config.account_key_type.value}. Address may not be compatible.")
            
            final_balance = balance_amount * unit
            
            # Add to balances - SS58 addresses can be used directly
            entry = [address, final_balance]
            balances.append(entry)
            print(f"✅ {address} --> {balance_amount} tokens ({final_balance:,} units)")

    # Update the balances in the data
    data["genesis"]["runtimeGenesis"]["patch"]["balances"]["balances"] = balances
