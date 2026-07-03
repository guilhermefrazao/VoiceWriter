import wave
import speech_recognition as sr
import json

import scripts.record_benchmark as rec
from voice.utils import benchmark_manifest as bm


def _silence_audio(seconds=1, rate=44100):
    # AudioData cru: silêncio 16-bit mono
    frames = b"\x00\x00" * int(rate * seconds)
    return sr.AudioData(frames, rate, 2)


def test_save_audio_wav_writes_16k_mono_16bit(tmp_path):
    out = tmp_path / "sub" / "1.wav"
    rec.save_audio_wav(_silence_audio(), out)
    assert out.exists()
    with wave.open(str(out), "rb") as w:
        assert w.getframerate() == 16000
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2


def test_record_pending_records_and_marks(tmp_path, monkeypatch):
    monkeypatch.setattr(bm, "BENCHMARK_DIR", tmp_path)
    (tmp_path / "commands.json").write_text(json.dumps([
        {"id": 1, "filename": "1.wav", "reference": "Abra o Google", "recorded_by": "legacy"},
        {"id": 2, "filename": "2.wav", "reference": "Feche o Firefox", "recorded_by": None},
    ]), encoding="utf-8")

    class FakeRecognizer:
        def adjust_for_ambient_noise(self, source, duration=1):
            pass

        def listen(self, source, timeout=None, phrase_time_limit=None):
            return _silence_audio()

    class FakeMic:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    prompts = []
    n = rec.record_pending(
        "commands",
        member="tester",
        recognizer=FakeRecognizer(),
        mic_factory=lambda: FakeMic(),
        prompt_fn=lambda text: prompts.append(text) or "record",
    )
    assert n == 1
    assert prompts == ["Feche o Firefox"]
    reloaded = bm.load_manifest("commands")
    assert reloaded[1].recorded_by == "tester"
    assert bm.audio_path("commands", reloaded[1]).exists()
