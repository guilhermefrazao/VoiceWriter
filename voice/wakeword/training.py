import os

import yaml


def build_training_config(
    target_phrase: list[str],
    model_name: str,
    output_dir: str,
    piper_sample_generator_stub_dir: str,
    background_paths: list[str],
    rir_paths: list[str],
    feature_data_files: dict[str, str],
    false_positive_validation_data_path: str,
    n_samples: int = 2000,
    n_samples_val: int = 500,
    steps: int = 20000,
) -> dict:
    return {
        "model_name": model_name,
        "target_phrase": target_phrase,
        "custom_negative_phrases": [],
        "n_samples": n_samples,
        "n_samples_val": n_samples_val,
        "tts_batch_size": 16,
        "augmentation_batch_size": 16,
        "piper_sample_generator_path": piper_sample_generator_stub_dir,
        "output_dir": output_dir,
        "rir_paths": rir_paths,
        "background_paths": background_paths,
        "background_paths_duplication_rate": [1] * len(background_paths),
        "false_positive_validation_data_path": false_positive_validation_data_path,
        "augmentation_rounds": 1,
        "feature_data_files": feature_data_files,
        "batch_n_per_class": {
            **{name: 1024 for name in feature_data_files},
            "adversarial_negative": 50,
            "positive": 50,
        },
        "model_type": "dnn",
        "layer_size": 32,
        "steps": steps,
        "max_negative_weight": 1500,
        "target_false_positives_per_hour": 0.2,
    }


def write_training_config(config: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True)
