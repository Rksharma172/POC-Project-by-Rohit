import hashlib
import os
import re

from fastapi import Header, HTTPException

from src.config_loader import load_config


config = load_config()


def slugify_owner(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9_-]+", "-", value)
    value = value.strip("-")
    return value or "default"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_demo_users() -> dict[str, str]:
    users = {}
    configured = config.get("security", {}).get("demo_users", {})

    for username, password in configured.items():
        env_name = f"ASKPOLICY_USER_{username.upper()}_PASSWORD"
        users[username] = os.getenv(env_name, str(password))

    return users


def verify_login(username: str, password: str) -> str | None:
    users = get_demo_users()
    expected = users.get(slugify_owner(username))

    if expected and password == expected:
        return slugify_owner(username)

    return None


def get_current_owner(
    x_askpolicy_user: str | None = Header(default=None),
    x_askpolicy_token: str | None = Header(default=None)
) -> str:
    owner = slugify_owner(x_askpolicy_user or "default")

    if owner == "default":
        return owner

    expected = get_demo_users().get(owner)

    if not expected:
        raise HTTPException(status_code=401, detail="Unknown user")

    if x_askpolicy_token != hash_token(f"{owner}:{expected}"):
        raise HTTPException(status_code=401, detail="Invalid session")

    return owner
