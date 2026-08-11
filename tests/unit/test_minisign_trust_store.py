import pytest

from bbr.bootstrap import verifier
from bbr.bootstrap.errors import BootstrapError


STORE = [
    {"key_id": "old", "public_key": "old-key", "valid_since": "2026-01-01"},
    {"key_id": "new", "public_key": "new-key", "valid_since": "2026-07-01"},
]


def _accept_only(key):
    def verify(artifact, signature, public_key):
        if public_key != key:
            raise BootstrapError(31, "invalid", "SIGNATURE")
    return verify


def test_trust_store_multiple_keys_accepted(monkeypatch, tmp_path):
    monkeypatch.setattr(verifier, "verify_signature", _accept_only("new-key"))
    assert verifier.verify_with_trust_store(tmp_path / "a", tmp_path / "s", STORE) == "new"


def test_trust_store_old_key_after_rotation_still_works(monkeypatch, tmp_path):
    monkeypatch.setattr(verifier, "verify_signature", _accept_only("old-key"))
    assert verifier.verify_with_trust_store(tmp_path / "a", tmp_path / "s", STORE) == "old"


def test_trust_store_removed_key_signature_invalid(monkeypatch, tmp_path):
    monkeypatch.setattr(verifier, "verify_signature", _accept_only("removed-key"))
    with pytest.raises(BootstrapError) as error:
        verifier.verify_with_trust_store(tmp_path / "a", tmp_path / "s", STORE)
    assert error.value.code == 31


def test_trust_store_no_match_signature_invalid(monkeypatch, tmp_path):
    def reject(*args):
        raise BootstrapError(31, "invalid", "SIGNATURE")
    monkeypatch.setattr(verifier, "verify_signature", reject)
    with pytest.raises(BootstrapError, match="TRUST_STORE_NO_VALID_SIGNATURE"):
        verifier.verify_with_trust_store(tmp_path / "a", tmp_path / "s", [])
