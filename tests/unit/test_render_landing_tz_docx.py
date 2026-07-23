import importlib.util
from pathlib import Path


def load_renderer():
    script = Path(__file__).parents[2] / "scripts" / "render_landing_tz_docx.py"
    spec = importlib.util.spec_from_file_location("render_landing_tz_docx", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ordered_item_text_supports_multi_digit_prefixes() -> None:
    renderer = load_renderer()

    assert renderer.ordered_item_text("1. Главная") == "Главная"
    assert renderer.ordered_item_text("10. **Блог**") == "**Блог**"


def test_ordered_item_text_rejects_plain_text() -> None:
    renderer = load_renderer()

    assert renderer.ordered_item_text("Главная") is None
