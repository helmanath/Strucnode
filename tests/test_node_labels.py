"""Nodes must show their label in the language currently selected."""

from tests import tk_stub

tk_stub.install()

from strucnode import i18n  # noqa: E402
from strucnode.core import fields  # noqa: E402
from strucnode.ui.nodes.node import Node  # noqa: E402


class FakeCanvas:
    """Just enough canvas for Node.draw() to run."""

    def __init__(self):
        self.texts = []

    def delete(self, *_a, **_k):
        pass

    def create_rectangle(self, *_a, **_k):
        return 1

    def create_oval(self, *_a, **_k):
        return 1

    def create_polygon(self, *_a, **_k):
        return 1

    def create_text(self, *_a, text="", **_k):
        self.texts.append(text)
        return 1


def test_argument_node_label_follows_the_locale():
    node = Node(FakeCanvas(), 1, "argument", "annee_creation", 0, 0)
    assert node.display_label == fields.label("annee_creation")
    english = node.display_label
    i18n.set_locale("fr")
    assert node.display_label == fields.label("annee_creation")
    assert node.display_label != english


def test_a_node_created_in_french_reads_correctly_in_english():
    """A node placed in French used to keep its French label for good."""
    i18n.set_locale("fr")
    node = Node(FakeCanvas(), 1, "argument", "exif_annee", 0, 0)
    french = node.display_label
    i18n.set_locale("en")
    assert node.display_label != french
    assert node.display_label == fields.label("exif_annee")


def test_default_folder_label_follows_the_locale():
    node = Node(FakeCanvas(), 2, "folder", None, 0, 0)
    assert node.label_is_default
    english = node.display_label
    i18n.set_locale("fr")
    assert node.display_label != english


def test_a_renamed_folder_keeps_its_name():
    node = Node(FakeCanvas(), 3, "folder", None, 0, 0, label_override="Vacances")
    assert not node.label_is_default
    i18n.set_locale("fr")
    assert node.display_label == "Vacances"


def test_argument_node_exposes_its_resolver():
    node = Node(FakeCanvas(), 4, "argument", "exif_mois", 0, 0)
    assert node.field == "exif_month"
