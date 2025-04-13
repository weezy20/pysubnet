from pathlib import Path
import json
import sys
import tomli  # install with `pip install tomli` if needed


def parse_config_file(config_file_path: Path) -> dict:
    """
    Parse a configuration file (JSON or TOML) and return a dictionary of kv pairs.
    """
    config_file = config_file_path.read_text()
    if config_file_path.suffix == ".json":
        data = json.loads(config_file)
    elif config_file_path.suffix == ".toml":
        data = tomli.loads(config_file)
    else:
        raise ValueError(f"Unsupported config file format: {config_file_path.suffix}")

    return data.get("nodes")


def load_nodes_from_file(config_file: Path) -> list[dict]:
    data = parse_config_file(config_file)
    return data["nodes"]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise ValueError(
            "Please provide the path to the configuration file as the first argument."
        )
    config_file_path = Path(sys.argv[1])
    if not config_file_path.exists():
        raise FileNotFoundError(f"The file '{config_file_path}' does not exist.")
    nodes = parse_config_file(config_file_path)
    print(nodes)  # Output will be the list of nodes defined in your configuration file.
