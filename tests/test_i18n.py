"""The catalogs must stay in sync, and bound widgets must actually refresh."""

import ast
import json
import re
from pathlib import Path

import pytest

from strucnode import i18n

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "strucnode"
FORMAT_FIELD = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)")


def catalog(lang):
    return json.loads((PACKAGE / "i18n" / "locales" / f"{lang}.json")
                      .read_text(encoding="utf-8"))


def test_locales_define_the_same_keys():
    en, fr = catalog("en"), catalog("fr")
    assert set(en) == set(fr), (
        f"only in en: {sorted(set(en) - set(fr))}; "
        f"only in fr: {sorted(set(fr) - set(en))}")


@pytest.mark.parametrize("key", sorted(catalog("en")))
def test_translations_take_the_same_format_fields(key):
    en_fields = set(FORMAT_FIELD.findall(catalog("en")[key]))
    fr_fields = set(FORMAT_FIELD.findall(catalog("fr")[key]))
    assert en_fields == fr_fields


def _keys_used_in_code():
    """Every literal key passed to t(), tr() or tr_var() across the package."""
    used = set()
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id == "t" and node.args:
                arg = node.args[0]
            elif node.func.id in ("tr", "tr_var") and len(node.args) >= 2:
                arg = node.args[1]
            else:
                continue
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                used.add(arg.value)
    return used


def test_every_key_used_in_code_is_defined():
    missing = sorted(_keys_used_in_code() - set(catalog("en")))
    assert not missing, f"keys used but never defined: {missing}"


def test_t_falls_back_to_the_key_and_records_it():
    assert i18n.t("nope_not_a_key") == "nope_not_a_key"
    assert "nope_not_a_key" in i18n.missing_keys()


def test_bound_widget_follows_the_locale():
    class FakeWidget:
        text = None

        def configure(self, text):
            self.text = text

    widget = FakeWidget()
    i18n.tr(widget, "analyze")
    assert widget.text == "Analyze"
    i18n.set_locale("fr")
    assert widget.text == "Analyser"


def test_set_raw_drops_the_binding():
    class FakeVar:
        value = None

        def set(self, value):
            self.value = value

    var = FakeVar()
    i18n.tr_var(var, "analyze")
    i18n.set_raw(var, "/home/photos")
    i18n.set_locale("fr")
    assert var.value == "/home/photos"


def test_bindings_are_released_when_the_widget_dies():
    class FakeWidget:
        def configure(self, text):
            pass

    before = i18n.binding_count()
    widget = FakeWidget()
    i18n.tr(widget, "analyze")
    assert i18n.binding_count() == before + 1
    del widget
    import gc

    gc.collect()
    assert i18n.binding_count() == before


def test_every_category_has_a_label():
    """`category_label` builds its key with an f-string, so the AST scan above
    cannot see it. Check the catalog covers every category explicitly."""
    from strucnode.core.categories import CATEGORIES

    en = catalog("en")
    missing = [cat for cat in CATEGORIES if f"cat_{cat}" not in en]
    assert not missing, f"categories without a label: {missing}"


def test_every_field_label_key_exists():
    from strucnode.core.fields import FIELDS, PALETTE_SECTIONS

    en = catalog("en")
    assert not [f.label_key for f in FIELDS.values() if f.label_key not in en]
    assert not [key for key, _ in PALETTE_SECTIONS if key not in en]


def test_every_metadata_label_key_exists():
    from strucnode.core.metadata import FIELD_LABELS

    en = catalog("en")
    assert not [key for key in FIELD_LABELS.values() if key not in en]


def test_is_bound_distinguishes_placeholder_from_data():
    class FakeVar:
        value = None

        def set(self, value):
            self.value = value

    var = FakeVar()
    i18n.tr_var(var, "no_folder")
    assert i18n.is_bound(var)
    i18n.set_raw(var, "/home/photos")
    assert not i18n.is_bound(var)
