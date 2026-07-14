"""Decoder for the `devalue` flat-array serialization format used by Nuxt 3's
`__NUXT_DATA__` SSR payload.

The payload is a JSON array. Index 0 is the root; every other slot is either
a JSON primitive, a plain list/dict whose values are themselves indices back
into the array, or a tagged pair like `["Reactive", 5]` / `["Date", 12]`
identifying a reducer. A handful of negative indices are sentinels for
values JSON can't represent natively (undefined, NaN, +/-Infinity, -0).

Nuxt registers extra single-argument reducers on top of devalue's built-ins
(`Reactive`, `ShallowReactive`, `Ref`, `ShallowRef`, `EmptyShallowRef`, ...)
that all just wrap a single value — those are unwrapped generically.
"""
from __future__ import annotations

from typing import Any

UNDEFINED = -1
HOLE = -2
NAN = -3
POSITIVE_INFINITY = -4
NEGATIVE_INFINITY = -5
NEGATIVE_ZERO = -6

_SENTINELS = {
    NAN: float("nan"),
    POSITIVE_INFINITY: float("inf"),
    NEGATIVE_INFINITY: float("-inf"),
    NEGATIVE_ZERO: -0.0,
}


def unflatten(values: list) -> Any:
    """Decode a devalue flat array into ordinary Python data structures."""
    hydrated: dict[int, Any] = {}

    def hydrate(index: int) -> Any:
        if index == UNDEFINED:
            return None
        if index in _SENTINELS:
            return _SENTINELS[index]
        if index in hydrated:
            return hydrated[index]

        value = values[index]

        if value is None or not isinstance(value, (list, dict)):
            hydrated[index] = value
            return value

        if isinstance(value, list):
            if value and isinstance(value[0], str):
                return _hydrate_tagged(index, value, hydrate, hydrated)
            arr: list = [None] * len(value)
            hydrated[index] = arr
            for i, n in enumerate(value):
                if n == HOLE:
                    continue
                arr[i] = hydrate(n)
            return arr

        obj: dict = {}
        hydrated[index] = obj
        for key, n in value.items():
            obj[key] = hydrate(n)
        return obj

    return hydrate(0)


def _hydrate_tagged(index: int, value: list, hydrate, hydrated: dict) -> Any:
    tag = value[0]
    if tag == "Date":
        result = hydrate(value[1])
    elif tag == "Set":
        result = [hydrate(i) for i in value[1:]]
    elif tag == "Map":
        result = {}
        hydrated[index] = result
        for i in range(1, len(value), 2):
            result[hydrate(value[i])] = hydrate(value[i + 1])
        return result
    elif tag == "RegExp":
        result = {"pattern": value[1], "flags": value[2]}
    elif tag == "Object":
        result = hydrate(value[1])
    elif tag == "BigInt":
        result = int(value[1])
    elif tag == "null":
        result = {}
    else:
        # Generic single-argument reducer (Reactive, ShallowReactive, Ref,
        # ShallowRef, EmptyShallowRef, NuxtError, ...) — just unwrap.
        result = hydrate(value[1])
    hydrated[index] = result
    return result


def _key_part(x: Any) -> Any:
    """Make a queryKey element hashable (dicts/lists -> nested tuples)."""
    if isinstance(x, dict):
        return tuple(sorted((k, _key_part(v)) for k, v in x.items()))
    if isinstance(x, list):
        return tuple(_key_part(v) for v in x)
    return x


def extract_queries(decoded: Any) -> dict[tuple, Any]:
    """Walk a decoded Nuxt payload for dehydrated vue-query state and return
    `{queryKey_tuple: body}`, where `body` is the unwrapped HTTP response
    body (the `{status, body}` wrapper is stripped).

    Returns an empty dict if the page has no vue-query state.
    """
    state = decoded.get("state") if isinstance(decoded, dict) else None
    if not isinstance(state, dict):
        return {}

    vue_query = None
    for key, val in state.items():
        if key.endswith("vue-query"):
            vue_query = val
            break
    if not isinstance(vue_query, dict):
        return {}

    out: dict[tuple, Any] = {}
    for query in vue_query.get("queries", []):
        query_key = query.get("queryKey")
        if query_key is None:
            continue
        data = (query.get("state") or {}).get("data")
        if not isinstance(data, dict) or "body" not in data:
            continue
        out[tuple(_key_part(k) for k in query_key)] = data["body"]
    return out
