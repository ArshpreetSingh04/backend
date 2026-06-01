"""Hermetic tests for OllamaProvider — the network seams are overridden."""

from __future__ import annotations

import json
import unittest

import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
)

from leadhunter.llm.base import LLMNetworkNotAllowedError
from leadhunter.llm.ollama_provider import OllamaProvider, DEFAULT_HOST


class _FakeOllama(OllamaProvider):
    """OllamaProvider with both HTTP seams faked; records the last POST."""

    def __init__(self, *, response_text="hi", tags_ok=True, **kwargs):
        super().__init__(**kwargs)
        self._response_text = response_text
        self._tags_ok = tags_ok
        self.last_post_url = None
        self.last_post_body = None
        self.get_called = False

    def _http_post(self, url, data):
        self.last_post_url = url
        self.last_post_body = json.loads(data.decode("utf-8"))
        return json.dumps({"response": self._response_text, "done": True})

    def _http_get(self, url):
        self.get_called = True
        if not self._tags_ok:
            raise ConnectionError("refused")
        return json.dumps({"models": []})


class OllamaProviderTests(unittest.TestCase):
    def test_generate_returns_response_field(self):
        provider = _FakeOllama(response_text="a qualified lead", allow_network=True)
        self.assertEqual(provider.generate("score this"), "a qualified lead")

    def test_generate_builds_expected_request_body(self):
        provider = _FakeOllama(allow_network=True, model="llama3.2")
        provider.generate(
            "prompt text", system="you are terse", temperature=0.2, max_tokens=128
        )
        self.assertEqual(provider.last_post_url, f"{DEFAULT_HOST}/api/generate")
        body = provider.last_post_body
        self.assertEqual(body["model"], "llama3.2")
        self.assertEqual(body["prompt"], "prompt text")
        self.assertFalse(body["stream"])
        self.assertEqual(body["system"], "you are terse")
        self.assertEqual(body["options"]["temperature"], 0.2)
        self.assertEqual(body["options"]["num_predict"], 128)

    def test_generate_fails_closed_without_opt_in(self):
        provider = _FakeOllama()  # allow_network False
        with self.assertRaises(LLMNetworkNotAllowedError):
            provider.generate("x")
        self.assertIsNone(provider.last_post_url)  # seam never reached

    def test_available_true_when_tags_ok(self):
        provider = _FakeOllama(allow_network=True, tags_ok=True)
        self.assertTrue(provider.available())
        self.assertTrue(provider.get_called)

    def test_available_false_when_tags_fail(self):
        provider = _FakeOllama(allow_network=True, tags_ok=False)
        self.assertFalse(provider.available())

    def test_available_false_without_opt_in(self):
        provider = _FakeOllama(tags_ok=True)  # allow_network False
        self.assertFalse(provider.available())
        self.assertFalse(provider.get_called)  # no probe attempted

    def test_env_overrides_host_and_model(self):
        provider = OllamaProvider(
            host="http://example:1234/", model="custom-model", allow_network=True
        )
        self.assertEqual(provider.host, "http://example:1234")
        self.assertEqual(provider.model, "custom-model")


if __name__ == "__main__":
    unittest.main()
