"""Cliente do Ollama local, sem chaves de serviços externos."""
import json
import urllib.error
import urllib.request
from integrations import DATA_DIR
from config import SYSTEM_PROMPT

SETTINGS = DATA_DIR / 'local_chat.json'
URL = 'http://127.0.0.1:11434'


def settings():
    if SETTINGS.exists():
        return json.loads(SETTINGS.read_text(encoding='utf-8'))
    return {'enabled': False, 'model': ''}


def configure(enabled, model):
    if not isinstance(enabled, bool) or not isinstance(model, str):
        raise ValueError('Configuração inválida.')
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    temp = SETTINGS.with_suffix('.tmp')
    temp.write_text(json.dumps({'enabled': enabled, 'model': model.strip()}), encoding='utf-8')
    temp.replace(SETTINGS)


def request(path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(URL + path, data=data, headers={'Content-Type': 'application/json'})
    try:
        return urllib.request.urlopen(req, timeout=180 if payload else 5)
    except urllib.error.HTTPError as error:
        raise RuntimeError('Ollama recusou a solicitação. Confira o modelo instalado e o suporte a imagens.') from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError('Ollama local indisponível. Abra o Ollama no computador e tente novamente.') from error


def models():
    with request('/api/tags') as response:
        return [item['name'] for item in json.load(response).get('models', [])]


def chat_stream(history, system_prompt=SYSTEM_PROMPT):
    model = settings().get('model')
    if not model:
        installed = models()
        if not installed:
            raise RuntimeError('Nenhum modelo instalado no Ollama. Instale um modelo e selecione-o nas Configurações.')
        model = installed[0]
    messages = [{'role': 'system', 'content': system_prompt}]
    for item in history:
        content = item.get('content', '')
        message = {'role': item['role'], 'content': content}
        if isinstance(content, list):
            message['content'] = '\n'.join(p.get('text', '') for p in content if p.get('type') == 'text')
            message['images'] = []
            for part in content:
                if part.get('type') == 'image_url':
                    url = part['image_url']['url']
                    if not url.startswith('data:') or ',' not in url:
                        raise ValueError('Envie a imagem como arquivo local.')
                    message['images'].append(url.split(',', 1)[1])
                elif part.get('type') != 'text':
                    raise ValueError('Esse tipo de conteúdo não é suportado pelo chat local.')
        messages.append(message)
    complete = False
    has_text = False
    try:
        with request('/api/chat', {'model': model, 'messages': messages, 'stream': True}) as response:
            for line in response:
                if not line.strip():
                    continue
                event = json.loads(line)
                if event.get('error'):
                    raise RuntimeError('Ollama: ' + str(event['error']))
                text = event.get('message', {}).get('content', '')
                if text:
                    has_text = True
                    yield text
                if event.get('done'):
                    complete = True
                    break
    except TimeoutError as error:
        raise RuntimeError('Ollama demorou demais para responder. Tente um modelo menor.') from error
    if not complete or not has_text:
        raise RuntimeError('Ollama não concluiu uma resposta de texto. Tente novamente.')
