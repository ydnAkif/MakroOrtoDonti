from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
import bcrypt
from urllib.parse import urlparse, urljoin

from app.extensions import db
from app.models.models import User

auth_bp = Blueprint("auth", __name__)


def _is_safe_redirect_url(target: str) -> bool:
    if not target:
        return False
    host_url = urlparse(request.host_url)
    redirect_url = urlparse(urljoin(request.host_url, target))
    return redirect_url.scheme in ("http", "https") and host_url.netloc == redirect_url.netloc


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = db.session.execute(
            db.select(User).where(User.username == username)
        ).scalar_one_or_none()

        if user and user.is_active:
            try:
                password_matches = bcrypt.checkpw(
                    password.encode("utf-8"),
                    user.password_hash.encode("utf-8"),
                )
            except ValueError:
                password_matches = False

            if password_matches:
                login_user(user)
                next_page = request.args.get("next")
                flash("Giriş başarılı!", "success")
                if next_page and _is_safe_redirect_url(next_page):
                    return redirect(next_page)
                return redirect(url_for("dashboard.index"))

        flash("Kullanıcı adı veya şifre hatalı.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Çıkış yapıldı.", "info")
    return redirect(url_for("auth.login"))
