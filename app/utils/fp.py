"""Functional Programming Utilities for Gym Tracker.

Provides core FP primitives: composition, currying, immutability helpers,
and higher-order functions used across all routers.
"""
from __future__ import annotations
from functools import reduce
from typing import TypeVar, Callable, Any

A = TypeVar("A")
B = TypeVar("B")
C = TypeVar("C")


# ── Function Composition ──────────────────────────────────────

def pipe(*fns: Callable) -> Callable:
    """Left-to-right function composition.

    pipe(f, g, h)(x) == h(g(f(x)))
    """
    return lambda val: reduce(lambda acc, f: f(acc), fns, val)


def compose(*fns: Callable) -> Callable:
    """Right-to-left function composition.

    compose(f, g, h)(x) == f(g(h(x)))
    """
    return lambda val: reduce(lambda acc, f: f(acc), reversed(fns), val)


# ── Currying ──────────────────────────────────────────────────

def curry(fn: Callable) -> Callable:
    """Auto-curry a function of arbitrary arity.

    add = curry(lambda a, b: a + b)
    add(1)(2)  # 3
    add(1, 2)  # 3
    """
    def curried(*args):
        if len(args) >= fn.__code__.co_argcount:
            return fn(*args)
        return curry(lambda *more: fn(*args, *more))
    return curried


# ── Higher-Order Functions ────────────────────────────────────

def apply_if(predicate: Callable[[A], bool], fn: Callable[[A], A]) -> Callable[[A], A]:
    """Return a function that applies `fn` only when `predicate` is true."""
    return lambda val: fn(val) if predicate(val) else val


def apply_when_some(fn: Callable[[A], B]) -> Callable[[A | None], B | None]:
    """Return a function that applies `fn` only when value is not None."""
    return lambda val: fn(val) if val is not None else None


def pick(*keys: str) -> Callable[[dict], dict]:
    """Return a function that creates a new dict with only the specified keys."""
    return lambda d: {k: d[k] for k in keys if k in d}


def omit(*keys: str) -> Callable[[dict], dict]:
    """Return a function that creates a new dict without the specified keys."""
    return lambda d: {k: v for k, v in d.items() if k not in keys}


def merge(base: dict, *overrides: dict) -> dict:
    """Immutable merge - returns a new dict, never mutates inputs."""
    return reduce(lambda acc, o: {**acc, **o}, overrides, base)


# ── List Operations ───────────────────────────────────────────

def flat_map(fn: Callable[[A], list[B]], xs: list[A]) -> list[B]:
    """Map then flatten - equivalent to list comprehension but composable."""
    return reduce(lambda acc, x: acc + fn(x), xs, [])


def group_by(key_fn: Callable[[A], str]) -> Callable[[list[A]], dict[str, list[A]]]:
    """Return a function that groups elements by key_fn.

    Uses recursion internally to demonstrate recursive thinking.
    """
    def _group(items: list[A]) -> dict[str, list[A]]:
        def recurse(remaining: list[A], acc: dict) -> dict:
            if not remaining:
                return acc
            head, *tail = remaining
            key = key_fn(head)
            return recurse(tail, merge(acc, {key: acc.get(key, []) + [head]}))
        return recurse(items, {})
    return _group


def sum_by(extract_fn: Callable[[A], float]) -> Callable[[list[A]], float]:
    """Return a function that sums extracted values from a list."""
    return lambda xs: sum(map(extract_fn, xs))


def filter_by(predicate: Callable[[A], bool]) -> Callable[[list[A]], list[A]]:
    """Curried filter - returns a reusable predicate function."""
    return lambda xs: list(filter(predicate, xs))


# ── Validation (Closure-based) ────────────────────────────────

def validator(
    check: Callable[[Any], bool],
    error_msg: str
) -> Callable[[Any], Any]:
    """Create a validation closure that raises or returns the value.

    v = validator(lambda x: x > 0, "Must be positive")
    v(5)   # 5
    v(-1)  # raises ValueError
    """
    def validate(value: Any) -> Any:
        if not check(value):
            raise ValueError(error_msg)
        return value
    return validate


def all_validators(*validators: Callable) -> Callable:
    """Compose multiple validators into one.

    v = all_validators(
        validator(lambda x: isinstance(x, int), "Must be int"),
        validator(lambda x: x > 0, "Must be positive"),
    )
    """
    return pipe(*validators)
