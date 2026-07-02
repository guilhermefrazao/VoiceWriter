import importlib.util
import os

import pytest

from voice.wakeword.training import ensure_piper_sample_generator_stub


def test_ensure_piper_sample_generator_stub_creates_importable_module(tmp_path):
    stub_dir = str(tmp_path / "stub")

    ensure_piper_sample_generator_stub(stub_dir)

    module_path = os.path.join(stub_dir, "generate_samples.py")
    assert os.path.exists(module_path)

    spec = importlib.util.spec_from_file_location("generate_samples_stub", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert callable(module.generate_samples)
    with pytest.raises(NotImplementedError):
        module.generate_samples()


def test_ensure_piper_sample_generator_stub_is_idempotent(tmp_path):
    stub_dir = str(tmp_path / "stub")

    ensure_piper_sample_generator_stub(stub_dir)
    ensure_piper_sample_generator_stub(stub_dir)  # must not raise

    assert os.path.exists(os.path.join(stub_dir, "generate_samples.py"))
