import pytest

from lumina.platform_support import runtime as runtime_mod


@pytest.fixture(autouse=True)
def restore_platform_flags(monkeypatch):
    monkeypatch.setattr(runtime_mod, "IS_MACOS", False)
    monkeypatch.setattr(runtime_mod, "IS_WINDOWS", False)
    monkeypatch.setattr(runtime_mod, "IS_LINUX", True)


def test_local_provider_maps_to_llama_cpp_on_non_macos():
    assert runtime_mod.resolve_provider_backend("local") == "llama_cpp"


def test_local_provider_maps_to_mlx_on_macos(monkeypatch):
    monkeypatch.setattr(runtime_mod, "IS_MACOS", True)
    monkeypatch.setattr(runtime_mod, "IS_LINUX", False)
    assert runtime_mod.resolve_provider_backend("local") == "mlx"


def test_openai_has_no_local_model_download():
    assert runtime_mod.get_local_model_download_spec("openai") is None


def test_llama_cpp_default_model_path_is_gguf():
    assert runtime_mod.default_provider_model_path("llama_cpp").endswith(".gguf")


def test_non_macos_whisper_default_is_portable():
    assert runtime_mod.resolve_whisper_model(runtime_mod.DEFAULT_MLX_WHISPER_MODEL) == "tiny"
