import re
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

def is_valid_public_key(key: str) -> bool:
    """
    Checks if a string matches the format of a Substrate public key
    (0x followed by 64 hexadecimal characters).

    Args:
        key: The key string to validate.

    Returns:
        True if the string is a valid public key format, False otherwise.
    """
    # Regex breakdown:
    # ^      - Matches the start of the string.
    # 0x     - Matches the literal characters "0x".
    # [0-9a-fA-F] - Matches a single hexadecimal character (0-9, a-f, A-F).
    # {64}   - Matches the previous element exactly 64 times.
    # $      - Matches the end of the string.
    pattern = r"^0x[0-9a-fA-F]{64}$"

    # re.fullmatch checks if the entire string matches the pattern
    if re.fullmatch(pattern, key):
        return True
    else:
        return False
