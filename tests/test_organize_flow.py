"""Drive the Organize tab from a node structure to a validated plan."""

from tests import tk_stub

tk_stub.install()

import datetime  # noqa: E402
import tkinter as tk  # noqa: E402

from strucnode.core import executor  # noqa: E402
from strucnode.ui.nodes.editor_tab import NodeEditorTab  # noqa: E402
from strucnode.ui.organize_tab import OrganizeTab  # noqa: E402


def _files(tmp_path, names=("a.jpg",)):
    when = datetime.datetime(2024, 5, 4)
    files = []
    for name in names:
        path = tmp_path / name
        path.write_bytes(b"12345")
        files.append({"path": str(path), "name": name, "ext": ".jpg",
                      "size_bytes": 5, "mtime_ts": 0.0, "meta": {},
                      "_mtime": when, "_ctime": when})
    return files


def _wired(tmp_path, names=("a.jpg",)):
    editor = NodeEditorTab(tk.Frame(), lambda: _files(tmp_path, names))
    editor._add_argument_node("annee_modif")
    tab = OrganizeTab(tk.Frame(), lambda: editor)
    return editor, tab


def test_loading_a_structure_produces_a_plan(tmp_path):
    editor, tab = _wired(tmp_path)
    files = editor._get_files()
    tab._on_structure_ready(editor.get_structure_for_files(files),
                            "Year", files)

    tab._dest_var.set(str(tmp_path / "dest"))
    tab._refresh_ops(tab._tree, tab._dest_var.get())

    assert len(tab._ops) == 1
    assert tab._plan.unmatched == []
    assert "2024" in tab._ops[0][1]


def test_the_plan_reports_a_same_destination_collision(tmp_path):
    src_a = tmp_path / "one"
    src_b = tmp_path / "two"
    for folder in (src_a, src_b):
        folder.mkdir()
        (folder / "IMG_1.jpg").write_bytes(b"x")

    when = datetime.datetime(2024, 5, 4)
    files = [{"path": str(folder / "IMG_1.jpg"), "name": "IMG_1.jpg",
              "ext": ".jpg", "size_bytes": 1, "mtime_ts": 0.0, "meta": {},
              "_mtime": when, "_ctime": when} for folder in (src_a, src_b)]

    editor = NodeEditorTab(tk.Frame(), lambda: files)
    editor._add_argument_node("annee_modif")
    tab = OrganizeTab(tk.Frame(), lambda: editor)
    tab._on_structure_ready(editor.get_structure_for_files(files), "Year", files)
    tab._refresh_ops(tab._tree, str(tmp_path / "dest"))

    assert len(tab._plan.internal_collisions) == 2
    tab._dup_mode.set(executor.RENAME)
    assert tab._collision_strategy() == executor.RENAME


def test_a_destination_inside_the_source_is_refused(tmp_path):
    photos = tmp_path / "photos"
    photos.mkdir()
    editor, tab = _wired(photos)
    files = editor._get_files()
    tab._on_structure_ready(editor.get_structure_for_files(files), "Year", files)
    tab._refresh_ops(tab._tree, str(photos / "sorted"))

    assert tab._confirm_run(str(photos / "sorted")) is False


def test_running_the_plan_moves_the_files(tmp_path):
    editor, tab = _wired(tmp_path, names=("a.jpg", "b.jpg"))
    files = editor._get_files()
    tab._on_structure_ready(editor.get_structure_for_files(files), "Year", files)
    dest = tmp_path / "dest"
    tab._refresh_ops(tab._tree, str(dest))

    result = executor.run(tab._ops, executor.COPY, journal=False)
    assert result.done == 2 and not result.errors
    assert sorted(p.name for p in (dest / "2024").iterdir()) == ["a.jpg", "b.jpg"]
