"""Helpers de 2FA TOTP - P2 (flag TWOFA_ENABLED, default off)."""

import os

PENDING_SESSION_KEY = "pending_2fa_user_id"
PENDING_EXP_KEY = "pending_2fa_exp"
PENDING_REMEMBER_KEY = "pending_2fa_remember"
PENDING_TTL_SECONDS = 600
SETUP_SECRET_KEY = "twofa_setup_secret"
SETUP_CODES_KEY = "twofa_setup_codes"


def twofa_enabled() -> bool:
    return (os.environ.get("TWOFA_ENABLED") or "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def get_totp(secret: str):
    import pyotp

    return pyotp.TOTP(secret)


def verify_totp(secret: str, code: str) -> bool:
    try:
        totp = get_totp(secret)
        return bool(totp.verify((code or "").strip(), valid_window=1))
    except Exception:
        return False


def provisioning_uri(secret: str, email: str) -> str:
    try:
        return get_totp(secret).provisioning_uri(
            name=email, issuer_name="PlanejaENEM"
        )
    except Exception:
        return ""
