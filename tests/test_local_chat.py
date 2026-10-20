import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'nova_ia' / 'src'))
import local_chat
import helpers


class LocalChatTests(unittest.TestCase):
    @patch.object(local_chat, 'settings', return_value={'enabled': True, 'model': 'local-test'})
    def test_stream_and_no_api_key(self, settings):
        body = b'{"message":{"content":"Ola"},"done":false}\n{"done":true}\n'
        with patch.object(local_chat, 'request', return_value=io.BytesIO(body)) as request:
            self.assertEqual(helpers.chamar_gemini('', [{'role': 'user', 'content': 'Oi'}]), 'Ola')
            payload = request.call_args.args[1]
            self.assertEqual(payload['model'], 'local-test')
            self.assertEqual(payload['messages'][-1]['content'], 'Oi')
            self.assertNotIn('key', payload)

    @patch.object(local_chat, 'settings', return_value={'enabled': True, 'model': ''})
    def test_missing_models(self, settings):
        with patch.object(local_chat, 'models', return_value=[]):
            with self.assertRaisesRegex(RuntimeError, 'Nenhum modelo'):
                list(local_chat.chat_stream([]))

    @patch.object(local_chat, 'settings', return_value={'enabled': True, 'model': 'test'})
    def test_incomplete_stream_is_rejected(self, settings):
        with patch.object(local_chat, 'request', return_value=io.BytesIO(b'{"message":{"content":"parcial"}}\n')):
            with self.assertRaisesRegex(RuntimeError, 'não concluiu'):
                list(local_chat.chat_stream([]))
