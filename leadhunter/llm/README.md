# LeadHunter — LLM layer

A small, pluggable LLM abstraction: one interface, one "box".

## Interface
`LLMProvider.generate(prompt, *, system=None, temperature=0.0, max_tokens=None) -> str`
plus a cheap `available()` probe used for provider selection.

## Providers
- **`OllamaProvider` (default, local, free):** talks to a local Ollama server's
  HTTP API (`http://localhost:11434` by default). Env overrides: `OLLAMA_HOST`,
  `OLLAMA_MODEL` (default `llama3.2`).
- **`HostedProvider` (free fallback):** a generic **OpenAI-compatible**
  `/chat/completions` endpoint — no vendor hard-coded. Configure via env:
  - `LLM_HOSTED_BASE_URL` (e.g. `https://openrouter.ai/api/v1`)
  - `LLM_HOSTED_MODEL`
  - `LLM_HOSTED_API_KEY`

## Selection
`get_provider(*, prefer=None, allow_network=False)`:
1. `prefer` arg or `LLM_PROVIDER` env (`ollama` | `hosted`) forces a provider.
2. Else: try local Ollama (`available()`); fall back to hosted if configured.
3. Else: raise `LLMUnavailableError` with a clear message.

## Responsible-use (fail closed)
LLM calls are network I/O — **including localhost Ollama**. Providers are
side-effect free at construction; `generate()`/`available()` refuse the network
unless created with `allow_network=True`, raising `LLMNetworkNotAllowedError`
otherwise. All HTTP goes through a single `_http_post`/`_http_get` seam, which
tests override — so the suite never makes a real call.

## Tests
Stdlib-only, hermetic:

    python -m unittest discover -s leadhunter/tests
