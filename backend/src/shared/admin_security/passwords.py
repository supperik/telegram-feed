from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_PH = PasswordHasher(memory_cost=64 * 1024, time_cost=3, parallelism=2)


def hash_password(password: str) -> str:
    return _PH.hash(password)


def verify_password(hash_: str, password: str) -> bool:
    try:
        _PH.verify(hash_, password)
        return True
    except VerifyMismatchError:
        return False
