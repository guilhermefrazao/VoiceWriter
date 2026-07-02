import os
from pathlib import Path

from voice.wakeword.training import generate_voice_clips


def test_generate_voice_clips_moves_and_renames_to_avoid_collisions(tmp_path):
    output_dir = str(tmp_path / "positive_train")
    calls = []

    def fake_runner(cmd, check):
        calls.append(cmd)
        output_dir_arg = cmd[cmd.index("--output-dir") + 1]
        os.makedirs(output_dir_arg, exist_ok=True)
        Path(output_dir_arg, "0.wav").write_bytes(b"fake wav data")

    generate_voice_clips(
        phrases=["transcrição", "transcrição por favor"],
        voice_model_paths=["voices/pt_BR-faber-medium.onnx"],
        output_dir=output_dir,
        samples_per_phrase=1,
        runner=fake_runner,
    )

    produced = sorted(os.listdir(output_dir))
    assert produced == ["phrase0_0.wav", "phrase1_0.wav"]
    assert len(calls) == 2
    assert calls[0][:3] == ["python", "-m", "piper_sample_generator"]
    assert "--model" in calls[0]
    assert "voices/pt_BR-faber-medium.onnx" in calls[0]


def test_generate_voice_clips_passes_all_voice_models(tmp_path):
    output_dir = str(tmp_path / "positive_train")
    calls = []

    def fake_runner(cmd, check):
        calls.append(cmd)
        output_dir_arg = cmd[cmd.index("--output-dir") + 1]
        os.makedirs(output_dir_arg, exist_ok=True)

    generate_voice_clips(
        phrases=["transcrição"],
        voice_model_paths=["voices/a.onnx", "voices/b.onnx"],
        output_dir=output_dir,
        samples_per_phrase=5,
        runner=fake_runner,
    )

    model_flags = [i for i, arg in enumerate(calls[0]) if arg == "--model"]
    assert len(model_flags) == 2
    assert "voices/a.onnx" in calls[0]
    assert "voices/b.onnx" in calls[0]
