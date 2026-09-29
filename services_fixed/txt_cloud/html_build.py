import json
import os

from flask import current_app
from jinja2 import ChoiceLoader, DictLoader

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, "templates.json"), encoding="utf-8") as fh:
    _REGISTRY = json.load(fh)

def _ensure_loader(app):
    if getattr(app, "_txtcloud_loader_installed", False):
        return
    app.jinja_env.loader = ChoiceLoader([
        DictLoader({name: entry["html"] for name, entry in _REGISTRY.items()}),
        app.jinja_env.loader,
    ])
    app._txtcloud_loader_installed = True

def build_page(name, **ctx):
    app = current_app
    _ensure_loader(app)

    entry = _REGISTRY[name]
    tpl_src = entry["html"]

    rendered = app.jinja_env.from_string(tpl_src).render(**ctx)

    for key in entry.get("raw", ()):
        if key in ctx:
            rendered = rendered.replace(f"%%{key}%%", str(ctx[key]))

    return rendered
