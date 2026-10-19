import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import uuid
from pathlib import Path
from typing import Any


DATA_DIR = Path(os.environ.get("INSTALITE_DATA_DIR", Path(__file__).parents[1] / "data"))


class JsonStore:
    def __init__(self, filename: str):
        self.path = DATA_DIR / filename
        self.lock = threading.Lock()

    def read(self) -> list[dict[str, Any]]:
        try:
            return json.loads(self.path.read_text("utf-8"))
        except FileNotFoundError:
            return []

    def write(self, value: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f".{uuid.uuid4().hex}.tmp")
        temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)


class AppAuthStore(JsonStore):
    def __init__(self) -> None:
        super().__init__("app-users.json")

    @staticmethod
    def _hash(password: str, salt: bytes | None = None) -> str:
        salt = salt or secrets.token_bytes(16)
        derived = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=64)
        return f"{base64.b64encode(salt).decode()}:{base64.b64encode(derived).decode()}"

    @staticmethod
    def _verify(password: str, stored: str) -> bool:
        try:
            salt_text, expected = stored.split(":", 1)
            actual = AppAuthStore._hash(password, base64.b64decode(salt_text)).split(":", 1)[1]
            return hmac.compare_digest(actual, expected)
        except Exception:
            return False

    def register(self, email: str, password: str) -> dict[str, str]:
        email = email.lower()
        with self.lock:
            users = self.read()
            if any(user["email"] == email for user in users):
                raise ValueError("An account with that email already exists.")
            result = {"id": str(uuid.uuid4()), "token": secrets.token_urlsafe(32)}
            users.append({"email": email, "passwordHash": self._hash(password), **result})
            self.write(users)
            return result

    def login(self, email: str, password: str) -> dict[str, str] | None:
        user = next((value for value in self.read() if value["email"] == email.lower()), None)
        if not user or not self._verify(password, user["passwordHash"]):
            return None
        return {"id": user["id"], "token": user["token"]}

    def user_for_token(self, token: str) -> str | None:
        user = next((value for value in self.read() if hmac.compare_digest(value["token"], token)), None)
        return user["id"] if user else None


class AccountStore(JsonStore):
    def __init__(self) -> None:
        super().__init__("accounts.json")

    def get_for_user(self, app_user_id: str) -> dict[str, Any] | None:
        return next((account for account in self.read() if account["appUserId"] == app_user_id), None)

    def save(self, account: dict[str, Any]) -> None:
        with self.lock:
            accounts = self.read()
            index = next((i for i, value in enumerate(accounts) if value["id"] == account["id"]), None)
            if index is None:
                accounts.append(account)
            else:
                accounts[index] = account
            self.write(accounts)
