"""The plan must expose every problem before a file moves."""

import os

from strucnode.core import planner
from strucnode.core.fields import UNRESOLVED


def _entry(path, name, size=10):
    return {"path": path, "name": name, "ext": os.path.splitext(name)[1],
            "size_bytes": size}


def test_unmatched_operations_are_kept_out_of_the_run(tmp_path):
    src = tmp_path / "a.jpg"
    src.write_bytes(b"x")
    tree = {UNRESOLVED: [_entry(str(src), "a.jpg")],
            "2024": [_entry(str(src), "b.jpg")]}
    plan = planner.build_plan(tree, str(tmp_path / "dest"))

    assert len(plan.operations) == 1
    assert len(plan.unmatched) == 1
    assert len(plan.all_operations) == 2
    assert UNRESOLVED not in plan.operations[0][1]


def test_two_sources_on_one_destination_are_a_collision(tmp_path):
    first = tmp_path / "one" / "IMG_1.jpg"
    second = tmp_path / "two" / "IMG_1.jpg"
    for path in (first, second):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    tree = {"2024": [_entry(str(first), "IMG_1.jpg"),
                     _entry(str(second), "IMG_1.jpg")]}

    plan = planner.build_plan(tree, str(tmp_path / "dest"))
    assert len(plan.internal_collisions) == 2
    assert plan.collisions


def test_existing_destination_is_a_collision(tmp_path):
    src = tmp_path / "a.jpg"
    src.write_bytes(b"x")
    dest = tmp_path / "dest" / "2024"
    dest.mkdir(parents=True)
    (dest / "a.jpg").write_bytes(b"old")

    plan = planner.build_plan({"2024": [_entry(str(src), "a.jpg")]},
                              str(tmp_path / "dest"))
    assert len(plan.existing_collisions) == 1


def test_total_bytes_sums_the_sources(tmp_path):
    src = tmp_path / "a.jpg"
    src.write_bytes(b"12345")
    plan = planner.build_plan({"2024": [_entry(str(src), "a.jpg")]},
                              str(tmp_path / "dest"))
    assert plan.total_bytes == 5


def test_destination_inside_source_is_detected(tmp_path):
    photos = tmp_path / "photos"
    photos.mkdir()
    (photos / "a.jpg").write_bytes(b"x")
    assert planner.destination_is_inside([str(photos / "a.jpg")],
                                         str(photos / "sorted"))
    assert not planner.destination_is_inside([str(photos / "a.jpg")],
                                             str(tmp_path / "elsewhere"))


def test_free_space_walks_up_to_an_existing_folder(tmp_path):
    assert planner.free_space(str(tmp_path / "not" / "created" / "yet")) > 0
