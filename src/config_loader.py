import os
import re

import yaml


ENV_PATTERN = re.compile(r"^\$\{([A-Z0-9_]+):([^}]*)\}$")


def resolve_env_values(value):
    if isinstance(value, dict):
        return {
            key: resolve_env_values(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            resolve_env_values(item)
            for item in value
        ]

    if isinstance(value, str):
        match = ENV_PATTERN.match(value)

        if match:
            env_name, default = match.groups()
            return os.getenv(env_name, default)

    return value


def load_config():
    config_path = os.path.join(os.getcwd(), "config.yaml")
    with open(config_path, "r") as f:
        return resolve_env_values(yaml.safe_load(f))
