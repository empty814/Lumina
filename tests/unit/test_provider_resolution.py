from types import SimpleNamespace
from unittest.mock import patch


def _cfg(provider_type: str = "local"):
    return SimpleNamespace(
        provider=SimpleNamespace(
            type=provider_type,
            model_path="/tmp/local-model",
            llama_cpp=SimpleNamespace(model_path="/tmp/local-model.gguf", n_gpu_layers=12, n_ctx=4096),
            openai=SimpleNamespace(base_url="http://example.com/v1", api_key="k", model="m"),
        )
    )


def test_build_provider_routes_local_to_llama_cpp_when_backend_resolves(monkeypatch):
    from lumina.cli import server as server_mod

    class FakeProvider:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(server_mod, "logger", server_mod.logger)
    with patch("lumina.platform_support.runtime.resolve_provider_backend", return_value="llama_cpp"), \
         patch("lumina.providers.llama_cpp.LlamaCppProvider", FakeProvider):
        provider = server_mod.build_provider(_cfg("local"))

    assert isinstance(provider, FakeProvider)
    assert provider.kwargs["model_path"] == "/tmp/local-model.gguf"


def test_build_provider_routes_openai_normally():
    from lumina.cli import server as server_mod

    class FakeProvider:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    with patch("lumina.platform_support.runtime.resolve_provider_backend", return_value="openai"), \
         patch("lumina.providers.openai.OpenAIProvider", FakeProvider):
        provider = server_mod.build_provider(_cfg("openai"))

    assert isinstance(provider, FakeProvider)
    assert provider.kwargs["base_url"] == "http://example.com/v1"
