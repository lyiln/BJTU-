from __future__ import annotations

from .storage import load_settings, save_settings

SERVICE_NAME = "bjtu-room-finder"


class CredentialError(RuntimeError):
    pass


def get_username() -> str | None:
    return load_settings().get("username")


def save_username(username: str) -> None:
    settings = load_settings()
    settings["username"] = username.strip()
    save_settings(settings)


def save_password(username: str, password: str) -> None:
    try:
        import keyring
    except Exception as exc:  # pragma: no cover - depends on platform
        raise CredentialError("keyring is not installed or cannot be imported") from exc

    try:
        keyring.set_password(SERVICE_NAME, username, password)
    except Exception as exc:  # pragma: no cover - depends on platform
        raise CredentialError(f"failed to save password in system keyring: {exc}") from exc


def get_password(username: str) -> str | None:
    try:
        import keyring
    except Exception:
        return None
    try:
        return keyring.get_password(SERVICE_NAME, username)
    except Exception:
        return None


def save_credentials(username: str, password: str) -> None:
    clean_username = username.strip()
    if not clean_username:
        raise CredentialError("username cannot be empty")
    if not password:
        raise CredentialError("password cannot be empty")
    save_username(clean_username)
    save_password(clean_username, password)
