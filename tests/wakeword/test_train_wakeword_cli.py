"""Testes para scripts/train_wakeword.py (CLI), sem tocar rede nem dependências
pesadas de treino (torch/datasets/scipy/openwakeword) — todas as funções que as
usam são substituídas por dublês.
"""
import importlib.util
import os
import sys

SCRIPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts",
    "train_wakeword.py",
)


def _load_module():
    spec = importlib.util.spec_from_file_location("train_wakeword_cli_under_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _patch_common(module, monkeypatch, fake_datasets):
    """Substitui as etapas que fariam I/O real (rede, subprocess, disco fora
    de tmp_path) por dublês, e captura o config passado a write_training_config.
    """
    captured_configs = []

    monkeypatch.setattr(module, "download_negative_datasets", lambda: fake_datasets)
    monkeypatch.setattr(module, "ensure_piper_sample_generator_stub", lambda stub_dir: None)
    monkeypatch.setattr(module, "generate_positive_clips", lambda voice_paths: None)
    monkeypatch.setattr(module, "generate_negative_clips", lambda voice_paths: None)
    monkeypatch.setattr(module, "run_train_phase", lambda flags: None)
    monkeypatch.setattr(module, "copy_trained_model", lambda src, dest: None)
    monkeypatch.setattr(
        module, "write_training_config", lambda config, path: captured_configs.append(config)
    )

    return captured_configs


def test_augment_standalone_gets_real_dataset_paths_not_empty(monkeypatch):
    """Finding #1: --augment sozinho (sem --download-datasets/--all) ainda
    deve popular rir_paths/background_paths/feature_data_files/validation_path
    no config, não deixá-los vazios.
    """
    module = _load_module()
    fake_datasets = (
        ["/fake/mit_rirs"],
        ["/fake/background_noise"],
        {"ACAV100M_sample": "/fake/features.npy"},
        "/fake/validation_set_features.npy",
    )
    captured_configs = _patch_common(module, monkeypatch, fake_datasets)

    monkeypatch.setattr(sys, "argv", ["train_wakeword.py", "--augment"])
    module.main()

    assert len(captured_configs) == 1
    config = captured_configs[0]
    assert config["rir_paths"] == ["/fake/mit_rirs"]
    assert config["background_paths"] == ["/fake/background_noise"]
    assert config["feature_data_files"] == {"ACAV100M_sample": "/fake/features.npy"}
    assert config["false_positive_validation_data_path"] == "/fake/validation_set_features.npy"


def test_train_standalone_also_calls_download_negative_datasets(monkeypatch):
    """Finding #1: --train sozinho também deve chamar download_negative_datasets
    (idempotente) em vez de silenciosamente montar um config vazio.
    """
    module = _load_module()
    fake_datasets = (["/fake/mit_rirs"], ["/fake/background_noise"], {}, "/fake/val.npy")
    call_count = {"n": 0}

    def fake_download():
        call_count["n"] += 1
        return fake_datasets

    monkeypatch.setattr(module, "download_negative_datasets", fake_download)
    _patch_common(module, monkeypatch, fake_datasets)
    # _patch_common overwrote download_negative_datasets with a plain lambda;
    # reapply our counting version afterwards.
    monkeypatch.setattr(module, "download_negative_datasets", fake_download)

    monkeypatch.setattr(sys, "argv", ["train_wakeword.py", "--train"])
    module.main()

    assert call_count["n"] == 1


def test_background_paths_is_a_distinct_directory_from_rir_paths(monkeypatch):
    """Finding #2: background_paths must not silently reuse the RIR directory
    (mit_rirs) — the config's background_paths should come straight from
    download_negative_datasets()'s own background directory.
    """
    module = _load_module()
    fake_datasets = (
        ["/fake/workspace/mit_rirs"],
        ["/fake/workspace/background_noise"],
        {"ACAV100M_sample": "/fake/features.npy"},
        "/fake/val.npy",
    )
    captured_configs = _patch_common(module, monkeypatch, fake_datasets)

    monkeypatch.setattr(sys, "argv", ["train_wakeword.py", "--all"])
    module.main()

    config = captured_configs[0]
    assert config["background_paths"] != config["rir_paths"]
    assert config["background_paths"] == ["/fake/workspace/background_noise"]
