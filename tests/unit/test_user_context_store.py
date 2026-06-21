from smith.models.user_context import UserContextDocument
from smith.services.user_context_store import UserContextStore, user_context_path


def test_empty_load_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    doc = UserContextStore.load()
    assert doc.schema_version == 2
    assert doc.confidence == 0.0
    assert doc.user.interests == []


def test_round_trip_save_load(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    doc = UserContextDocument.empty()
    doc.user.interests = ["drones"]
    doc.derived.primary_languages = ["Python"]
    doc.confidence = 0.5
    doc.confidence_reason = "test"
    path = UserContextStore.save(doc)
    assert path == user_context_path()
    loaded = UserContextStore.load()
    assert loaded.user.interests == ["drones"]
    assert loaded.derived.primary_languages == ["Python"]
    assert loaded.confidence == 0.5


def test_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / ".smith"))
    assert UserContextStore.exists() is False
    UserContextStore.save(UserContextDocument.empty())
    assert UserContextStore.exists() is True
