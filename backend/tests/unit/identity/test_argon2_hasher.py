"""Unit tests for the Argon2id password hasher."""

from __future__ import annotations

from app.modules.identity.infrastructure.auth import Argon2Hasher


class TestArgon2Hasher:
    def test_hash_then_verify_roundtrip(self) -> None:
        h = Argon2Hasher()
        encoded = h.hash("Sup3rStrongP@ss")
        assert encoded != "Sup3rStrongP@ss"  # never store plaintext
        assert h.verify(encoded, "Sup3rStrongP@ss") is True

    def test_verify_rejects_wrong_password(self) -> None:
        h = Argon2Hasher()
        encoded = h.hash("correct horse battery")
        assert h.verify(encoded, "wrong password") is False

    def test_verify_empty_hash_is_false(self) -> None:
        # Defends the login path against users without a password hash.
        assert Argon2Hasher().verify("", "anything") is False

    def test_verify_garbage_hash_is_false(self) -> None:
        assert Argon2Hasher().verify("not-an-argon2-hash", "x") is False

    def test_salt_makes_hashes_unique(self) -> None:
        h = Argon2Hasher()
        assert h.hash("samepass") != h.hash("samepass")

    def test_needs_rehash_false_for_current_params(self) -> None:
        h = Argon2Hasher()
        assert h.needs_rehash(h.hash("pw")) is False

    def test_needs_rehash_true_for_foreign_hash(self) -> None:
        # A bcrypt-looking string is not a valid Argon2 hash → must be rehashed.
        assert Argon2Hasher().needs_rehash("$2b$12$abcdefghijklmnopqrstuv") is True
