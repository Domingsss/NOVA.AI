import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "nova_ia" / "src"))
import integrations


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.patch = patch.object(integrations, "SETTINGS_FILE", Path(self.temp.name) / "apis.json")
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_secret_preserved_hidden_and_explicitly_removed(self):
        integrations.save_integration({"name": "Teste", "category": "imagens", "key": "segredo"})
        public = integrations.list_integrations()[0]
        self.assertNotIn("key", public)
        self.assertTrue(public["has_key"])
        integrations.save_integration(dict(public, name="Alterado", key=""))
        self.assertEqual(integrations._read()[0]["key"], "segredo")
        integrations.save_integration(dict(public, clear_key=True))
        self.assertFalse(integrations.list_integrations()[0]["has_key"])
        integrations.delete_integration(public["id"])
        self.assertEqual(integrations.list_integrations(), [])

    def test_multiple_services_and_invalid_input(self):
        for category in ("respostas", "imagens", "videos"):
            integrations.save_integration({"name": category, "category": category})
        self.assertEqual(len(integrations.list_integrations()), 3)
        for url in ("file:///tmp/key", "https://user:password@example.com", "inválido"):
            with self.assertRaises(ValueError):
                integrations.save_integration({"name": "Teste", "category": "videos", "url": url})
        self.assertEqual(len(integrations.list_integrations()), 3)

    def test_corrupt_file_is_not_overwritten(self):
        integrations.SETTINGS_FILE.write_text("invalid", encoding="utf-8")
        with self.assertRaises(ValueError):
            integrations.save_integration({"name": "Teste", "category": "videos"})
        self.assertEqual(integrations.SETTINGS_FILE.read_text(), "invalid")
