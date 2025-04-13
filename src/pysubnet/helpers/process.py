import subprocess


def run_command(command, cwd=None):
    """
    Runs a command in a given directory
    """
    result = subprocess.run(command, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        raise Exception(f"Command failed: {' '.join(command)}\n{result.stderr}")
    return result


def parse_subkey_output(output):
    """Parses subkey output"""
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
