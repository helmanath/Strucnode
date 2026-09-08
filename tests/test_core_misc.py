"""Categories, size formatting, field resolution, scanning, dedupe, presets."""

import datetime
import os

import pytest

from strucnode import config, i18n
from strucnode.core import dedupe, fields, scanner
from strucnode.core.categories import category_label, fmt_size, get_category


@pytest.mark.parametrize("ext, expected", [
    (".JPG", "images"), (".cr2", "images"), (".mp4", "videos"),
    (".py", "code"), (".zzz", "other"), ("", "other"),
])
def test_get_category(ext, expected):
    assert get_category(ext) == expected


def test_fmt_size_follows_the_locale():
    assert fmt_size(1536) == "1.5 KB"
    i18n.set_locale("fr")
    assert fmt_size(1536) == "1.5 Ko"


def test_category_label_follows_the_locale():
    assert category_label("videos") == "Videos"
    i18n.set_locale("fr")
    assert category_label("videos") == "Vidéos"


def _entry(name="IMG_0042.CR2", size=5_000_000, when=datetime.datetime(2024, 3, 7)):
    return {"path": f"/src/{name}", "name": name,
            "ext": os.path.splitext(name)[1].lower(),
            "size_bytes": size, "_mtime": when, "_ctime": when}


@pytest.mark.parametrize("resolver, expected", [
    ("year_mtime", "2024"),
    ("month_mtime", "03"),
    ("day_mtime", "07"),
    ("ext", "CR2"),
    ("category", "Images"),
    ("first_letter", "I"),
    ("filename_noext", "IMG_0042"),
    ("size_range", "1MB-10MB"),
    ("unknown_resolver", fields.UNRESOLVED),
])
def test_resolve(resolver, expected):
    assert fields.resolve(_entry(), resolver) == expected


@pytest.mark.parametrize("size, expected", [
    (10, "0-100KB"), (500_000, "100KB-1MB"), (5_000_000, "1MB-10MB"),
    (50_000_000, "10MB-100MB"), (500_000_000, "100MB+"),
])
def test_size_buckets_are_path_safe(size, expected):
    value = fields.resolve(_entry(size=size), "size_range")
    assert value == expected
    assert not set(value) & set('<>:"/\\|?*')


def test_field_labels_follow_the_locale():
    assert fields.label("exif_annee") != fields.FIELDS["exif_annee"].label_key
    english = fields.label("annee_creation")
    i18n.set_locale("fr")
    assert fields.label("annee_creation") != english


def test_scan_indexes_a_tree(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.jpg").write_bytes(b"12345")
    (tmp_path / "sub" / "b.txt").write_text("hello")

    result = scanner.scan(str(tmp_path))
    assert result.total_files == 2
    assert result.total_dirs == 1
    assert result.total_size == 10
    assert {f["name"] for f in result.files} == {"a.jpg", "b.txt"}
    assert {f["ext"] for f in result.files} == {".jpg", ".txt"}
    assert "images" in result.by_category and "docs" in result.by_category


def test_scan_stores_raw_values_only(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"x")
    entry = scanner.scan(str(tmp_path)).files[0]
    assert "size" not in entry and "mtime" not in entry
    assert isinstance(entry["size_bytes"], int)
    assert isinstance(entry["mtime_ts"], float)


def test_scan_can_be_cancelled(tmp_path):
    import threading
    for i in range(5):
        (tmp_path / f"{i}.jpg").write_bytes(b"x")
    cancel = threading.Event()
    cancel.set()
    result = scanner.scan(str(tmp_path), cancel=cancel)
    assert result.cancelled


def test_files_without_an_extension_get_a_localized_label(tmp_path):
    (tmp_path / "README").write_text("x")
    assert scanner.scan(str(tmp_path)).files[0]["ext"] == "(no extension)"


def test_dedupe(tmp_path):
    a, b, c = tmp_path / "a", tmp_path / "b", tmp_path / "c"
    a.write_bytes(b"same")
    b.write_bytes(b"same")
    c.write_bytes(b"different")
    assert dedupe.equal_full(str(a), str(b))
    assert not dedupe.equal_full(str(a), str(c))
    assert not dedupe.equal_full(str(a), str(tmp_path / "missing"))


def test_settings_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("STRUCNODE_HOME", str(tmp_path))
    settings = config.load_settings()
    settings["locale"] = "fr"
    settings["ignored_key"] = "dropped"
    config.save_settings(settings)
    assert config.load_settings()["locale"] == "fr"
    assert "ignored_key" not in config.load_settings()


def test_presets_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("STRUCNODE_HOME", str(tmp_path))
    from strucnode.ui.nodes.presets import PresetStore

    store = PresetStore()
    store.save("Vacances 2024", {"nodes": [], "connections": [], "next_id": 1})
    assert store.names() == ["Vacances 2024"]
    assert store.load("Vacances 2024")["version"] == 1
    assert store.delete("Vacances 2024")
    assert store.names() == []


def test_preset_names_cannot_escape_the_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("STRUCNODE_HOME", str(tmp_path))
    from strucnode.ui.nodes.presets import PresetStore

    store = PresetStore()
    path = store.path_for("../../evil")
    assert path.parent == store.directory()
