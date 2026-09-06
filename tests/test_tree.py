"""Folder-name safety and tree building."""

import os

import pytest

from strucnode.core import tree
from strucnode.core.fields import UNRESOLVED


@pytest.mark.parametrize("raw, expected", [
    ("Canon EOS 5D/Mark II", "Canon EOS 5D_Mark II"),
    ("a:b*c?d", "a_b_c_d"),
    ("trailing.  ", "trailing"),
    ("", "_"),
    (".", "_"),
    ("..", "_"),
    ("CON", "_CON"),
    ("com1.txt", "_com1.txt"),
])
def test_sanitize_component(raw, expected):
    assert tree.sanitize_component(raw) == expected


def test_sanitize_component_blocks_traversal():
    assert os.sep not in tree.sanitize_component("../../etc/passwd")
    assert "/" not in tree.sanitize_component("../../etc/passwd")


def test_sanitize_component_caps_length():
    assert len(tree.sanitize_component("x" * 500)) == 120


def _files():
    return [
        {"path": "/src/a.jpg", "name": "a.jpg", "ext": ".jpg", "size_bytes": 10,
         "_mtime": __import__("datetime").datetime(2024, 5, 4),
         "_ctime": __import__("datetime").datetime(2024, 5, 4)},
        {"path": "/src/b.png", "name": "b.png", "ext": ".png", "size_bytes": 20,
         "_mtime": __import__("datetime").datetime(2023, 1, 2),
         "_ctime": __import__("datetime").datetime(2023, 1, 2)},
    ]


def test_build_tree_groups_by_field():
    result = tree.build_tree(_files(), [tree.arg_token("year_mtime")])
    assert sorted(result) == ["2023", "2024"]
    assert len(result["2024"]) == 1


def test_build_tree_nests_levels():
    result = tree.build_tree(_files(), [tree.arg_token("year_mtime"),
                                        tree.arg_token("month_mtime")])
    assert result["2024"]["05"][0]["name"] == "a.jpg"


def test_build_tree_applies_the_separator():
    result = tree.build_tree(_files(), [tree.arg_token("year_mtime", "-")])
    assert sorted(result) == ["2023-", "2024-"]


def test_dynamic_folder_name_joins_parts():
    token = tree.dyn_folder_token([
        tree.dyn_arg_part("year_mtime"),
        tree.dyn_literal_part("-"),
        tree.dyn_arg_part("month_mtime"),
    ])
    result = tree.build_tree(_files(), [token])
    assert sorted(result) == ["2023-01", "2024-05"]


def test_dynamic_folder_name_is_unresolved_when_a_part_is():
    token = tree.dyn_folder_token([tree.dyn_arg_part("nope"),
                                   tree.dyn_literal_part("-x")])
    result = tree.build_tree(_files(), [token])
    assert list(result) == [UNRESOLVED]


def test_unresolved_field_keeps_its_marker():
    result = tree.build_tree(_files(), [tree.arg_token("does_not_exist")])
    assert list(result) == [UNRESOLVED]
    assert tree.is_unresolved(os.path.join("/dest", UNRESOLVED, "a.jpg"))


def test_is_unresolved_ignores_a_question_mark_inside_a_name():
    assert not tree.is_unresolved(os.path.join("/dest", "what?", "a.jpg"))


def test_flatten_to_operations_builds_paths():
    built = tree.build_tree(_files(), [tree.arg_token("year_mtime")])
    ops = tree.flatten_to_operations(built, os.path.join("/dest"))
    assert (os.path.join("/src", "a.jpg"),
            os.path.join("/dest", "2024", "a.jpg")) in [
        (s, d) for s, d in ops]


def test_count_files():
    built = tree.build_tree(_files(), [tree.arg_token("year_mtime")])
    assert tree.count_files(built) == 2


def test_is_within(tmp_path):
    inside = tmp_path / "a" / "b"
    inside.mkdir(parents=True)
    assert tree.is_within(str(tmp_path), str(inside))
    assert not tree.is_within(str(inside), str(tmp_path))
