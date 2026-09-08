"""Actually build every view.

Import checks were not enough: the crash that shipped happened inside
``_build_ui``, reading an attribute ``__init__`` only assigned afterwards.
Constructing each view against the strict stub reproduces that class of bug
without a display.
"""

from tests import tk_stub

tk_stub.install()

import tkinter as tk  # noqa: E402

from strucnode import i18n  # noqa: E402
from strucnode.app import StrucnodeApp  # noqa: E402
from strucnode.ui.explorer_tab import ExplorerTab  # noqa: E402
from strucnode.ui.nodes.editor_tab import NodeEditorTab  # noqa: E402
from strucnode.ui.organize_tab import OrganizeTab  # noqa: E402


def test_explorer_tab_builds():
    tab = ExplorerTab(tk.Frame())
    assert tab.files == []


def test_node_editor_tab_builds():
    editor = NodeEditorTab(tk.Frame(), lambda: [])
    assert editor.get_structure() is None


def test_organize_tab_builds():
    tab = OrganizeTab(tk.Frame(), lambda: None)
    assert tab._ops == []


def test_every_view_survives_a_language_switch():
    """The whole point of the refactor: switching must not raise anywhere."""
    views = [ExplorerTab(tk.Frame()),
             NodeEditorTab(tk.Frame(), lambda: []),
             OrganizeTab(tk.Frame(), lambda: None)]
    for locale in ("fr", "en", "fr"):
        i18n.set_locale(locale)
        for view in views:
            view.refresh_lang()


def test_explorer_renders_a_scan_result(tmp_path):
    from strucnode.core.scanner import scan

    (tmp_path / "a.jpg").write_bytes(b"12345")
    (tmp_path / "notes.txt").write_text("hello")

    seen = []
    tab = ExplorerTab(tk.Frame(), on_scan_done=seen.append)
    tab.show_results(scan(str(tmp_path)))

    assert len(seen) == 1
    assert len(tab.files) == 2
    tab._load_category("images")
    i18n.set_locale("fr")
    tab.refresh_lang()


def test_main_window_builds(tmp_path, monkeypatch):
    monkeypatch.setenv("STRUCNODE_HOME", str(tmp_path))
    app = StrucnodeApp()
    assert app._folder is None
    app._switch_tab("explorer")


def test_main_window_survives_a_language_switch(tmp_path, monkeypatch):
    monkeypatch.setenv("STRUCNODE_HOME", str(tmp_path))
    app = StrucnodeApp()
    app._set_language("fr")
    app._set_language("en")


def test_locked_tabs_open_once_a_scan_has_run(tmp_path, monkeypatch):
    """Opening the node editor and organizer is where lazy wiring can break."""
    from strucnode.core.scanner import scan

    monkeypatch.setenv("STRUCNODE_HOME", str(tmp_path))
    photos = tmp_path / "photos"
    photos.mkdir()
    (photos / "a.jpg").write_bytes(b"12345")

    app = StrucnodeApp()
    app.explorer.show_results(scan(str(photos)))
    assert app._indexed

    app._switch_tab("nodal")
    assert app._nodal_editor is not None
    app._switch_tab("organize")
    assert app._organize_tab is not None

    app._set_language("fr")
    app._set_language("en")


def test_viewers_build(tmp_path):
    """Fullscreen viewers only exist after a click, so nothing else builds them."""
    from strucnode.media.video import VideoPlayer
    from strucnode.ui.viewers import FullscreenVideoPlayer, FullscreenViewer, Viewer360

    photo = tmp_path / "a.jpg"
    photo.write_bytes(b"not really a jpeg")

    VideoPlayer(tk.Canvas(), 320, 240)
    FullscreenViewer(tk.Frame(), str(photo))
    Viewer360(tk.Frame(), str(photo))
    FullscreenVideoPlayer(tk.Frame(), str(tmp_path / "clip.mp4"))
