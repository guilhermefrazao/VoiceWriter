import json
import pytest
from voice.utils import benchmark_manifest as bm


def _write(tmp_path, name, data):
    p = tmp_path / name
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_load_manifest_parses_samples(tmp_path, monkeypatch):
    monkeypatch.setattr(bm, "BENCHMARK_DIR", tmp_path)
    _write(tmp_path, "commands.json", [
        {"id": 1, "filename": "1.wav", "reference": "Abra o Google", "recorded_by": "saraiva"},
        {"id": 2, "filename": "2.wav", "reference": "Feche o Firefox", "recorded_by": None},
    ])
    samples = bm.load_manifest("commands")
    assert len(samples) == 2
    assert samples[0].id == 1
    assert samples[0].reference == "Abra o Google"
    assert samples[1].recorded_by is None


def test_load_manifest_rejects_duplicate_ids(tmp_path, monkeypatch):
    monkeypatch.setattr(bm, "BENCHMARK_DIR", tmp_path)
    _write(tmp_path, "commands.json", [
        {"id": 1, "filename": "1.wav", "reference": "a", "recorded_by": None},
        {"id": 1, "filename": "x.wav", "reference": "b", "recorded_by": None},
    ])
    with pytest.raises(ValueError, match="duplicad"):
        bm.load_manifest("commands")


def test_pending_samples_filters_unrecorded(tmp_path, monkeypatch):
    monkeypatch.setattr(bm, "BENCHMARK_DIR", tmp_path)
    _write(tmp_path, "commands.json", [
        {"id": 1, "filename": "1.wav", "reference": "a", "recorded_by": "x"},
        {"id": 2, "filename": "2.wav", "reference": "b", "recorded_by": None},
    ])
    samples = bm.load_manifest("commands")
    pending = bm.pending_samples(samples)
    assert [s.id for s in pending] == [2]


def test_mark_recorded_and_save_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(bm, "BENCHMARK_DIR", tmp_path)
    _write(tmp_path, "commands.json", [
        {"id": 1, "filename": "1.wav", "reference": "a", "recorded_by": None},
    ])
    samples = bm.load_manifest("commands")
    bm.mark_recorded(samples, 1, "saraiva")
    bm.save_manifest("commands", samples)
    reloaded = bm.load_manifest("commands")
    assert reloaded[0].recorded_by == "saraiva"


def test_audio_path_uses_dataset_subdir(tmp_path, monkeypatch):
    monkeypatch.setattr(bm, "BENCHMARK_DIR", tmp_path)
    s = bm.BenchmarkSample(id=3, filename="3.wav", reference="x", recorded_by=None)
    assert bm.audio_path("commands", s) == tmp_path / "commands" / "3.wav"
