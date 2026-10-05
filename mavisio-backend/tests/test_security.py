from app.core.security import create_token, decode_token, hash_password, verify_password


def test_password_and_token():
    assert verify_password("secret123", hash_password("secret123"))
    assert decode_token(create_token("b519cf38-ec78-4e3b-90f8-69b0c4a2d2ed")) == "b519cf38-ec78-4e3b-90f8-69b0c4a2d2ed"
