import pytest


def test_data_integrity_error_is_value_error():
    """DataIntegrityError must be catchable as ValueError."""
    from trading_os.data.exceptions import DataIntegrityError

    with pytest.raises(ValueError):
        raise DataIntegrityError(
            symbol="SSE:000001",
            expected_range=(3000.0, 4500.0),
            actual_value=11.0,
        )


def test_data_integrity_error_message_contains_symbol():
    from trading_os.data.exceptions import DataIntegrityError

    err = DataIntegrityError(
        symbol="SSE:000001",
        expected_range=(3000.0, 4500.0),
        actual_value=11.0,
    )
    assert "SSE:000001" in str(err)
    assert "11.0" in str(err)
