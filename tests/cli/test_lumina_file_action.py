import importlib.util
from pathlib import Path


_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "lumina_file_action.py"
_SPEC = importlib.util.spec_from_file_location("lumina_file_action", _SCRIPT_PATH)
lumina_file_action = importlib.util.module_from_spec(_SPEC)
assert _SPEC is not None and _SPEC.loader is not None
_SPEC.loader.exec_module(lumina_file_action)


def test_detect_polish_language_for_readme():
    lang = lumina_file_action.detect_polish_language(Path("/tmp/README.md"))
    assert lang == "en"


def test_detect_polish_language_for_en_suffix():
    lang = lumina_file_action.detect_polish_language(Path("/tmp/notes-en.txt"))
    assert lang == "en"


def test_detect_polish_language_defaults_to_zh():
    lang = lumina_file_action.detect_polish_language(Path("/tmp/notes.txt"))
    assert lang == "zh"
