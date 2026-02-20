from concurrency_safe.hashing import key_to_int64


def test_same_key_same_value():
    assert key_to_int64("stock:ABC") == key_to_int64("stock:ABC")


def test_different_keys_different_values():
    assert key_to_int64("stock:ABC") != key_to_int64("stock:XYZ")


def test_returns_int():
    value = key_to_int64("test")
    assert isinstance(value, int)