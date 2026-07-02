"""Testes para os helpers de download de scripts/train_wakeword.py
(_download_to, download_voices) — sem rede real: urllib.request.urlretrieve
é substituído por um dublê que só grava bytes falsos no caminho pedido.
"""
import importlib.util
import os

import pytest

SCRIPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts",
    "train_wakeword.py",
)


def _load_module():
    spec = importlib.util.spec_from_file_location("train_wakeword_download_helpers_under_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def module():
    return _load_module()


def test_download_to_writes_dest_via_tmp_then_atomic_rename(module, monkeypatch, tmp_path):
    dest_path = str(tmp_path / "voice.onnx")
    seen_tmp_paths = []

    def fake_urlretrieve(url, tmp_path_arg):
        seen_tmp_paths.append(tmp_path_arg)
        with open(tmp_path_arg, "wb") as f:
            f.write(b"fake-bytes")

    monkeypatch.setattr(module.urllib.request, "urlretrieve", fake_urlretrieve)

    module._download_to("http://example.com/voice.onnx", dest_path)

    assert seen_tmp_paths == [dest_path + ".part"]
    assert os.path.exists(dest_path)
    assert not os.path.exists(dest_path + ".part")
    with open(dest_path, "rb") as f:
        assert f.read() == b"fake-bytes"


def test_download_to_leaves_no_dest_file_if_urlretrieve_raises(module, monkeypatch, tmp_path):
    dest_path = str(tmp_path / "voice.onnx")

    def failing_urlretrieve(url, tmp_path_arg):
        with open(tmp_path_arg, "wb") as f:
            f.write(b"partial")
        raise ConnectionError("dropped mid-download")

    monkeypatch.setattr(module.urllib.request, "urlretrieve", failing_urlretrieve)

    with pytest.raises(ConnectionError):
        module._download_to("http://example.com/voice.onnx", dest_path)

    # dest was never promoted, so a subsequent run's os.path.exists(dest_path)
    # check correctly sees it as incomplete and retries.
    assert not os.path.exists(dest_path)


def test_download_voices_downloads_both_files_when_missing(module, monkeypatch, tmp_path):
    module.VOICES_DIR = str(tmp_path / "voices")
    module.PT_BR_VOICES = {"faber": "http://example.com/pt_BR-faber-medium.onnx"}
    calls = []

    def fake_download_to(url, dest_path):
        calls.append((url, dest_path))
        with open(dest_path, "wb") as f:
            f.write(b"x")

    monkeypatch.setattr(module, "_download_to", fake_download_to)

    paths = module.download_voices()

    assert len(calls) == 2
    assert calls[0][0] == "http://example.com/pt_BR-faber-medium.onnx"
    assert calls[1][0] == "http://example.com/pt_BR-faber-medium.onnx.json"
    assert paths == [os.path.join(module.VOICES_DIR, "pt_BR-faber.onnx")]


def test_download_voices_repairs_missing_json_sidecar_only(module, monkeypatch, tmp_path):
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir()
    onnx_path = voices_dir / "pt_BR-faber.onnx"
    onnx_path.write_bytes(b"already here")
    # .json sidecar deliberately absent.

    module.VOICES_DIR = str(voices_dir)
    module.PT_BR_VOICES = {"faber": "http://example.com/pt_BR-faber-medium.onnx"}
    calls = []

    def fake_download_to(url, dest_path):
        calls.append((url, dest_path))
        with open(dest_path, "wb") as f:
            f.write(b"x")

    monkeypatch.setattr(module, "_download_to", fake_download_to)

    module.download_voices()

    assert len(calls) == 1
    assert calls[0][0] == "http://example.com/pt_BR-faber-medium.onnx.json"


def test_download_voices_skips_when_both_files_present(module, monkeypatch, tmp_path):
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir()
    (voices_dir / "pt_BR-faber.onnx").write_bytes(b"onnx")
    (voices_dir / "pt_BR-faber.onnx.json").write_bytes(b"{}")

    module.VOICES_DIR = str(voices_dir)
    module.PT_BR_VOICES = {"faber": "http://example.com/pt_BR-faber-medium.onnx"}
    calls = []
    monkeypatch.setattr(module, "_download_to", lambda url, dest_path: calls.append(url))

    module.download_voices()

    assert calls == []
