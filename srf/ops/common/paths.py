"""Path resolution for ops: a node's declared reads/writes name its own files.

An op runs inside a work directory and exchanges artifacts through files. The
graph — not the op — decides which files those are: the executing node declares
``reads`` / ``writes``, and the runtime exposes them on the context. Ops that
hardcode a filename break as soon as two branches of a fork run at once, so they
resolve their paths from the declaration instead.
"""

from __future__ import annotations

from typing import Any


def _declared(ctx: Any, attribute: str) -> list[str]:
    names = getattr(ctx, attribute, None)
    if not names:
        return []
    return sorted(str(name) for name in names)


def declared_read(ctx: Any, default: str, *, suffix: str = "") -> str:
    """The node's declared read matching ``suffix``, else ``default``."""
    return _pick(_declared(ctx, "_current_node_reads"), default, suffix)


def declared_write(ctx: Any, default: str, *, suffix: str = "") -> str:
    """The node's declared write matching ``suffix``, else ``default``."""
    return _pick(_declared(ctx, "_current_node_writes"), default, suffix)


def _pick(names: list[str], default: str, suffix: str) -> str:
    matches = [name for name in names if name.endswith(suffix)] if suffix else names
    return matches[0] if matches else default


def write_declared(ctx: Any, default: str, content: str, *, suffix: str = "") -> str:
    """Write ``content`` to the node's declared write path; returns the path used."""
    name = declared_write(ctx, default, suffix=suffix)
    ctx.write_text(name, content)
    return name


def read_declared(ctx: Any, default: str, *, suffix: str = "") -> str:
    """Read the node's declared read path, falling back to ``default``."""
    return ctx.read_text(declared_read(ctx, default, suffix=suffix))
