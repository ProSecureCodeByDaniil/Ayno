#!/usr/bin/env python3

import json
import os
import re
import secrets
import string
import sys
from enum import Enum

try:
    import requests
except ImportError:
    print("Требуется пакет 'requests'. Установите: pip install requests",
          file=sys.stderr)
    sys.exit(110)


# ==================== CONFIGURATION ====================
PORT = int(os.environ.get("TXTCLOUD_PORT", "5000"))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
HTTP_TIMEOUT = 5.0


# ==================== DEBUG LOG ====================
def debug_log(msg, level="INFO"):
    if not DEBUG:
        return
    colors = {
        "INFO":  "\033[94m",    # Синий
        "GOOD":  "\033[92m",    # Зеленый
        "WARN":  "\033[93m",    # Желтый
        "ERROR": "\033[91m",    # Красный
        "RESET": "\033[0m",     # Сброс
    }
    color = colors.get(level, colors["INFO"])
    print(f"{color}[{level}]{colors['RESET']} {msg}",
          file=sys.stderr, flush=True)


# ==================== MESSAGES LOADER ====================
def _find_messages_file():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "star_wars_messages.json"),
        os.path.join(here, "..", "..", "star_wars_messages.json"),
        os.path.join(here, "..", "..", "..", "star_wars_messages.json"),
        os.path.join(os.getcwd(), "star_wars_messages.json"),
        os.path.join(os.getcwd(), "services", "txt_cloud",
                     "star_wars_messages.json"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def load_messages():
    path = _find_messages_file()
    if path is None:
        debug_log("star_wars_messages.json не найден, используем fallback",
                  "WARN")
        return ["A long time ago in a galaxy far, far away..."]
    try:
        with open(path, "r", encoding="utf-8") as fh:
            msgs = json.load(fh)
        if not isinstance(msgs, list) or not msgs:
            raise ValueError("not a non-empty list")
        debug_log(f"Загружено {len(msgs)} сообщений из {path}", "GOOD")
        return msgs
    except Exception as e:
        debug_log(f"Не удалось прочитать {path}: {e}", "WARN")
        return ["A long time ago in a galaxy far, far away..."]


MESSAGES = load_messages()


def get_random_message():
    return secrets.choice(MESSAGES)


# ==================== DATA GENERATORS ====================
def _random_alnum(n):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def generate_login():
    # app.py требует: только буквы, цифры, '-' и '_'
    return "pilot_" + _random_alnum(16)


def generate_password():
    return _random_alnum(24)


# ==================== HTTP CLIENT ====================
class TxtCloudClient:
    """Тонкая обёртка над requests.Session для приложения TXT Cloud"""

    def __init__(self, host, port=PORT):
        self.base = f"http://{host}:{port}"
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": "TXTCloudChecker/1.0"})

    def _get(self, path):
        return self.s.get(self.base + path,
                          timeout=HTTP_TIMEOUT, allow_redirects=True)

    def _post_form(self, path, data):
        return self.s.post(self.base + path, data=data,
                           timeout=HTTP_TIMEOUT, allow_redirects=True)

    def _post_multipart(self, path, files):
        return self.s.post(self.base + path, files=files,
                           timeout=HTTP_TIMEOUT, allow_redirects=True)

    # ---- actions ----
    def ping(self):
        r = self._get("/")
        return r.status_code == 200

    def register(self, login, password):
        r = self._post_form("/register",
                            {"login": login, "password": password})
        ok = ("Регистрация прошла успешно" in r.text
              or "/register/success" in r.url)
        debug_log(f"register({login}): status={r.status_code} ok={ok}", "INFO")
        return ok

    def login(self, login, password):
        r = self._post_form("/login",
                            {"login": login, "password": password})
        ok = "Личный кабинет" in r.text or "user_id" in r.text
        debug_log(f"login({login}): status={r.status_code} ok={ok}", "INFO")
        return ok

    def upload(self, content, filename="note.txt"):
        if isinstance(content, str):
            content = content.encode("utf-8")
        files = {"file": (filename, content, "text/plain")}
        r = self._post_multipart("/upload", files)
        ok = "Файл успешно загружен" in r.text
        debug_log(f"upload({filename}, {len(content)}b): "
                  f"status={r.status_code} ok={ok}", "INFO")
        return ok

    def read(self):
        r = self._get("/read")
        if r.status_code != 200:
            debug_log(f"read: status={r.status_code}", "ERROR")
            return None
        m = re.search(r'<div class="note-box">(.*?)</div>',
                      r.text, re.DOTALL)
        if not m:
            debug_log("read: note-box не найден", "ERROR")
            return None
        return m.group(1)

    def logout(self):
        try:
            self._get("/logout")
        except Exception:
            pass


# ==================== EXIT STATUS ====================
class ExitStatus(Enum):
    OK = 101
    CORRUPT = 102
    MUMBLE = 103
    DOWN = 104
    CHECKER_ERROR = 110


def die(code, msg=""):
    if msg:
        print(msg, file=sys.stderr, flush=True)
    debug_log(f"Exiting with {code.name} ({code.value})", "INFO")
    sys.exit(code.value)


def print_ok():
    print("OK", flush=True)


# ==================== ACTIONS ====================
def check(host):
    debug_log("=" * 60, "INFO")
    debug_log("CHECK ACTION", "INFO")
    debug_log("=" * 60, "INFO")

    try:
        client = TxtCloudClient(host)

        if not client.ping():
            die(ExitStatus.DOWN, "Service is not reachable on GET /")

        login = generate_login()
        password = generate_password()

        if not client.register(login, password):
            die(ExitStatus.MUMBLE, "Registration failed")

        if not client.login(login, password):
            die(ExitStatus.MUMBLE, "Login failed")

        message = get_random_message()
        debug_log(f"Сообщение длиной {len(message)} символов", "INFO")

        if not client.upload(message, "note.txt"):
            die(ExitStatus.MUMBLE, "Upload failed")

        stored = client.read()
        if stored is None:
            die(ExitStatus.MUMBLE, "Read returned nothing")

        if stored != message:
            idx = next(
                (i for i, (a, b) in enumerate(zip(stored, message)) if a != b),
                min(len(stored), len(message)),
            )
            die(ExitStatus.CORRUPT,
                f"Content mismatch at pos {idx}: "
                f"got {stored[idx:idx+40]!r}, "
                f"expected {message[idx:idx+40]!r} "
                f"(len got={len(stored)}, expected={len(message)})")

        client.logout()
        debug_log("CHECK OK", "GOOD")
        print_ok()
        die(ExitStatus.OK)

    except requests.RequestException as e:
        debug_log(f"HTTP error: {e}", "ERROR")
        die(ExitStatus.DOWN, str(e))
    except Exception as e:
        import traceback
        debug_log(traceback.format_exc(), "ERROR")
        die(ExitStatus.CHECKER_ERROR, str(e))


def put(host, flag_id, flag, vuln):
    debug_log("=" * 60, "INFO")
    debug_log(f"PUT ACTION vuln={vuln} in_flag_id={flag_id}", "INFO")
    debug_log("=" * 60, "INFO")

    login = generate_login()
    password = generate_password()

    try:
        client = TxtCloudClient(host)

        if not client.register(login, password):
            die(ExitStatus.MUMBLE, "Registration failed")

        if not client.login(login, password):
            die(ExitStatus.MUMBLE, "Login failed")

        if not client.upload(flag, "flag.txt"):
            die(ExitStatus.MUMBLE, "Upload failed")

        # Убеждаемся, что флаг реально записан и читается.
        stored = client.read()
        if stored != flag:
            die(ExitStatus.MUMBLE,
                f"Flag not readable right after upload "
                f"(got len={len(stored) if stored is not None else 'None'})")

        client.logout()

        new_flag_id = json.dumps({
            "login": login,
            "password": password,
        })

        debug_log(f"New flag_id: {new_flag_id}", "INFO")
        print_ok()
        sys.stderr.write(new_flag_id + "\n")
        sys.stderr.flush()
        die(ExitStatus.OK)

    except requests.RequestException as e:
        die(ExitStatus.DOWN, str(e))
    except Exception as e:
        import traceback
        debug_log(traceback.format_exc(), "ERROR")
        die(ExitStatus.CHECKER_ERROR, str(e))


def get(host, flag_id, flag, vuln):
    debug_log("=" * 60, "INFO")
    debug_log(f"GET ACTION vuln={vuln}", "INFO")
    debug_log("=" * 60, "INFO")

    try:
        data = json.loads(flag_id)
        login = data["login"]
        password = data["password"]
    except Exception as e:
        die(ExitStatus.CORRUPT, f"Invalid flag_id: {e}")

    try:
        client = TxtCloudClient(host)

        if not client.login(login, password):
            die(ExitStatus.CORRUPT, "Login failed")

        stored = client.read()
        if stored is None:
            die(ExitStatus.CORRUPT, "Read returned nothing")

        if stored != flag:
            die(ExitStatus.CORRUPT,
                f"Flag not found "
                f"(got len={len(stored)}, expected len={len(flag)})")

        client.logout()
        debug_log("GET OK", "GOOD")
        print_ok()
        die(ExitStatus.OK)

    except requests.RequestException as e:
        die(ExitStatus.DOWN, str(e))
    except Exception as e:
        import traceback
        debug_log(traceback.format_exc(), "ERROR")
        die(ExitStatus.CHECKER_ERROR, str(e))


def info():
    # Один сервис — одна уязвимость, по одному флагу за раунд.
    print("vulns: 1:1", flush=True)
    die(ExitStatus.OK)


# ==================== MAIN ====================
def _main():
    from sys import argv

    if len(argv) < 2:
        die(ExitStatus.CHECKER_ERROR, "Invalid arguments")

    cmd = argv[1]

    try:
        if cmd == "info":
            info()
        elif cmd == "check":
            if len(argv) < 3:
                die(ExitStatus.CHECKER_ERROR, "check requires <host>")
            check(argv[2])
        elif cmd == "put":
            if len(argv) < 6:
                die(ExitStatus.CHECKER_ERROR,
                    "put requires <host> <flag_id> <flag> <vuln>")
            put(argv[2], argv[3], argv[4], int(argv[5]))
        elif cmd == "get":
            if len(argv) < 6:
                die(ExitStatus.CHECKER_ERROR,
                    "get requires <host> <flag_id> <flag> <vuln>")
            get(argv[2], argv[3], argv[4], int(argv[5]))
        else:
            die(ExitStatus.CHECKER_ERROR, f"Unknown action: {cmd}")
    except IndexError:
        die(ExitStatus.CHECKER_ERROR, "Invalid arguments")
    except SystemExit:
        raise
    except Exception as e:
        die(ExitStatus.CHECKER_ERROR, str(e))


if __name__ == "__main__":
    _main()
