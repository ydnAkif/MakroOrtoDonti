#!/usr/bin/env python3
"""Fail-closed production/staging configuration preflight."""

from __future__ import annotations

import os
import sys

from app.config import is_insecure_secret


TRUE_VALUES = {"1", "true", "yes", "on"}


def validate_environment(env: dict[str, str]) -> list[str]:
    errors: list[str] = []
    secret = env.get("SECRET_KEY", "")
    encryption = env.get("ENCRYPTION_KEY", "")
    backup_keys = [v.strip() for v in env.get("BACKUP_ENCRYPTION_KEYS", "").split(",") if v.strip()]

    if is_insecure_secret(secret):
        errors.append("SECRET_KEY güçlü ve kalıcı olmalı")
    if is_insecure_secret(encryption):
        errors.append("ENCRYPTION_KEY güçlü ve kalıcı olmalı")
    if secret and secret == encryption:
        errors.append("SECRET_KEY ve ENCRYPTION_KEY farklı olmalı")
    if not backup_keys or is_insecure_secret(backup_keys[0]):
        errors.append("BACKUP_ENCRYPTION_KEYS ilk değeri güçlü güncel anahtar olmalı")
    if backup_keys and backup_keys[0] in {secret, encryption}:
        errors.append("Yedek anahtarı uygulama anahtarlarından farklı olmalı")

    for name in ("SESSION_COOKIE_SECURE", "FORCE_HSTS", "DATABASE_ENCRYPTION_AT_REST"):
        if env.get(name, "").lower() not in TRUE_VALUES:
            errors.append(f"{name}=true olmalı")
    if not env.get("REMOTE_BACKUP_URL", "").strip():
        errors.append("REMOTE_BACKUP_URL tanımlı olmalı")

    if env.get("TRUST_PROXY", "").lower() in TRUE_VALUES:
        forwarded = env.get("FORWARDED_ALLOW_IPS", "").strip()
        if not forwarded or forwarded == "*":
            errors.append("TRUST_PROXY için FORWARDED_ALLOW_IPS güvenilir IP/CIDR olmalı")
    return errors


def main() -> None:
    errors = validate_environment(dict(os.environ))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
    print("Production preflight PASSED.")


if __name__ == "__main__":
    main()
