import os
import random
import secrets

from flask import (
    Flask, flash, redirect, request, session, url_for,
)

import db
from html_build import build_page

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(BASE_DIR, "storage")

MAX_FILE_SIZE = 1024 * 1024
ALLOWED_EXT = ".txt"
AVATAR_COUNT = 50

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE + 512 * 1024

db.init_db()
os.makedirs(STORAGE_DIR, exist_ok=True)


def note_path(user_id):
    return os.path.join(STORAGE_DIR, f"{user_id}.txt")


def current_user():
    uid = session.get("user_id")
    return db.get_user_by_user_id(uid) if uid else None


def login_required():
    user = current_user()
    if user is None:
        session.clear()
        flash("Сначала войдите в аккаунт", "error")
    return user


def is_note_readable(user_id):
    path = note_path(user_id)
    return os.path.isfile(path) and os.path.getsize(path) > 0


@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("account"))
    return build_page("index.html")


@app.route("/login", methods=["POST"])
def login():
    login_ = (request.form.get("login") or "").strip()
    password = request.form.get("password") or ""

    user = db.verify_user(login_, password)
    if user is None:
        flash("Неверный логин или пароль", "error")
        return redirect(url_for("index"))

    session.clear()
    session["user_id"] = user["user_id"]
    flash("Вы успешно вошли", "success")
    return redirect(url_for("account"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return build_page("register.html")

    login_ = (request.form.get("login") or "").strip()
    password = request.form.get("password") or ""

    if not login_ or not password:
        flash("Логин и пароль не могут быть пустыми", "error")
        return redirect(url_for("register"))
    if len(login_) > 64 or len(password) > 128:
        flash("Слишком длинный логин или пароль", "error")
        return redirect(url_for("register"))
    if not login_.replace("_", "").replace("-", "").isalnum():
        flash("Логин: только буквы, цифры, «-» и «_»", "error")
        return redirect(url_for("register"))

    avatar = f"{random.randint(1, AVATAR_COUNT)}.jpg"
    user_id = db.create_user(login_, password, avatar)
    if user_id is None:
        flash("Пользователь с таким логином уже существует", "error")
        return redirect(url_for("register"))

    open(note_path(user_id), "w").close()

    session.clear()
    session["user_id"] = user_id
    return redirect(url_for("register_success"))


@app.route("/register/success")
def register_success():
    user = current_user()
    if user is None:
        return redirect(url_for("index"))
    return build_page("register_success.html", user=user)


@app.route("/logout")
def logout():
    session.clear()
    flash("Вы вышли из аккаунта", "success")
    return redirect(url_for("index"))


@app.route("/account")
def account():
    user = login_required()
    if user is None:
        return redirect(url_for("index"))
    return build_page(
        "account.html",
        user=user,
        has_note=is_note_readable(user["user_id"]),
    )


@app.route("/files")
def files():
    user = login_required()
    if user is None:
        return redirect(url_for("index"))
    return build_page(
        "files.html",
        user=user,
        has_note=is_note_readable(user["user_id"]),
    )


@app.route("/upload", methods=["GET", "POST"])
def upload():
    user = login_required()
    if user is None:
        return redirect(url_for("index"))

    if request.method == "POST":
        file = request.files.get("file")
        if file is None or file.filename == "":
            flash("Файл не выбран", "error")
            return build_page("upload_txt.html", user=user)

        if not file.filename.lower().endswith(ALLOWED_EXT):
            flash("Вы можете выбрать только файл с расширением .txt", "error")
            return build_page("upload_txt.html", user=user)

        data = file.read()
        if len(data) > MAX_FILE_SIZE:
            flash("Файл больше 1 Мб — загрузка отклонена", "error")
            return build_page("upload_txt.html", user=user)

        with open(note_path(user["user_id"]), "wb") as fh:
            fh.write(data)

        flash("Файл успешно загружен и сохранён!", "success")
        return redirect(url_for("account"))

    return build_page("upload_txt.html", user=user)


@app.route("/read")
def read():
    user = login_required()
    if user is None:
        return redirect(url_for("index"))

    path = note_path(user["user_id"])
    if not os.path.isfile(path):
        flash("Ваш файл не найден", "error")
        return redirect(url_for("account"))

    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        content = fh.read()

    if content == "":
        flash("Ваш файл пуст — читать нечего", "error")
        return redirect(url_for("account"))

    return build_page("read_txt.html", user=user, content=content)


@app.route("/game")
def game():
    user = login_required()
    if user is None:
        return redirect(url_for("index"))
    return build_page("game.html", user=user)


@app.errorhandler(413)
def request_entity_too_large(_e):
    flash("Файл слишком большой (максимум 1 Мб)", "error")
    return redirect(url_for("upload"))


@app.errorhandler(404)
def not_found(_e):
    return build_page("404.html"), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
