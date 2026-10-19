import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field

from .crypto import decrypt_json, encrypt_json
from .feed_policy import FEED_SESSION_LIMIT, apply_feed_policy
from .instagram import InstagramAdapter, InstagramChallengeError, InstagramError, InstagramLoginError, InstagramLoginRequiredError, InstagramProviderCompatibilityError, InstagramTwoFactorError
from .stores import AccountStore, AppAuthStore


def load_env() -> None:
    for path in (Path.cwd() / ".env", Path(__file__).parents[3] / ".env"):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


load_env()
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
accounts = AccountStore()
app_auth = AppAuthStore()


@app.exception_handler(HTTPException)
async def http_exception_response(_: Request, error: HTTPException) -> JSONResponse:
    """Keep the JSON error contract the Vite client used with the Fastify API."""
    content = error.detail if isinstance(error.detail, dict) else {"error": error.detail}
    return JSONResponse(status_code=error.status_code, content=content)


class AppCredentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class InstagramCredentials(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    verification_code: str | None = Field(default=None, min_length=4, max_length=32)


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def public_account(account: dict) -> dict:
    return {key: account[key] for key in ("id", "username", "status", "updatedAt")}


def current_user(authorization: Annotated[str | None, Header()] = None) -> str:
    token = authorization.removeprefix("Bearer ") if authorization else ""
    user_id = app_auth.user_for_token(token)
    if not user_id:
        raise HTTPException(401, "Unauthorized")
    return user_id


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/app-auth/register", status_code=201)
def register(body: AppCredentials) -> dict:
    if len(body.password) < 10:
        raise HTTPException(422, "Password must be at least 10 characters.")
    try:
        return app_auth.register(str(body.email), body.password)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@app.post("/app-auth/login")
def login(body: AppCredentials) -> dict:
    result = app_auth.login(str(body.email), body.password)
    if not result:
        raise HTTPException(401, "Invalid email or password.")
    return result


@app.get("/account")
def account(app_user_id: Annotated[str, Depends(current_user)]) -> dict:
    value = accounts.get_for_user(app_user_id)
    return {"account": public_account(value) if value else None}


@app.post("/auth/login", status_code=201)
def instagram_login(body: InstagramCredentials, app_user_id: Annotated[str, Depends(current_user)]) -> dict:
    adapter = InstagramAdapter()
    old = accounts.get_for_user(app_user_id)
    try:
        if old and old["status"] == "two_factor_required" and old["username"].lower() == body.username.lower():
            adapter.restore(decrypt_json(old["encryptedSession"]), decrypt_json(old["encryptedDeviceState"]))
        instagram_user_id, username, session, device = adapter.login(body.username, body.password, body.verification_code)
        value = {
            "id": old["id"] if old else str(uuid.uuid4()), "appUserId": app_user_id,
            "instagramUserId": instagram_user_id, "username": username,
            "encryptedSession": encrypt_json(session), "encryptedDeviceState": encrypt_json(device),
            "status": "active", "updatedAt": now(),
        }
        accounts.save(value)
        return {"account": public_account(value)}
    except InstagramChallengeError as error:
        raise HTTPException(409, str(error)) from error
    except InstagramTwoFactorError as error:
        if error.session is not None and error.device is not None:
            value = {
                "id": old["id"] if old else str(uuid.uuid4()), "appUserId": app_user_id,
                "instagramUserId": old["instagramUserId"] if old else "", "username": body.username,
                "encryptedSession": encrypt_json(error.session), "encryptedDeviceState": encrypt_json(error.device),
                "status": "two_factor_required", "updatedAt": now(),
            }
            accounts.save(value)
        raise HTTPException(409, str(error)) from error
    except InstagramLoginError as error:
        raise HTTPException(401, str(error)) from error
    except InstagramProviderCompatibilityError as error:
        raise HTTPException(503, detail={"error": str(error), "diagnostic": error.diagnostic}) from error
    except InstagramError as error:
        raise HTTPException(502, str(error)) from error


@app.get("/feed")
def feed(app_user_id: Annotated[str, Depends(current_user)]) -> dict:
    account_value = accounts.get_for_user(app_user_id)
    if not account_value:
        raise HTTPException(404, "Connect an Instagram account first.")
    if account_value["status"] != "active":
        raise HTTPException(401, detail={"error": "Instagram login is required.", "status": account_value["status"]})
    adapter = InstagramAdapter()
    try:
        adapter.restore(decrypt_json(account_value["encryptedSession"]), decrypt_json(account_value["encryptedDeviceState"]))
        items = apply_feed_policy(adapter.get_timeline())
        session, device = adapter.settings()
        account_value.update({"encryptedSession": encrypt_json(session), "encryptedDeviceState": encrypt_json(device), "updatedAt": now()})
        accounts.save(account_value)
        return {"items": items, "limit": FEED_SESSION_LIMIT}
    except (InstagramLoginRequiredError, InstagramChallengeError) as error:
        status = "challenge_required" if isinstance(error, InstagramChallengeError) else "login_required"
        account_value.update({"status": status, "updatedAt": now()})
        accounts.save(account_value)
        raise HTTPException(401, detail={"error": str(error), "status": status}) from error
    except ValueError as error:
        raise HTTPException(500, "Saved Instagram state cannot be decrypted. Check SESSION_ENCRYPTION_KEY.") from error
    except InstagramError as error:
        raise HTTPException(502, str(error)) from error
