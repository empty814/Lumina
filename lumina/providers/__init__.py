from .base import BaseProvider

__all__ = ["BaseProvider", "LocalProvider", "LlamaCppProvider", "OpenAIProvider"]


def __getattr__(name: str):
    # 惰性导入：只在真正需要时拉取 native extension（mlx 等）
    if name == "LocalProvider":
        from .local import LocalProvider
        return LocalProvider
    if name == "LlamaCppProvider":
        from .llama_cpp import LlamaCppProvider
        return LlamaCppProvider
    if name == "OpenAIProvider":
        from .openai import OpenAIProvider
        return OpenAIProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
