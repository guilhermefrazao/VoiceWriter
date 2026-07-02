from voice.wakeword.training import copy_trained_model


def test_copy_trained_model_creates_dest_dirs_and_copies_bytes(tmp_path):
    source = tmp_path / "my_custom_model" / "transcricao" / "transcricao.onnx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"fake onnx bytes")
    dest = tmp_path / "voice" / "wakeword" / "models" / "transcricao.onnx"

    copy_trained_model(str(source), str(dest))

    assert dest.read_bytes() == b"fake onnx bytes"
