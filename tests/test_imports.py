"""Every module must import cleanly, UI included."""

import importlib

import pytest

from tests import tk_stub

tk_stub.install()

MODULES = [
    "strucnode",
    "strucnode.app",
    "strucnode.config",
    "strucnode.theme",
    "strucnode.i18n",
    "strucnode.core.categories",
    "strucnode.core.dedupe",
    "strucnode.core.executor",
    "strucnode.core.fields",
    "strucnode.core.metadata",
    "strucnode.core.planner",
    "strucnode.core.scanner",
    "strucnode.core.tree",
    "strucnode.media.images",
    "strucnode.media.system",
    "strucnode.media.video",
    "strucnode.ui.explorer_tab",
    "strucnode.ui.organize_tab",
    "strucnode.ui.viewers",
    "strucnode.ui.nodes.node",
    "strucnode.ui.nodes.presets",
    "strucnode.ui.nodes.editor_tab",
]


@pytest.mark.parametrize("name", MODULES)
def test_module_imports(name):
    importlib.import_module(name)


def test_the_stub_is_active_even_where_real_tkinter_exists():
    """CI has Tkinter but no display.

    Letting the real one win there made every widget test die with
    "TclError: no display name". conftest installs the stub unconditionally;
    this asserts it actually took effect.
    """
    import tkinter

    assert tk_stub.is_installed()
    assert getattr(tkinter, "__strucnode_tk_stub__", False)


def test_installing_the_stub_twice_is_a_no_op():
    import tkinter

    before = tkinter.Frame
    tk_stub.install()
    assert tkinter.Frame is before
