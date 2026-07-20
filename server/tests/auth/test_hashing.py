from server.auth.hashing import hash_password, verify_password


def test_hash_password_generates_a_random_salt_each_call():
    hash_a, salt_a = hash_password("correct horse")
    hash_b, salt_b = hash_password("correct horse")
    assert salt_a != salt_b
    assert hash_a != hash_b  # different salts => different digests for the same password


def test_verify_password_accepts_the_right_password():
    digest, salt = hash_password("correct horse")
    assert verify_password("correct horse", salt, digest) is True


def test_verify_password_rejects_the_wrong_password():
    digest, salt = hash_password("correct horse")
    assert verify_password("wrong password", salt, digest) is False
