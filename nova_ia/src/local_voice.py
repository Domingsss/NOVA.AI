"""Transcrição e síntese locais. Nenhuma chamada a APIs de inferência."""
import base64
import io
import threading
import wave
from integrations import DATA_DIR

_lock = threading.Lock()
_whisper = None
_piper = None
VOICE = DATA_DIR / 'models' / 'pt_BR-faber-medium.onnx'


def transcribe(audio_b64):
    raw = base64.b64decode(audio_b64, validate=True)
    if not raw or len(raw) > 15 * 1024 * 1024:
        raise ValueError('Envie uma gravação de até 15 MB.')
    with _lock:
        global _whisper
        if _whisper is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as error:
                raise RuntimeError('Instale requirements-ai-local.txt para usar voz local.') from error
            model = DATA_DIR / 'models' / 'whisper-small'
            if not model.is_dir():
                raise RuntimeError('Baixe os modelos com scripts/setup_local_ai.py primeiro.')
            _whisper = WhisperModel(str(model), device='cpu', compute_type='int8', local_files_only=True)
        segments, _ = _whisper.transcribe(io.BytesIO(raw), language='pt', vad_filter=True)
        return ' '.join(segment.text.strip() for segment in segments).strip()


def synthesize(text):
    if not isinstance(text, str) or not text.strip() or len(text) > 6000:
        raise ValueError('A fala precisa ter entre 1 e 6000 caracteres.')
    with _lock:
        global _piper
        if _piper is None:
            if not VOICE.is_file() or not VOICE.with_suffix('.onnx.json').is_file():
                raise RuntimeError('Voz Piper não instalada. Execute scripts/setup_local_ai.py.')
            try:
                from piper import PiperVoice
            except ImportError as error:
                raise RuntimeError('Instale requirements-ai-local.txt para usar Piper.') from error
            _piper = PiperVoice.load(str(VOICE))
        output = io.BytesIO()
        with wave.open(output, 'wb') as wav:
            _piper.synthesize_wav(text.strip(), wav)
        return 'data:audio/wav;base64,' + base64.b64encode(output.getvalue()).decode('ascii')
