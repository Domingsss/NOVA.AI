"""Cadastro local de serviços para integrações futuras."""
import json
import os
import sys
import threading
import uuid
from pathlib import Path
from urllib.parse import urlsplit

DATA_DIR = (Path(sys.executable).parent if getattr(sys, "frozen", False)
            else Path(__file__).resolve().parent.parent) / "data"
SETTINGS_FILE = DATA_DIR / "integrations.json"
_lock = threading.Lock()
CATEGORIES = {"respostas", "imagens", "videos"}


def _read():
    if not SETTINGS_FILE.exists():
        return []
    return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))


def _write(items):
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = SETTINGS_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, SETTINGS_FILE)


def list_integrations():
    with _lock:
        return [{k: v for k, v in item.items() if k != "key"} |
                {"has_key": bool(item.get("key"))} for item in _read()]


def save_integration(data):
    if not isinstance(data, dict):
        raise ValueError("Cadastro inválido.")
    fields = {}
    for name in ("id", "name", "category", "url", "model", "key"):
        value = data.get(name, "")
        if not isinstance(value, str) or len(value) > 4096:
            raise ValueError("Campo inválido: " + name)
        fields[name] = value.strip()
    if not fields["name"] or fields["category"] not in CATEGORIES:
        raise ValueError("Informe o nome e a finalidade da API.")
    if fields["url"]:
        url = urlsplit(fields["url"])
        if url.scheme not in ("https", "http") or not url.hostname or url.username or url.password:
            raise ValueError("Informe um endereço HTTP ou HTTPS sem credenciais.")
    with _lock:
        items = _read()
        previous = next((i for i in items if i["id"] == fields["id"]), None)
        if fields["id"] and previous is None:
            raise ValueError("API não encontrada. Atualize a lista.")
        fields["id"] = fields["id"] or uuid.uuid4().hex
        fields["key"] = ("" if data.get("clear_key") is True else
                         fields["key"] or (previous or {}).get("key", ""))
        items = [i for i in items if i["id"] != fields["id"]]
        items.append(fields)
        _write(items)


def delete_integration(identifier):
    with _lock:
        items = _read()
        _write([i for i in items if i["id"] != identifier])
