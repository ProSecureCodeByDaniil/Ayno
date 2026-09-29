#!/usr/bin/env python3

import html
import json
import os
import random
import re
import secrets
import sys
import tempfile

try:
    import requests
except ImportError:
    print("Требуется пакет 'requests'. Установите: pip install requests",
          file=sys.stderr)
    sys.exit(2)


# ==================== CONFIGURATION ====================
DEFAULT_URL = "http://127.0.0.1:5000"
TIMEOUT = 15
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

BASE_URL = os.environ.get("TXTCLOUD_URL", DEFAULT_URL).rstrip("/")
HERE = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(HERE, "star_wars_messages.json")

# Параметры генерации флага: TEAM000_<32 символа A-Z0-9>
FLAG_PREFIX = "TEAM000_"
FLAG_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
FLAG_SUFFIX_LENGTH = 32


def debug_log(msg, level="INFO"):
    if not DEBUG:
        return
    colors = {
        "INFO": "\033[94m",
        "GOOD": "\033[92m",
        "WARN": "\033[93m",
        "ERROR": "\033[91m",
        "RESET": "\033[0m",
    }
    color = colors.get(level, colors["INFO"])
    print(f"{color}[{level}]{colors['RESET']} {msg}",
          file=sys.stderr, flush=True)


# ==================== HTTP HELPERS ====================
def new_session():
    s = requests.Session()
    s.headers.update({"User-Agent": "TXTCloudChecker/1.0"})
    return s


def rtext(r):
    return r.content.decode("utf-8", errors="replace")


def generate_credentials():
    return f"pilot_{secrets.token_hex(16)}", secrets.token_hex(16)


def generate_flag():
    """Генерирует флаг вида TEAM000_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX."""
    suffix = "".join(secrets.choice(FLAG_ALPHABET)
                     for _ in range(FLAG_SUFFIX_LENGTH))
    return f"{FLAG_PREFIX}{suffix}"


def register(session, login, password):
    return session.post(
        f"{BASE_URL}/register",
        data={"login": login, "password": password},
        timeout=TIMEOUT, allow_redirects=True,
    )


def do_login(session, login, password):
    return session.post(
        f"{BASE_URL}/login",
        data={"login": login, "password": password},
        timeout=TIMEOUT, allow_redirects=True,
    )


def post_upload(session, content, filename):
    files = {"file": (filename, content, "text/plain")}
    return session.post(
        f"{BASE_URL}/upload", files=files,
        timeout=TIMEOUT, allow_redirects=True,
    )


def extract_user_id(html_body):
    m = re.search(r'user_id:\s*<code>([0-9a-fA-F]+)</code>', html_body)
    return m.group(1) if m else None


def extract_note(html_body):
    m = re.search(r'<div class="note-box">(.*?)</div>', html_body, re.DOTALL)
    if not m:
        return None
    return html.unescape(m.group(1))


# ==================== REPORT FRAMEWORK ====================
PASSED, FAILED = [], []


def check(name, ok, detail=""):
    if ok:
        PASSED.append(name)
        print(f"  [OK]   {name}")
    else:
        FAILED.append((name, detail))
        print(f"  [FAIL] {name}" + (f"  ({detail})" if detail else ""))


def section(title):
    print(f"\n=== {title} ===")


def creds(login, password):
    print(f"  Логин:  {login}")
    print(f"  Пароль: {password}")


def show_block(title, text):
    line = "─" * max(10, 56 - len(title))
    print(f"  ┌─ {title} {line}")
    for ln in text.split("\n"):
        print(f"  │ {ln}")
    print(f"  └{'─' * 60}")


# ==================== EXPECTED TEXTS ====================
EXPECTED_TEXTS = {
    "_base": [
        'TXT<span>Cloud</span>',
    ],
    "/": [
        "A long time ago in a galaxy far, far away…",
        "Хранилище txt-файлов",
        "1 Мб на пользователя. Один файл. Доступ с любого устройства.",
        "Да пребудет с вами Сила",
        "⚔ Вход",
        "✦ Регистрация",
        "Логин",
        "Пароль",
        "Войти",
        "Джабба Хатт ждёт тебя. Он занесёт тебя в свои списки.",
        "Пройти регистрацию",
    ],
    "/register": [
        "Регистрация",
        "Джабба Хатт",
    ],
    "/account": [
        "Личный кабинет",
        "user_id:",
        "✦ Начинающий пилот TXT Cloud ✦",
        "Мои файлы",
        "Файл ещё не загружен",
        "Загрузить файл",
        "Только .txt, размером до 1 Мб",
        "Hyperspace Defender",
        "Сбей TIE-файтеры, уклоняйся от астероидов",
        "Выйти из аккаунта",
        "Завершить сессию и вернуться на вход",
    ],
    "/files": [
        "Мои файлы",
        "📁 Ваш txt-файл",
        "Файл ещё не загружен.",
        "🚀 Развлечение",
        "Сыграйте в Hyperspace Defender, пока Империя не видит.",
        "Играть",
    ],
    "/game": [
        "HYPERSPACE DEFENDER",
        "«Войди в гиперпространство, пилот»",
        "Имя пилота",
        "Старт",
        "Закрыть",
        "✦ ТОП-10 ✦",
    ],
    "/upload": [
        "Загрузка файла",
        "Только",
        ".txt",
        "не больше",
        "1 Мб",
        "турболазером",
        "Выбрать файл",
        "Загрузить",
        "Назад",
    ],
    "404": [
        "404 — эти дроиды не те, что вы ищете",
        "В чём дело? Всё же работало",
        "На главную",
    ],
}


# ==================== TESTS ====================
def test_server_alive():
    section("Доступность сервера и публичные страницы")
    s = new_session()

    try:
        r = s.get(f"{BASE_URL}/", timeout=TIMEOUT)
    except requests.RequestException as e:
        check("Сервер отвечает", False, str(e))
        return False

    check("GET / — 200", r.status_code == 200, f"status={r.status_code}")

    r = s.get(f"{BASE_URL}/register", timeout=TIMEOUT)
    check("GET /register — 200", r.status_code == 200,
          f"status={r.status_code}")

    r = s.get(f"{BASE_URL}/no-such-page-xyz", timeout=TIMEOUT)
    check("GET неизвестного URL — 404", r.status_code == 404,
          f"status={r.status_code}")
    return True


def test_login_required():
    section("Защита маршрутов (login_required)")
    for url in ["/account", "/files", "/upload", "/read", "/game"]:
        s = new_session()
        r = s.get(f"{BASE_URL}{url}",
                  allow_redirects=False, timeout=TIMEOUT)
        loc = r.headers.get("Location", "")
        ok = r.status_code == 302 and loc.rstrip("/") in ("", BASE_URL)
        check(f"GET {url} без логина → 302 на /", ok,
              f"status={r.status_code}, loc={loc!r}")


def test_register_negative():
    section("Регистрация — негативные кейсы")

    s = new_session()
    r = s.post(f"{BASE_URL}/register",
               data={"login": "", "password": ""},
               timeout=TIMEOUT, allow_redirects=True)
    check("Пустые логин/пароль отклонены",
          "не могут быть пустыми" in rtext(r))

    s = new_session()
    r = s.post(f"{BASE_URL}/register",
               data={"login": "bad name!", "password": "pass"},
               timeout=TIMEOUT, allow_redirects=True)
    check("Недопустимые символы в логине",
          "только буквы, цифры" in rtext(r))

    s = new_session()
    r = s.post(f"{BASE_URL}/register",
               data={"login": "x" * 100, "password": "pass"},
               timeout=TIMEOUT, allow_redirects=True)
    check("Слишком длинный логин отклонён",
          "Слишком длинный" in rtext(r))


def test_register_success_and_duplicate():
    section("Регистрация — успех и дубликат")

    login, password = generate_credentials()
    creds(login, password)
    print(f"  Длина логина:  {len(login)}")
    print(f"  Длина пароля:  {len(password)}")

    s = new_session()
    r = register(s, login, password)
    check("Успешная регистрация → /register/success",
          "/register/success" in r.url, f"url={r.url}")
    check("Страница успеха содержит логин", login in rtext(r))
    check("Страница успеха: 'Регистрация прошла успешно'",
          "Регистрация прошла успешно" in rtext(r))

    s2 = new_session()
    r2 = register(s2, login, password)
    check("Дубликат логина отклонён",
          "уже существует" in rtext(r2))

    return s, login, password


def test_logged_in_pages(session, login):
    section("Личный кабинет / файлы / игра (пустое состояние)")
    print(f"  Проверяем логин в /account: {login}")

    r = session.get(f"{BASE_URL}/",
                    allow_redirects=False, timeout=TIMEOUT)
    loc = r.headers.get("Location", "")
    check("Авторизованный GET / → 302 на /account",
          r.status_code == 302 and "/account" in loc, f"loc={loc!r}")

    r = session.get(f"{BASE_URL}/account", timeout=TIMEOUT)
    b = rtext(r)
    check("GET /account — 200", r.status_code == 200,
          f"status={r.status_code}")
    check("Account содержит user_id", "user_id" in b)
    check("Account содержит аватар", "/static/avatars/" in b)
    check("Account: файл ещё не загружен", "не загружен" in b)

    check("Account содержит ожидаемый логин", login in b,
          f"ожидался {login!r}")
    check('Account: логин в <div class="name">',
          f'<div class="name">{login}</div>' in b,
          f"искали <div class=\"name\">{login}</div>")

    m = re.search(r'<div class="name">([^<]*)</div>', b)
    found = m.group(1) if m else None
    check("Account: .name совпадает с ожидаемым",
          found == login,
          f"найдено {found!r}, ожидалось {login!r}")

    r = session.get(f"{BASE_URL}/files", timeout=TIMEOUT)
    check("GET /files — 200", r.status_code == 200)

    r = session.get(f"{BASE_URL}/read",
                    timeout=TIMEOUT, allow_redirects=True)
    check("GET /read с пустым файлом → 'пуст'",
          "пуст" in rtext(r))

    r = session.get(f"{BASE_URL}/game", timeout=TIMEOUT)
    check("GET /game — 200", r.status_code == 200)


def test_upload_negative(session):
    section("Загрузка — негативные кейсы")

    r = session.post(f"{BASE_URL}/upload", data={},
                     timeout=TIMEOUT, allow_redirects=True)
    check("Без файла → 'Файл не выбран'",
          "Файл не выбран" in rtext(r))

    r = post_upload(session, b"hello world", "note.pdf")
    check("Не .txt → ошибка",
          "только файл с расширением .txt" in rtext(r))

    big = b"a" * (1024 * 1024 + 500)
    r = post_upload(session, big, "big.txt")
    check("> 1 Мб → 'больше 1 Мб'",
          "больше 1 Мб" in rtext(r))


def test_page_texts_integrity(session, login):
    section("Проверка всех текстов страниц (golden strings, пустое состояние)")
    print(f"  Используем существующий аккаунт: {login}")

    pages = {
        "/":          None,
        "/register":  None,
        "/account":   session,
        "/files":     session,
        "/upload":    session,
        "/game":      session,
        "404":        None,
    }

    for path, sess in pages.items():
        url = f"{BASE_URL}/definitely-not-found-{secrets.token_hex(4)}" \
            if path == "404" else f"{BASE_URL}{path}"
        client = sess if sess is not None else new_session()

        try:
            r = client.get(url, timeout=TIMEOUT)
        except requests.RequestException as e:
            check(f"GET {path} — доступен", False, str(e))
            continue

        if path == "404":
            check("GET 404-страница — 404", r.status_code == 404,
                  f"status={r.status_code}")
        else:
            check(f"GET {path} — 200", r.status_code == 200,
                  f"status={r.status_code}")

        body = rtext(r)

        for needle in EXPECTED_TEXTS["_base"]:
            check(f"{path}: содержит {needle!r}", needle in body)

        for needle in EXPECTED_TEXTS.get(path, []):
            check(f"{path}: содержит {needle!r}", needle in body)


def test_upload_success_and_read(session, use_flag=False):
    """Загрузка файла + проверка ЗАГРУЖЕННОГО состояния /account и /files."""
    section("Загрузка валидного .txt и чтение")

    before = {n for n in os.listdir(HERE) if n.lower().endswith(".txt")}

    if use_flag:
        msg = generate_flag()
        check("Флаг сгенерирован", True)
        print(f"  Сгенерирован флаг: {msg}")
        print(f"  Длина: {len(msg)} символов")
    else:
        if not os.path.isfile(JSON_PATH):
            check("star_wars_messages.json найден", False,
                  f"path={JSON_PATH}")
            return
        check("star_wars_messages.json найден", True)

        try:
            with open(JSON_PATH, encoding="utf-8") as fh:
                messages = json.load(fh)
        except (OSError, json.JSONDecodeError) as e:
            check("JSON успешно прочитан", False, str(e))
            return

        check("JSON содержит непустой список",
              isinstance(messages, list) and len(messages) > 0,
              f"type={type(messages).__name__}, "
              f"len={len(messages) if isinstance(messages, list) else 'n/a'}")
        if not (isinstance(messages, list) and messages):
            return

        idx = random.randrange(len(messages))
        msg = messages[idx]
        print(f"  Выбрано сообщение №{idx + 1} из {len(messages)}")
        print(f"  Длина исходного текста: {len(msg)} символов")

    show_block("ИСХОДНЫЙ ТЕКСТ", msg)

    fd, tmp_path = tempfile.mkstemp(prefix="txtcloud_", suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(msg)
        with open(tmp_path, "rb") as fh:
            payload = fh.read()
        print(f"  Временный .txt: {tmp_path} ({len(payload)} байт)")

        r = post_upload(session, payload, "note.txt")
        check("Загрузка валидного .txt успешна",
              "Файл успешно загружен" in rtext(r),
              f"preview={rtext(r)[:160]!r}")
    finally:
        try:
            os.remove(tmp_path)
            print(f"  Временный .txt удалён: {tmp_path}")
        except OSError:
            pass

    after = {n for n in os.listdir(HERE) if n.lower().endswith(".txt")}
    check("Рядом с test.py не появились .txt",
          before == after,
          f"new={sorted(after - before)}")

    # ---- ЗАГРУЖЕННОЕ состояние /account и /files ----
    r = session.get(f"{BASE_URL}/account", timeout=TIMEOUT)
    b = rtext(r)
    check("Account: 'Файл загружен' после загрузки",
          "Файл загружен" in b)
    check("Account: появился пункт 'Прочитать файл'",
          "Прочитать файл" in b)

    r = session.get(f"{BASE_URL}/files", timeout=TIMEOUT)
    check("Files: 'Файл загружен' после загрузки",
          "Файл загружен" in rtext(r))

    # ---- Чтение /read ----
    r = session.get(f"{BASE_URL}/read", timeout=TIMEOUT)
    b = rtext(r)
    check("GET /read — 200", r.status_code == 200,
          f"status={r.status_code}")

    check("/read: содержит 'Содержимое вашего файла'",
          "Содержимое вашего файла" in b)
    check("/read: содержит '📁 К моим файлам'",
          "📁 К моим файлам" in b)
    check("/read: содержит '🏠 В кабинет'",
          "🏠 В кабинет" in b)

    m = re.search(r'<div class="note-box">(.*?)</div>', b, re.DOTALL)
    check("На /read найден <div class=\"note-box\">", m is not None)

    if m is None:
        return

    rendered_escaped = m.group(1)
    rendered = html.unescape(rendered_escaped)

    print(f"  Длина текста со страницы /read: {len(rendered)} символов")
    show_block("ТЕКСТ СО СТРАНИЦЫ /read (из <div class=\"note-box\">)",
               rendered)

    print(f"  HTML-фрагмент note-box, длина: {len(rendered_escaped)} символов")
    if len(rendered_escaped) <= 2000:
        show_block("HTML ВНУТРИ note-box", rendered_escaped)
    else:
        print("  (HTML слишком длинный, показываем первые 1000 и "
              "последние 500 символов)")
        show_block("HTML ВНУТРИ note-box (начало)",
                   rendered_escaped[:1000])
        show_block("HTML ВНУТРИ note-box (конец)",
                   rendered_escaped[-500:])

    ok_exact = rendered == msg
    check("Текст на /read СОВПАДАЕТ с исходным (посимвольно)",
          ok_exact,
          "" if ok_exact else
          f"len_rendered={len(rendered)} len_expected={len(msg)}")

    if not ok_exact:
        for i, (a, c) in enumerate(zip(rendered, msg)):
            if a != c:
                print(f"  Расхождение на позиции {i}: "
                      f"rendered={a!r}, expected={c!r}")
                lo = max(0, i - 40)
                hi = min(max(len(rendered), len(msg)), i + 40)
                show_block("ОКРЕСТНОСТЬ РАСХОЖДЕНИЯ — сайт",
                           rendered[lo:hi])
                show_block("ОКРЕСТНОСТЬ РАСХОЖДЕНИЯ — ожидалось",
                           msg[lo:hi])
                break
        else:
            print(f"  Префикс совпал, но длины разные: "
                  f"{len(rendered)} vs {len(msg)}")
            show_block("ХВОСТ (сайт, последние 200)", rendered[-200:])
            show_block("ХВОСТ (ожидалось, последние 200)", msg[-200:])


def test_logout_and_relogin(login, password):
    section("Выход и повторный вход")
    creds(login, password)

    s = new_session()
    r = do_login(s, login, password)
    check("Вход с верными данными → /account",
          "/account" in r.url, f"url={r.url}")

    r = s.get(f"{BASE_URL}/account", timeout=TIMEOUT)
    b = rtext(r)
    check("После входа /account доступен", login in b)
    check('После входа .name == логин',
          f'<div class="name">{login}</div>' in b,
          f"ожидался <div class=\"name\">{login}</div>")

    r = s.get(f"{BASE_URL}/logout",
              timeout=TIMEOUT, allow_redirects=True)
    check("Выход → flash 'Вы вышли'",
          "Вы вышли" in rtext(r))

    r = s.get(f"{BASE_URL}/account",
              allow_redirects=False, timeout=TIMEOUT)
    check("После выхода /account снова redirect",
          r.status_code == 302, f"status={r.status_code}")

    wrong = secrets.token_hex(16)
    print(f"  Неверный пароль для теста: {wrong}")
    s2 = new_session()
    r = do_login(s2, login, wrong)
    check("Неверный пароль отклонён",
          "Неверный логин или пароль" in rtext(r))

    ghost_login, ghost_pw = generate_credentials()
    print(f"  Несуществующий логин для теста: {ghost_login}")
    s3 = new_session()
    r = do_login(s3, ghost_login, ghost_pw)
    check("Несуществующий пользователь отклонён",
          "Неверный логин или пароль" in rtext(r))


# ==================== MAIN ====================
def main():
    global PASSED, FAILED
    PASSED, FAILED = [], []

    use_flag = len(sys.argv) > 1 and sys.argv[1] == "flag"

    if len(sys.argv) > 1 and sys.argv[1] not in ("flag",):
        print(f"Неизвестный аргумент: {sys.argv[1]!r}. "
              f"Использование: python3 test.py [flag]",
              file=sys.stderr)
        return 2

    print("TXT Cloud — проверка функционала запущенного сервера")
    print("=" * 60)
    print(f"BASE_URL: {BASE_URL}")
    print(f"Режим:    "
          f"{'flag (генерируется TEAM000_...)' if use_flag else 'star_wars_messages.json'}")
    print("Учётные данные генерируются функцией generate_credentials():")
    print("  логин  = 'pilot_' + 32 hex-символа (secrets.token_hex(16))")
    print("  пароль =           32 hex-символа (secrets.token_hex(16))")
    if use_flag:
        print("Пример генерируемого флага (generate_flag()):")
        print(f"  {generate_flag()}")

    if not test_server_alive():
        print("\nСервер недоступен — проверьте, что app.py запущен "
              "и адрес в TXTCLOUD_URL указан верно.")
        return 1

    # Порядок тестов согласован с состоянием аккаунта:
    #   1. Публичные страницы и защита маршрутов.
    #   2. Негативные кейсы регистрации.
    #   3. Создание ОДНОГО аккаунта.
    #   4. Проверки ПУСТОГО состояния (/account, /files, /read, /game).
    #   5. Golden-strings для ПУСТОГО состояния.
    #   6. Негативные кейсы загрузки (состояние не меняется).
    #   7. Загрузка файла → проверки ЗАГРУЖЕННОГО состояния.
    #   8. Выход / повторный вход.
    test_login_required()
    test_register_negative()
    session, login, password = test_register_success_and_duplicate()
    test_logged_in_pages(session, login)
    test_page_texts_integrity(session, login)
    test_upload_negative(session)
    test_upload_success_and_read(session, use_flag=use_flag)
    test_logout_and_relogin(login, password)

    print()
    print("=" * 60)
    total = len(PASSED) + len(FAILED)
    print(f"ИТОГО: {len(PASSED)}/{total} прошло, {len(FAILED)} провалено")
    if FAILED:
        print("\nПроваленные проверки:")
        for name, detail in FAILED:
            print(f"  - {name}" + (f"  ({detail})" if detail else ""))
    return 0 if not FAILED else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nПрервано пользователем", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        debug_log(str(e), "ERROR")
        print(f"Непредвиденная ошибка: {e}", file=sys.stderr)
        sys.exit(2)
