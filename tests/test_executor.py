"""Running a plan must never destroy a file the user did not agree to lose."""

import json
import threading

from strucnode.core import executor


def _plan(tmp_path, content=b"new"):
    src = tmp_path / "src" / "a.jpg"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(content)
    dst = tmp_path / "dest" / "a.jpg"
    return src, dst, [(str(src), str(dst))]


def test_copy_creates_the_destination(tmp_path):
    src, dst, ops = _plan(tmp_path)
    result = executor.run(ops, executor.COPY, journal=False)
    assert result.done == 1 and not result.errors
    assert dst.read_bytes() == b"new"
    assert src.exists()


def test_move_removes_the_source(tmp_path):
    src, dst, ops = _plan(tmp_path)
    executor.run(ops, executor.MOVE, journal=False)
    assert dst.exists() and not src.exists()


def test_skip_leaves_the_destination_untouched(tmp_path):
    src, dst, ops = _plan(tmp_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(b"old")
    result = executor.run(ops, executor.COPY, executor.SKIP, journal=False)
    assert dst.read_bytes() == b"old"
    assert result.skipped == 1


def test_rename_keeps_both_files(tmp_path):
    src, dst, ops = _plan(tmp_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(b"old")
    executor.run(ops, executor.COPY, executor.RENAME, suffix="-copy", journal=False)
    assert dst.read_bytes() == b"old"
    assert (tmp_path / "dest" / "a-copy.jpg").read_bytes() == b"new"


def test_compare_full_skips_identical_files(tmp_path):
    src, dst, ops = _plan(tmp_path, b"same")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(b"same")
    executor.run(ops, executor.COPY, executor.COMPARE_FULL, journal=False)
    assert not (tmp_path / "dest" / "a-copy.jpg").exists()


def test_compare_full_keeps_both_when_they_differ(tmp_path):
    """The regression that used to silently overwrite the destination."""
    src, dst, ops = _plan(tmp_path, b"new")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(b"different")
    executor.run(ops, executor.COPY, executor.COMPARE_FULL, suffix="-copy",
                 journal=False)
    assert dst.read_bytes() == b"different"
    assert (tmp_path / "dest" / "a-copy.jpg").read_bytes() == b"new"


def test_compare_meta_keeps_both_when_sizes_differ(tmp_path):
    src, dst, ops = _plan(tmp_path, b"much longer content")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(b"short")
    executor.run(ops, executor.COPY, executor.COMPARE_META, suffix="-copy",
                 journal=False)
    assert dst.read_bytes() == b"short"
    assert (tmp_path / "dest" / "a-copy.jpg").exists()


def test_replace_overwrites(tmp_path):
    src, dst, ops = _plan(tmp_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(b"old")
    executor.run(ops, executor.COPY, executor.REPLACE, journal=False)
    assert dst.read_bytes() == b"new"


def test_cancellation_stops_before_the_next_file(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    ops = []
    for i in range(5):
        path = src / f"{i}.jpg"
        path.write_bytes(b"x")
        ops.append((str(path), str(tmp_path / "dest" / f"{i}.jpg")))

    cancel = threading.Event()

    def progress(done, _total):
        if done >= 2:
            cancel.set()

    result = executor.run(ops, executor.COPY, cancel=cancel, progress=progress,
                          journal=False)
    assert result.cancelled
    assert result.done < 5


def test_errors_are_collected_not_raised(tmp_path):
    ops = [(str(tmp_path / "missing.jpg"), str(tmp_path / "dest" / "a.jpg"))]
    result = executor.run(ops, executor.COPY, journal=False)
    assert result.errors == 1 and result.error_messages


def test_journal_records_what_was_done(tmp_path, monkeypatch):
    monkeypatch.setenv("STRUCNODE_HOME", str(tmp_path / "home"))
    src, dst, ops = _plan(tmp_path)
    result = executor.run(ops, executor.COPY)
    assert result.journal_path
    with open(result.journal_path, encoding="utf-8") as fh:
        payload = json.load(fh)
    assert payload["operations"][0]["src"] == str(src)
    assert payload["mode"] == executor.COPY


def test_no_partial_file_is_left_behind(tmp_path):
    src, dst, ops = _plan(tmp_path)
    executor.run(ops, executor.COPY, journal=False)
    assert not list((tmp_path / "dest").glob("*.strucnode-part"))
