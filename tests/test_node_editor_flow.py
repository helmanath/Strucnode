"""Drive the node editor the way a user does: place nodes, wire them, resolve.

The canvas interactions are the part no other test reaches, and the part the
refactor moved the most.
"""

from tests import tk_stub

tk_stub.install()

import datetime  # noqa: E402
import tkinter as tk  # noqa: E402

from strucnode import i18n  # noqa: E402
from strucnode.core.tree import flatten_to_operations  # noqa: E402
from strucnode.ui.nodes.editor_tab import NodeEditorTab  # noqa: E402


def _files():
    when = datetime.datetime(2024, 5, 4)
    return [{"path": "/src/a.jpg", "name": "a.jpg", "ext": ".jpg",
             "size_bytes": 10, "mtime_ts": 0.0, "meta": {},
             "_mtime": when, "_ctime": when}]


def _editor(files=None):
    return NodeEditorTab(tk.Frame(), lambda: files if files is not None else _files())


def test_adding_nodes_updates_the_status():
    editor = _editor()
    editor._add_argument_node("annee_modif")
    editor._add_folder_node()
    assert len(editor._nodes) == 2


def test_a_chain_of_arguments_resolves_to_a_tree():
    editor = _editor()
    editor._add_argument_node("annee_modif")
    editor._add_argument_node("mois_modif")
    first, second = sorted(editor._nodes)
    editor._connections.append(
        {"src": first, "dst": second, "ctype": "chain", "cid": None})

    tree, labels, files = editor.get_structure()
    assert tree == {"2024": {"05": files}}
    assert len(labels) == 2


def test_a_folder_node_names_itself_from_its_name_port():
    editor = _editor()
    editor._add_folder_node()
    editor._add_argument_node("annee_modif")
    folder = min(editor._nodes)
    argument = max(editor._nodes)
    editor._connections.append(
        {"src": argument, "dst": folder, "ctype": "name_in", "cid": None})

    tree, _labels, _files = editor.get_structure()
    assert list(tree) == ["2024"]


def test_the_resolved_tree_flattens_to_operations():
    editor = _editor()
    editor._add_argument_node("annee_modif")
    tree, _labels, _files = editor.get_structure()
    ops = flatten_to_operations(tree, "/dest")
    assert len(ops) == 1
    assert ops[0][0] == "/src/a.jpg"
    assert "2024" in ops[0][1]


def test_no_files_means_no_structure():
    assert _editor(files=[]).get_structure() is None


def test_an_empty_canvas_means_no_structure():
    assert _editor()._chain_tokens() is None


def test_presets_round_trip_through_the_canvas(tmp_path, monkeypatch):
    monkeypatch.setenv("STRUCNODE_HOME", str(tmp_path))
    editor = _editor()
    editor._add_argument_node("exif_annee")
    editor._add_folder_node("Vacances")
    data = editor._preset_data()

    restored = _editor()
    restored._apply_preset_data(data)
    assert len(restored._nodes) == 2
    labels = {n.display_label for n in restored._nodes.values()}
    assert "Vacances" in labels


def test_a_preset_saved_in_french_reads_in_english(tmp_path, monkeypatch):
    monkeypatch.setenv("STRUCNODE_HOME", str(tmp_path))
    i18n.set_locale("fr")
    editor = _editor()
    editor._add_argument_node("exif_annee")
    editor._add_folder_node()          # left at its default name
    data = editor._preset_data()

    i18n.set_locale("en")
    restored = _editor()
    restored._apply_preset_data(data)
    labels = {n.display_label for n in restored._nodes.values()}
    assert labels == {i18n.t("nt_exif_annee"), i18n.t("node_default_folder")}
    assert all("é" not in label for label in labels)


def test_deleting_a_node_drops_its_connections():
    editor = _editor()
    editor._add_argument_node("annee_modif")
    editor._add_argument_node("mois_modif")
    first, second = sorted(editor._nodes)
    editor._connections.append(
        {"src": first, "dst": second, "ctype": "chain", "cid": None})

    editor._delete_node(second)
    assert second not in editor._nodes
    assert editor._connections == []


def test_clearing_the_canvas_removes_everything():
    editor = _editor()
    editor._add_argument_node("annee_modif")
    editor._clear_all()
    assert editor._nodes == {}
    assert editor._connections == []
