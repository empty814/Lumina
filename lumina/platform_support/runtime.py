"""
lumina/platform_support/runtime.py — 运行时平台与本地模型默认策略。

把「本地 provider 在不同平台映射到什么实现」和默认模型路径集中在这里，
避免配置加载、启动流程、provider 构造各写一套平台判断。
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

IS_MACOS = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

DEFAULT_PROVIDER_TYPE = "local"
VALID_PROVIDER_TYPES = {"local", "llama_cpp", "openai"}

DEFAULT_MLX_MODEL_REPO_ID = "mlx-community/Qwen3.5-0.8B-4bit"
DEFAULT_MLX_MODEL_DIRNAME = "qwen3.5-0.8b-4bit"
DEFAULT_MLX_MODEL_PATH = Path.home() / ".lumina" / "models" / DEFAULT_MLX_MODEL_DIRNAME

# 非 macOS 的本地后端统一走 llama.cpp。选一个体积小、CPU 也能跑的默认 GGUF。
DEFAULT_GGUF_MODEL_REPO_ID = "Qwen/Qwen2.5-0.5B-Instruct-GGUF"
DEFAULT_GGUF_MODEL_FILENAME = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
DEFAULT_GGUF_MODEL_PATH = Path.home() / ".lumina" / "models" / DEFAULT_GGUF_MODEL_FILENAME

DEFAULT_MLX_WHISPER_MODEL = "mlx-community/whisper-tiny-mlx-4bit"
DEFAULT_FASTER_WHISPER_MODEL = "tiny"


@dataclass(frozen=True)
class ModelDownloadSpec:
    backend: str
    repo_id: str
    local_path: Path
    filename: str | None = None


def normalize_provider_type(value: str | None) -> str:
    provider_type = (value or DEFAULT_PROVIDER_TYPE).strip().lower()
    if provider_type not in VALID_PROVIDER_TYPES:
        raise ValueError(
            f"Unsupported provider.type={provider_type!r}; "
            f"expected one of {sorted(VALID_PROVIDER_TYPES)}"
        )
    return provider_type


def resolve_provider_backend(provider_type: str | None) -> str:
    """将用户语义上的 provider.type 映射到底层实现。"""
    normalized = normalize_provider_type(provider_type)
    if normalized == "openai":
        return "openai"
    if normalized == "llama_cpp":
        return "llama_cpp"
    return "mlx" if IS_MACOS else "llama_cpp"


def default_provider_model_path(provider_type: str | None = None) -> str:
    backend = resolve_provider_backend(provider_type)
    if backend == "mlx":
        return str(DEFAULT_MLX_MODEL_PATH)
    if backend == "llama_cpp":
        return str(DEFAULT_GGUF_MODEL_PATH)
    return ""


def default_whisper_model() -> str:
    return DEFAULT_MLX_WHISPER_MODEL if IS_MACOS else DEFAULT_FASTER_WHISPER_MODEL


def resolve_whisper_model(value: str | None) -> str:
    """空值和旧版 macOS 默认值在非 macOS 上都收敛到跨平台默认。"""
    model = (value or "").strip()
    if not model:
        return default_whisper_model()
    if not IS_MACOS and model == DEFAULT_MLX_WHISPER_MODEL:
        return DEFAULT_FASTER_WHISPER_MODEL
    return model


def resolve_local_model_path(value: str | None, provider_type: str | None) -> str:
    model_path = (value or "").strip()
    if not model_path:
        return default_provider_model_path(provider_type)

    backend = resolve_provider_backend(provider_type)
    if backend == "llama_cpp" and model_path == str(DEFAULT_MLX_MODEL_PATH):
        return str(DEFAULT_GGUF_MODEL_PATH)
    return model_path


def get_local_model_download_spec(provider_type: str | None) -> ModelDownloadSpec | None:
    backend = resolve_provider_backend(provider_type)
    if backend == "openai":
        return None
    if backend == "mlx":
        return ModelDownloadSpec(
            backend="mlx",
            repo_id=DEFAULT_MLX_MODEL_REPO_ID,
            local_path=DEFAULT_MLX_MODEL_PATH,
        )
    return ModelDownloadSpec(
        backend="llama_cpp",
        repo_id=DEFAULT_GGUF_MODEL_REPO_ID,
        local_path=DEFAULT_GGUF_MODEL_PATH,
        filename=DEFAULT_GGUF_MODEL_FILENAME,
    )
