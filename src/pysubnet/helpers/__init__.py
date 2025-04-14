# helpers/__init__.py
import os
from pathlib import Path
from .process import parse_subkey_output, run_command
from .prompts import prompt_str, prompt_path, prompt_bool
from .config import load_config, PySubnetConfig, NetworkConfig, NodeConfig


def l2_seg(path: str) -> str:
    """Returns last two path segments as a string, or basename if too short.

    Example:
        "/a/b/c/d" -> "c/d"
        "/tmp" -> "tmp"
        "C:\\Users\\John" -> "Users/John"
    """
    path_obj = Path(path)  # Convert input string to Path
    parts = path_obj.parts
    if len(parts) < 2:
        return path_obj.name  # Return basename as string
    return f"{parts[-2]}/{parts[-1]}"  # Join last two with forward slash


__all__ = [
    "parse_subkey_output",
    "run_command",
    "prompt_str",
    "prompt_path",
    "prompt_bool",
    "load_config",
    "PySubnetConfig",
    "NetworkConfig",
    "NodeConfig",
    l2_seg,
]
