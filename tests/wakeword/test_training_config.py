import yaml

from voice.wakeword.training import build_training_config, write_training_config


def test_build_training_config_has_expected_keys():
    config = build_training_config(
        target_phrase=["transcrição", "transcrição por favor"],
        model_name="transcricao",
        output_dir="/tmp/out",
        piper_sample_generator_stub_dir="/tmp/stub",
        background_paths=["/tmp/bg"],
        rir_paths=["/tmp/rir"],
        feature_data_files={"ACAV100M_sample": "/tmp/features.npy"},
        false_positive_validation_data_path="/tmp/val.npy",
    )

    assert config["model_name"] == "transcricao"
    assert config["target_phrase"] == ["transcrição", "transcrição por favor"]
    assert config["piper_sample_generator_path"] == "/tmp/stub"
    assert config["background_paths"] == ["/tmp/bg"]
    assert config["background_paths_duplication_rate"] == [1]
    assert config["feature_data_files"] == {"ACAV100M_sample": "/tmp/features.npy"}
    assert config["batch_n_per_class"]["positive"] == 50
    assert config["batch_n_per_class"]["ACAV100M_sample"] == 1024
    assert config["n_samples"] == 2000
    assert config["steps"] == 20000


def test_write_training_config_round_trips_through_yaml(tmp_path):
    config = {"model_name": "transcricao", "target_phrase": ["transcrição"]}
    path = str(tmp_path / "nested" / "config.yaml")

    write_training_config(config, path)

    with open(path, encoding="utf-8") as f:
        loaded = yaml.safe_load(f)

    assert loaded == config
