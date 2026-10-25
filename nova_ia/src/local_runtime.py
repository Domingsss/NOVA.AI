"""Inicializa o servidor local sob demanda, sem abrir a interface do Ollama."""
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request

from integrations import DATA_DIR

URL = 'http://127.0.0.1:11434'
RUNTIME_DIR = DATA_DIR / 'ollama'
_lock = threading.Lock()
_process = None


def executable():
    candidates = [
        os.environ.get('NOVA_OLLAMA_EXE'),
        RUNTIME_DIR / 'bin' / ('ollama.exe' if os.name == 'nt' else 'ollama'),
        shutil.which('ollama'),
        Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'Programs' / 'Ollama' / 'ollama.exe',
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise RuntimeError('Ollama não instalado. Execute scripts/setup_ollama.ps1 na pasta da NOVA.')


def environment():
    env = os.environ.copy()
    for name, folder in [('OLLAMA_MODELS', 'models'), ('TEMP', 'tmp'), ('TMP', 'tmp'), ('HOME', 'home'), ('USERPROFILE', 'home')]:
        path = RUNTIME_DIR / folder
        path.mkdir(parents=True, exist_ok=True)
        env[name] = str(path)
    env['OLLAMA_HOST'] = '127.0.0.1:11434'
    return env


def available():
    try:
        with urllib.request.urlopen(URL + '/api/version', timeout=1) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError):
        return False


def ensure_running(timeout=45):
    global _process
    if available():
        return
    with _lock:
        if available():
            return
        if _process is None or _process.poll() is not None:
            binary = executable()
            env = environment()
            with (RUNTIME_DIR / 'server.log').open('ab') as log:
                try:
                    _process = subprocess.Popen(
                        [binary, 'serve'], env=env, cwd=str(RUNTIME_DIR),
                        stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                    )
                except OSError as error:
                    raise RuntimeError('Não foi possível iniciar o Ollama local.') from error
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if available():
                return
            if _process.poll() is not None:
                raise RuntimeError('Ollama encerrou ao iniciar. Consulte nova_ia/data/ollama/server.log.')
            time.sleep(0.25)
        raise RuntimeError('Ollama ainda está iniciando. Aguarde e tente novamente.')
