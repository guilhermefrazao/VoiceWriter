from voice.utils import benchmark_manifest as bm


def test_command_samples_iterate_from_manifest():
    samples = bm.load_manifest("commands")
    # os pipelines devem conseguir montar (caminho, referência) para cada amostra
    pairs = [(bm.audio_path("commands", s), s.reference) for s in samples]
    assert len(pairs) == 30
    assert all(ref for _, ref in pairs)
