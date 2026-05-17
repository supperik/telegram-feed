def test_hash_and_verify_round_trip():
    from shared.admin_security.passwords import hash_password, verify_password
    h = hash_password("hunter2!")
    assert h.startswith("$argon2")
    assert verify_password(h, "hunter2!") is True
    assert verify_password(h, "wrong") is False


def test_two_hashes_of_same_password_differ():
    from shared.admin_security.passwords import hash_password
    a = hash_password("same")
    b = hash_password("same")
    assert a != b  # Argon2 uses a per-hash random salt.
