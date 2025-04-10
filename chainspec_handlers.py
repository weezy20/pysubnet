import json


def edit_vs_ss_authorities(chainspec, NODES):
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
    with open(chainspec, "r") as f:
        data = json.load(f)
    genesis = data["genesis"]["runtimeGenesis"]["patch"]
    session = genesis["session"]
    validatorSet = genesis["validatorSet"]
    # Remove existing keys
    session["keys"] = []
    validatorSet["initialValidators"] = []
    # Insert keys into pallet-sessions
    for node in NODES:
        entry_sessions = [
            node["validator-accountid20-public-key"],
            node["validator-accountid20-public-key"],
            {"aura": node["aura-ss58"], "grandpa": node["grandpa-ss58"]},
        ]
        session["keys"].append(entry_sessions)
        entry_validatorSet = node["validator-accountid20-public-key"]
        validatorSet["initialValidators"].append(entry_validatorSet)

    # Write the modified data back to the original file
    with open(chainspec, "w") as f:
        json.dump(data, f, indent=2)
