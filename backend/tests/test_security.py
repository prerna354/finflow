from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_is_hashed_and_verifies():
    hashed = hash_password("Test@12345")
    assert hashed != "Test@12345"
    assert verify_password("Test@12345", hashed)
    assert not verify_password("wrong-password", hashed)


def test_token_round_trip():
    token = create_access_token(subject="user-123", role="customer")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "customer"


def test_bad_token_is_rejected():
    assert decode_access_token("not-a-real-token") is None
