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
        if includeNodeBalances:
            # Check if node has a balance defined
            if node.get("balance") is not None:
                amount = node["balance"]
        entry = [
            node[vkey],
            amount * unit,
        ]
        balances.append(entry)
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
