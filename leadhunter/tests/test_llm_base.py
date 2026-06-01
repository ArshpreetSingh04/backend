"""Tests for the LLMProvider abstraction and its fail-closed network guard."""

from __future__ import annotations

import unittest

import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
)

from leadhunter.llm.base import (
    LLMProvider,
    LLMNetworkNotAllowedError,
)


class _EchoProvider(LLMProvider):
    """Minimal concrete provider: requires network, echoes the prompt."""

    name = "echo"

    def generate(self, prompt, *, system=None, temperature=0.0, max_tokens=None):
        self._require_network()
        return prompt


class LLMBaseTests(unittest.TestCase):
    def test_abc_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            LLMProvider()  # type: ignore[abstract]

    def test_generate_fails_closed_without_opt_in(self):
        provider = _EchoProvider()  # allow_network defaults to False
        with self.assertRaises(LLMNetworkNotAllowedError):
            provider.generate("hello")

    def test_generate_runs_with_opt_in(self):
        provider = _EchoProvider(allow_network=True)
        self.assertEqual(provider.generate("hello"), "hello")

    def test_available_defaults_to_false(self):
        self.assertFalse(_EchoProvider(allow_network=True).available())


if __name__ == "__main__":
    unittest.main()
