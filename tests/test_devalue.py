import math

from ffs import devalue


def test_unflatten_scalar():
    assert devalue.unflatten([42]) == 42
    assert devalue.unflatten(["hello"]) == "hello"


def test_unflatten_object_with_pointers():
    values = [{"a": 1}, "hi"]
    assert devalue.unflatten(values) == {"a": "hi"}


def test_unflatten_array_with_pointers():
    values = [[1, 2], "x", "y"]
    assert devalue.unflatten(values) == ["x", "y"]


def test_unflatten_sentinels():
    values = [[devalue.NAN, devalue.UNDEFINED, devalue.POSITIVE_INFINITY, devalue.NEGATIVE_INFINITY]]
    result = devalue.unflatten(values)
    assert math.isnan(result[0])
    assert result[1] is None
    assert result[2] == float("inf")
    assert result[3] == float("-inf")


def test_unflatten_hole_in_array():
    values = [[devalue.HOLE, 1], "x"]
    assert devalue.unflatten(values) == [None, "x"]


def test_unflatten_date_tag_unwraps_to_underlying_value():
    values = [["Date", 1], "2024-01-01T00:00:00.000Z"]
    assert devalue.unflatten(values) == "2024-01-01T00:00:00.000Z"


def test_unflatten_set_tag():
    values = [["Set", 1, 2], "a", "b"]
    assert devalue.unflatten(values) == ["a", "b"]


def test_unflatten_map_tag():
    values = [["Map", 1, 2], "k", "v"]
    assert devalue.unflatten(values) == {"k": "v"}


def test_unflatten_generic_reducer_unwraps():
    # Reactive/ShallowRef/etc. are single-argument reducers that just wrap a value.
    values = [["Reactive", 1], 42]
    assert devalue.unflatten(values) == 42


def test_unflatten_shared_reference_hydrated_once():
    # Two array slots pointing at the same object index should yield the same object.
    values = [[1, 1], {"a": 2}, "shared"]
    result = devalue.unflatten(values)
    assert result[0] is result[1]
    assert result[0] == {"a": "shared"}


def test_extract_queries_unwraps_body_and_hashable_keys():
    decoded = {
        "state": {
            "$abc-vue-query": {
                "queries": [
                    {
                        "queryKey": ["competitions", 242, 2025],
                        "state": {"data": {"status": 200, "body": {"name": "Worlds"}}},
                    },
                    {
                        "queryKey": ["results", {"page": 1, "pageSize": 24}],
                        "state": {"data": {"status": 200, "body": {"items": []}}},
                    },
                ]
            }
        }
    }
    queries = devalue.extract_queries(decoded)
    assert queries[("competitions", 242, 2025)] == {"name": "Worlds"}
    assert queries[("results", (("page", 1), ("pageSize", 24)))] == {"items": []}


def test_extract_queries_no_vue_query_state_returns_empty():
    assert devalue.extract_queries({"state": {}}) == {}
    assert devalue.extract_queries({}) == {}
