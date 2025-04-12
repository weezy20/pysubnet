import os
from pathlib import Path

TRIES = 2  # Number extra tries before aborting


def prompt_bool(prompt_text: str) -> bool:
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

    for i in range(TRIES+1):
        response = input(prompt_text).strip().lower()
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


def prompt_path(prompt_text: str) -> Path:
    """
    Prompts the user with a given text and validates if the response is a valid OS path.

    Args:
        prompt_text (str): The text to display to the user.

    Returns:
        str: The valid OS path provided by the user, or None if the user provides an invalid path twice.
    """
    for i in range(TRIES+1):
        response = input(prompt_text).strip()
        if os.path.exists(response):  # Check if the path exists on the system
            return Path(response)
        else:
            if i == TRIES:
                raise ValueError("Invalid response. Aborting")
            else:
                print("Invalid response. Please respond a valid filesystem path")
                continue

    print("You have entered an invalid path twice. Operation aborted.")
    return None
