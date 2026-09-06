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
