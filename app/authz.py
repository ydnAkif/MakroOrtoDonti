from __future__ import annotations

from functools import wraps

from flask import flash, redirect, url_for
from flask_login import current_user


def roles_required(*roles: str):
    """Restrict endpoint access to users with one of the given roles."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))

            user_role = getattr(current_user, "role", None)
            if user_role not in roles:
                flash("Bu işlem için yetkiniz bulunmuyor.", "danger")
                return redirect(url_for("dashboard.index"))

            return view_func(*args, **kwargs)

        return wrapped

    return decorator
