from datetime import UTC, datetime
from dataclasses import dataclass
from typing import Any

from instagrapi import Client


class InstagramError(Exception):
    pass


class InstagramChallengeError(InstagramError):
    pass


class InstagramTwoFactorError(InstagramError):
    def __init__(
        self,
        message: str,
        *,
        session: dict[str, Any] | None = None,
        device: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.session = session
        self.device = device


class InstagramLoginRequiredError(InstagramError):
    pass


class InstagramLoginError(InstagramError):
    pass


class InstagramProviderCompatibilityError(InstagramError):
    """Instagram rejected the adapter's current private-client login flow."""

    def __init__(self, message: str, diagnostic: dict[str, Any]) -> None:
        super().__init__(message)
        self.diagnostic = diagnostic


@dataclass
class LoginTrace:
    """Only non-secret facts about one login attempt.

    CAA result payloads can contain opaque contexts and account data.  Keep
    booleans here so API responses and logs cannot disclose that payload.
    """

    caa_attempted: bool = False
    legacy_attempted: bool = False
    caa_fallback_requested: bool = False
    caa_two_factor_context: bool = False
    failure_phase: str = "unknown"

    def diagnostic(self) -> dict[str, Any]:
        if self.failure_phase == "caa":
            code = "instagram_login.caa_needs_upgrade"
        elif self.failure_phase == "legacy":
            code = "instagram_login.legacy_needs_upgrade"
        elif self.legacy_attempted and self.caa_attempted:
            code = "instagram_login.caa_legacy_needs_upgrade"
        else:
            code = "instagram_login.needs_upgrade"
        return {
            "code": code,
            "failurePhase": self.failure_phase,
            "caaAttempted": self.caa_attempted,
            "legacyAttempted": self.legacy_attempted,
            "caaFallbackRequested": self.caa_fallback_requested,
            "caaTwoFactorContext": self.caa_two_factor_context,
            # CAA_LOGIN_FALLBACK is an instruction to change endpoint, not an
            # explanation for why that account was routed there.  Do not turn
            # that opaque server decision into a guessed account diagnosis.
            "diagnosis": "indeterminate" if self.caa_fallback_requested else "not_available",
        }


def _message(error: Exception) -> str:
    return str(error) or error.__class__.__name__


def _raise_mapped(error: Exception, login_trace: LoginTrace | None = None) -> None:
    name = error.__class__.__name__.lower()
    message = _message(error)
    error_type = str(getattr(error, "error_type", "") or "").lower()
    if error_type == "needs_upgrade" or "version of instagram is out of date" in message.lower():
        trace = login_trace or LoginTrace()
        if trace.caa_fallback_requested and trace.failure_phase == "legacy":
            user_message = (
                "Instagram directed this CAA login to its legacy mobile endpoint, "
                "which then rejected the request as an outdated app before a verification flow began. "
                "This response does not identify an account-specific cause, and this adapter has no supported continuation for it."
            )
        else:
            user_message = (
                "Instagram rejected the private-client login request as an outdated app. "
                "This response does not identify an account-specific cause, and this adapter has no supported continuation for it."
            )
        raise InstagramProviderCompatibilityError(
            user_message,
            trace.diagnostic(),
        ) from error
    if "challenge" in name or "challenge" in message.lower() or "checkpoint" in message.lower():
        raise InstagramChallengeError("Instagram requires a login challenge. Complete it in Instagram, then reconnect this account.") from error
    if "twofactor" in name or "two_factor" in name:
        raise InstagramTwoFactorError("Instagram requires a verification code.") from error
    if "loginrequired" in name or "login_required" in message.lower() or "session" in message.lower():
        raise InstagramLoginRequiredError("Instagram session requires login again.") from error
    if "badpassword" in name or "password" in message.lower() or "login" in name:
        raise InstagramLoginError("Instagram rejected the username or password.") from error
    raise InstagramError(f"Instagram request failed: {message}") from error


def split_settings(settings: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    session_keys = {"cookies", "authorization_data", "last_login"}
    return ({key: value for key, value in settings.items() if key in session_keys}, {key: value for key, value in settings.items() if key not in session_keys})


def merge_settings(session: dict[str, Any], device: dict[str, Any]) -> dict[str, Any]:
    return {**device, **session}


class InstagramAdapter:
    """The only module that knows instagrapi's private response structure."""

    def __init__(self) -> None:
        self.client = Client()

    def _trace_login(self, trace: LoginTrace) -> tuple[Any, Any]:
        """Wrap only library entry points to record CAA control flow.

        The wrapper does not inspect or retain request/response bodies.  It is
        removed at the end of the request so no state crosses app users.
        """
        original_caa = getattr(self.client, "bloks_caa_login", None)
        original_legacy = getattr(self.client, "login_legacy", None)

        if callable(original_caa):
            def traced_caa(*args: Any, **kwargs: Any) -> Any:
                trace.caa_attempted = True
                try:
                    outcome = original_caa(*args, **kwargs)
                except Exception:
                    trace.failure_phase = "caa"
                    raise
                if isinstance(outcome, dict):
                    markers = getattr(self.client, "_caa_result_action_markers", lambda _: [])(outcome)
                    trace.caa_fallback_requested = any(
                        isinstance(marker, str) and marker.startswith("CAA_LOGIN_FALLBACK:")
                        for marker in markers
                    )
                    context = getattr(self.client, "_extract_two_step_verification_context", lambda _: "")(outcome)
                    trace.caa_two_factor_context = bool(context)
                return outcome

            self.client.bloks_caa_login = traced_caa

        if callable(original_legacy):
            def traced_legacy(*args: Any, **kwargs: Any) -> Any:
                trace.legacy_attempted = True
                try:
                    return original_legacy(*args, **kwargs)
                except Exception:
                    trace.failure_phase = "legacy"
                    raise

            self.client.login_legacy = traced_legacy

        return original_caa, original_legacy

    def _restore_login_trace(self, original_caa: Any, original_legacy: Any) -> None:
        if callable(original_caa):
            self.client.bloks_caa_login = original_caa
        if callable(original_legacy):
            self.client.login_legacy = original_legacy

    def login(
        self, username: str, password: str, verification_code: str | None = None
    ) -> tuple[str, str, dict[str, Any], dict[str, Any]]:
        trace = LoginTrace()
        original_caa, original_legacy = self._trace_login(trace)
        try:
            authenticated = self.client.login(
                username, password, verification_code=(verification_code or "").strip()
            )
            if not authenticated:
                raise InstagramLoginError("Instagram rejected the username or password.")
            settings = self.client.get_settings()
            account_username = getattr(self.client, "username", None) or username
            account_id = str(getattr(self.client, "user_id", "") or "")
            if not account_id:
                raise InstagramError("Instagram did not return an account identifier.")
            session, device = split_settings(settings)
            return account_id, account_username, session, device
        except InstagramError:
            raise
        except Exception as error:
            try:
                _raise_mapped(error, trace)
            except InstagramTwoFactorError as mapped:
                # The generated device identity is safe to retain encrypted and
                # lets the next password-and-code attempt use the same device.
                # The password and verification code never enter these settings.
                session, device = self.settings()
                raise InstagramTwoFactorError(str(mapped), session=session, device=device) from error
        finally:
            self._restore_login_trace(original_caa, original_legacy)

    def restore(self, session: dict[str, Any], device: dict[str, Any]) -> None:
        try:
            settings = merge_settings(session, device)
            # State from the retired Node adapter is a different client schema;
            # it must be reconnected instead of being treated as a valid device.
            if not isinstance(settings.get("uuids"), dict) or not isinstance(settings.get("cookies"), dict):
                raise InstagramLoginRequiredError("Saved Instagram state belongs to an incompatible adapter. Reconnect this account.")
            self.client.set_settings(settings)
        except InstagramError:
            raise
        except Exception as error:
            _raise_mapped(error)

    def settings(self) -> tuple[dict[str, Any], dict[str, Any]]:
        return split_settings(self.client.get_settings())

    def get_timeline(self) -> list[dict[str, Any]]:
        try:
            raw = self.client.get_timeline_feed("cold_start_fetch")
            entries = raw.get("feed_items", raw.get("items", [])) if isinstance(raw, dict) else []
            result: list[dict[str, Any]] = []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                media = entry.get("media_or_ad") or entry.get("media") or entry
                item = normalize_timeline_item(media, entry)
                if item:
                    result.append(item)
            return result
        except Exception as error:
            _raise_mapped(error)


def _media_candidate(value: dict[str, Any], is_video: bool) -> dict[str, Any] | None:
    if is_video:
        candidates = value.get("video_versions") or []
    else:
        candidates = (value.get("image_versions2") or {}).get("candidates") or []
    return next((candidate for candidate in candidates if isinstance(candidate, dict) and candidate.get("url")), None)


def normalize_timeline_item(raw: Any, wrapper: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    author = raw.get("user") or {}
    if not raw.get("pk") or not author.get("pk") or not author.get("username"):
        return None
    carousel = raw.get("carousel_media") or []
    sources = carousel if carousel else [raw]
    media = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        # The web MVP renders carousel cards as images. Private responses
        # usually include an image thumbnail even when a child is a video.
        candidate = _media_candidate(source, False if carousel else source.get("media_type") == 2)
        if candidate:
            media.append({"url": candidate["url"], "width": candidate.get("width", 0), "height": candidate.get("height", 0)})
    if not media:
        return None
    timestamp = raw.get("taken_at")
    try:
        created_at = datetime.fromtimestamp(int(timestamp), UTC).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError, OSError):
        created_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    friendship = author.get("friendship_status") or {}
    suggested = bool(wrapper.get("suggested_users") or wrapper.get("is_suggested") or raw.get("injected"))
    sponsored = bool(wrapper.get("ads_metadata") or raw.get("is_ad") or raw.get("is_paid_partnership"))
    return {
        "id": str(raw["pk"]),
        "type": "carousel" if carousel else ("video" if raw.get("media_type") == 2 else "image"),
        "author": {"id": str(author["pk"]), "username": author["username"], "avatarUrl": author.get("profile_pic_url")},
        "caption": (raw.get("caption") or {}).get("text") or None,
        "media": media,
        "createdAt": created_at,
        "policy": {
            "isSuggested": suggested,
            "isSponsored": sponsored,
            "isReel": raw.get("product_type") == "clips" or bool(raw.get("is_unified_video")),
            "isFollowing": friendship.get("following"),
        },
    }
