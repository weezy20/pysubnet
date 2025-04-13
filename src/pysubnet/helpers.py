import os
from pathlib import Path
import subprocess

TRIES = 2  # Number extra tries before aborting


def prompt_bool(prompt_text: str, default: bool = None) -> bool:
    """
    Prompts the user with a given text and checks if the response is affirmative or negative.

    Args:
        prompt_text (str): The text to display to the user.

    Returns:
        bool: True if the user responds with 'yes', 'y', or 'yay' (case insensitive),
              False if the user responds with 'no', 'n', or 'nay' (case insensitive).

    Raises:
        ValueError: If the user provides an invalid response.
    """
    valid_yes = {"yes", "y", "yay"}
    valid_no = {"no", "n", "nay"}

    if default is not None:
        match default:
            case True:
                prompt_text += " [default: Yes] "
            case False:
                prompt_text += " [default: No] "

    for i in range(TRIES + 1):
        response = input(prompt_text).strip().lower()
        # False/True is not None, Empty response is False, hence not "" == True
        if not response and default is not None:
            return default
        if response in valid_yes:
            return True
        elif response in valid_no:
            return False
        else:
            if i == TRIES:
                raise ValueError("Invalid response. Aborting.")
            else:
                print(
                    "Invalid response. Please respond with 'yes', 'y', 'yay', 'no', 'n', or 'nay'."
                )
                continue


def prompt_path(prompt_text: str, default: str = None) -> Path:
    """
    Prompts the user with a given text and validates if the response is a valid OS path.

    Args:
        prompt_text (str): The text to display to the user.

    Returns:
        str: The valid OS path provided by the user, or None if the user provides an invalid path twice.
    """
    if default is not None:
        prompt_text += f" [default: {default}] "

    for i in range(TRIES + 1):
        response = input(prompt_text).strip()
        if not response and default is not None:
            response = default
        if os.path.exists(response):  # Check if the path exists on the system
            return Path(response)
        else:
            if i == TRIES:
                raise ValueError("Invalid response. Aborting")
            else:
                print(
                    f"{response} doesn't exist. Please respond a valid filesystem path"
                )
                continue

    print("You have entered an invalid path twice. Operation aborted.")
    return None


def prompt_str(prompt_text: str, default: str = None) -> str:
    """
    Prompts the user with a given text.

    Args:
        prompt_text (str): The text to display to the user.

    Returns:
        str: User input
    """
    if default is not None:
        prompt_text += f" [default: {default}] "
    else:
        prompt_text += ": "

    response = input(prompt_text).strip()
    for i in range(TRIES + 1):
        if not response and default is not None:
            return default
        elif response:
            return response
        else:
            if i == TRIES:
                raise ValueError("Empty response. Aborting.")
            print("Invalid response. Please provide a non-empty input.")
            response = input(prompt_text).strip()


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
