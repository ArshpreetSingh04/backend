"""Hermetic tests for HostedProvider — the OpenAI-compatible network seam is faked."""

from __future__ import annotations

import json
import unittest

import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
)

from leadhunter.llm.base import LLMNetworkNotAllowedError, LLMUnavailableError
from leadhunter.llm.hosted_provider import HostedProvider


class _FakeHosted(HostedProvider):
    """HostedProvider with the POST seam faked; records the last request."""

    def __init__(self, *, content="ok", **kwargs):
        super().__init__(**kwargs)
        self._content = content
        self.last_post_url = None
        self.last_post_body = None

    def _http_post(self, url, data):
        self.last_post_url = url
        self.last_post_body = json.loads(data.decode("utf-8"))
        return json.dumps(
            {"choices": [{"message": {"role": "assistant", "content": self._content}}]}
        )


_CFG = dict(base_url="https://api.example/v1", model="free-model", api_key="k-123")


class HostedProviderTests(unittest.TestCase):
    def test_generate_returns_message_content(self):
        provider = _FakeHosted(content="enriched", allow_network=True, **_CFG)
        self.assertEqual(provider.generate("do it"), "enriched")

    def test_generate_builds_openai_chat_request(self):
        provider = _FakeHosted(allow_network=True, **_CFG)
        provider.generate("user prompt", system="sys", temperature=0.5, max_tokens=64)
        self.assertEqual(provider.last_post_url, "https://api.example/v1/chat/completions")
        body = provider.last_post_body
        self.assertEqual(body["model"], "free-model")
        self.assertEqual(body["temperature"], 0.5)
        self.assertEqual(body["max_tokens"], 64)
        self.assertEqual(
            body["messages"],
            [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "user prompt"},
            ],
        )

    def test_generate_fails_closed_without_opt_in(self):
        provider = _FakeHosted(**_CFG)  # allow_network False
        with self.assertRaises(LLMNetworkNotAllowedError):
            provider.generate("x")
        self.assertIsNone(provider.last_post_url)

    def test_missing_config_raises_unavailable(self):
        provider = _FakeHosted(allow_network=True, base_url="", model="", api_key="")
        with self.assertRaises(LLMUnavailableError):
            provider.generate("x")
        self.assertIsNone(provider.last_post_url)  # no network attempted

    def test_available_reflects_configuration(self):
        self.assertTrue(HostedProvider(**_CFG).available())
        self.assertFalse(HostedProvider(base_url="", api_key="").available())


if __name__ == "__main__":
    unittest.main()
