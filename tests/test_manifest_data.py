from voice.utils import benchmark_manifest as bm


def test_commands_manifest_has_30_unique():
    samples = bm.load_manifest("commands")
    assert len(samples) == 30
    assert len({s.id for s in samples}) == 30


def test_transcriptions_manifest_has_30_unique():
    samples = bm.load_manifest("transcriptions")
    assert len(samples) == 30
    assert len({s.id for s in samples}) == 30


def test_legacy_wavs_exist_on_disk():
    for dataset in ("commands", "transcriptions"):
        for s in bm.load_manifest(dataset):
            if s.recorded_by == "legacy":
                assert bm.audio_path(dataset, s).exists(), f"faltando: {s.filename}"
