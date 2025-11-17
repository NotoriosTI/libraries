from env_manager.utils import coerce_type


def test_coerce_str_returns_string():
    assert coerce_type("value", "str", "TEST") == "value"


def test_coerce_int_success():
    assert coerce_type("123", "int", "TEST") == 123


def test_coerce_float_success():
    assert coerce_type("1.23", "float", "TEST") == 1.23


def test_coerce_bool_true_values():
    assert coerce_type("true", "bool", "FLAG") is True
    assert coerce_type("1", "bool", "FLAG") is True


def test_coerce_bool_false_values():
    assert coerce_type("false", "bool", "FLAG") is False
    assert coerce_type("0", "bool", "FLAG") is False


def test_coerce_bool_invalid_value():
    try:
        coerce_type("yes", "bool", "FLAG")
    except ValueError as exc:
        assert "Invalid boolean value" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected ValueError for invalid bool")


def test_coerce_invalid_type():
    try:
        coerce_type("value", "date", "TEST")
    except ValueError as exc:
        assert "Unsupported type" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected ValueError for unsupported type")
