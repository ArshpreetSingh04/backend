"""Tests for get_provider() selection logic — all availability is mocked."""

from __future__ import annotations

import unittest

import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
)

from leadhunter.llm import factory
from leadhunter.llm.base import LLMUnavailableError
from leadhunter.llm.ollama_provider import OllamaProvider
from leadhunter.llm.hosted_provider import HostedProvider


class _Env:
    """Patch factory's env-reading and availability for a single test."""

    def __init__(self, test, *, ollama_up, hosted_cfg, llm_provider_env=None):
        self.test = test
        self.ollama_up = ollama_up
        self.hosted_cfg = hosted_cfg
        self.llm_provider_env = llm_provider_env
        self._orig_environ = factory.os.environ

    def __enter__(self):
        env = {}
        if self.llm_provider_env is not None:
            env["LLM_PROVIDER"] = self.llm_provider_env
        if self.hosted_cfg:
            env["LLM_HOSTED_BASE_URL"] = "https://api.example/v1"
            env["LLM_HOSTED_API_KEY"] = "k-123"
        factory.os.environ = env
        # Force Ollama availability deterministically (no network).
        self._orig_avail = OllamaProvider.available
        up = self.ollama_up
        OllamaProvider.available = lambda self: up  # type: ignore[assignment]
        return self

    def __exit__(self, *exc):
        factory.os.environ = self._orig_environ
        OllamaProvider.available = self._orig_avail  # type: ignore[assignment]
        return False


class FactoryTests(unittest.TestCase):
    def test_default_picks_ollama_when_available(self):
        with _Env(self, ollama_up=True, hosted_cfg=True):
            provider = factory.get_provider(allow_network=True)
        self.assertIsInstance(provider, OllamaProvider)

    def test_falls_back_to_hosted_when_ollama_down(self):
        with _Env(self, ollama_up=False, hosted_cfg=True):
            provider = factory.get_provider(allow_network=True)
        self.assertIsInstance(provider, HostedProvider)

    def test_prefer_argument_forces_hosted(self):
        with _Env(self, ollama_up=True, hosted_cfg=True):
            provider = factory.get_provider(prefer="hosted", allow_network=True)
        self.assertIsInstance(provider, HostedProvider)

    def test_env_var_forces_hosted(self):
        with _Env(self, ollama_up=True, hosted_cfg=True, llm_provider_env="hosted"):
            provider = factory.get_provider(allow_network=True)
        self.assertIsInstance(provider, HostedProvider)

    def test_unknown_prefer_raises(self):
        with _Env(self, ollama_up=True, hosted_cfg=True):
            with self.assertRaises(LLMUnavailableError):
                factory.get_provider(prefer="bogus", allow_network=True)

    def test_no_provider_available_raises(self):
        with _Env(self, ollama_up=False, hosted_cfg=False):
            with self.assertRaises(LLMUnavailableError):
                factory.get_provider(allow_network=True)


if __name__ == "__main__":
    unittest.main()
