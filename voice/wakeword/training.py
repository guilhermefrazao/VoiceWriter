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


def ensure_piper_sample_generator_stub(stub_dir: str) -> None:
    """openwakeword.train importa incondicionalmente `generate_samples` de
    `piper_sample_generator_path`, mesmo quando só usamos --augment_clips e
    --train_model. Como a ferramenta original só gera fala em inglês, os
    clipes pt-BR são gerados separadamente (generate_voice_clips, abaixo) e
    este stub só existe para satisfazer o import — nunca é chamado de fato.
    """
    os.makedirs(stub_dir, exist_ok=True)
    stub_path = os.path.join(stub_dir, "generate_samples.py")
    if not os.path.exists(stub_path):
        with open(stub_path, "w", encoding="utf-8") as f:
            f.write(
                "def generate_samples(*args, **kwargs):\n"
                "    raise NotImplementedError(\n"
                '        "Geracao via TTS em ingles desabilitada; os clipes pt-BR ja "\n'
                '        "foram gerados por generate_voice_clips()."\n'
                "    )\n"
            )
