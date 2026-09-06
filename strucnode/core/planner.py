"""Turning a folder tree into a validated, reviewable plan of operations.

The planner exists so that everything that can go wrong is known *before* a
single file moves: unresolved fields, destinations that already exist, two
sources landing on the same destination, a destination nested inside the
source, and not enough free space.
"""

from __future__ import annotations

import os
import shutil
from collections import Counter
from dataclasses import dataclass, field

from .tree import flatten_to_operations, is_unresolved

Operation = tuple[str, str]


@dataclass
class Plan:
    """Everything the Organize tab needs to describe a run before starting it."""

    operations: list[Operation] = field(default_factory=list)
    """Runnable operations, in execution order."""

    unmatched: list[Operation] = field(default_factory=list)
    """Operations left out because a metadata field could not be resolved."""

    existing_collisions: list[Operation] = field(default_factory=list)
    """Operations whose destination already exists on disk."""

    internal_collisions: list[Operation] = field(default_factory=list)
    """Operations sharing a destination with another operation of the same plan."""

    total_bytes: int = 0

    @property
    def all_operations(self) -> list[Operation]:
        """Runnable plus unmatched, in tree order -- what the preview lists."""
        return self.operations + self.unmatched

    @property
    def collisions(self) -> list[Operation]:
        """Every operation needing a duplicate decision."""
        return self.existing_collisions + self.internal_collisions


def build_plan(tree, destination: str) -> Plan:
    """Flatten *tree* onto *destination* and classify every operation.

    Unmatched operations are kept out of :attr:`Plan.operations`: the previous
    code listed them in an "unmatched" tab and then copied them anyway, into a
    folder literally named ``?``.
    """
    plan = Plan()
    seen: Counter[str] = Counter()

    for src, dst in flatten_to_operations(tree, destination):
        if is_unresolved(dst):
            plan.unmatched.append((src, dst))
            continue
        plan.operations.append((src, dst))
        seen[os.path.normcase(dst)] += 1
        try:
            plan.total_bytes += os.path.getsize(src)
        except OSError:
            pass

    for src, dst in plan.operations:
        if seen[os.path.normcase(dst)] > 1:
            plan.internal_collisions.append((src, dst))
        elif os.path.exists(dst):
            plan.existing_collisions.append((src, dst))

    return plan


def destination_is_inside(sources: list[str], destination: str) -> bool:
    """Return True when *destination* sits inside one of the *sources*."""
    if not destination:
        return False
    try:
        dest = os.path.realpath(destination)
    except OSError:
        return False
    roots = {os.path.realpath(os.path.dirname(s)) for s in sources[:200]}
    for root in roots:
        try:
            if os.path.commonpath([root, dest]) == root and root != dest:
                return True
        except (ValueError, OSError):
            continue
    return False


def free_space(destination: str) -> int | None:
    """Free bytes on the volume holding *destination*, or None if unknown."""
    probe = destination
    while probe and not os.path.isdir(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            return None
        probe = parent
    try:
        return shutil.disk_usage(probe).free
    except OSError:
        return None
