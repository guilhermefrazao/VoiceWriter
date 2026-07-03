import os
import shutil
import subprocess
import sys
from typing import Callable

import yaml


PT_BR_VOICES: dict[str, str] = {
    "faber": "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx",
    "edresson": "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/edresson/low/pt_BR-edresson-low.onnx",
    "jeff": "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/jeff/medium/pt_BR-jeff-medium.onnx",
    "cadu": "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/cadu/medium/pt_BR-cadu-medium.onnx",
}

NEGATIVE_PHRASES: list[str] = [
    "bom dia", "boa tarde", "boa noite", "obrigado", "computador", "internet",
    "arquivo", "documento", "programa", "código", "reunião", "mensagem",
    "abrir chrome", "fechar notepad", "desligar computador", "editor de texto",
    "inteligência artificial", "assistente virtual", "gravação de áudio",
    "transcreva isso", "escreva aqui", "ligar o som",
]


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


def ensure_piper_train_stub(stub_dir: str) -> None:
    """`piper_sample_generator`'s __main__.py importa `piper_train.vits.commons`
    incondicionalmente, mesmo só usando vozes .onnx (generate_samples_onnx) —
    caminho que nunca chama essas funções (elas só existem para o gerador
    .pt/VITS legado, generate_samples). Sem o pacote piper_train real
    instalado (pesado: VITS + monotonic_align, exige toolchain de compilação),
    o import falha antes até do parse de argumentos. Este stub só existe para
    satisfazer o import — nunca é chamado de fato no caminho .onnx que usamos.
    """
    vits_dir = os.path.join(stub_dir, "piper_train", "vits")
    os.makedirs(vits_dir, exist_ok=True)

    init_path = os.path.join(stub_dir, "piper_train", "__init__.py")
    if not os.path.exists(init_path):
        open(init_path, "w").close()

    vits_init_path = os.path.join(vits_dir, "__init__.py")
    if not os.path.exists(vits_init_path):
        open(vits_init_path, "w").close()

    commons_path = os.path.join(vits_dir, "commons.py")
    if not os.path.exists(commons_path):
        with open(commons_path, "w", encoding="utf-8") as f:
            f.write(
                "def _unused(*args, **kwargs):\n"
                "    raise NotImplementedError(\n"
                '        "piper_train stub - caminho .pt/VITS nao usado; este "\n'
                '        "projeto so gera clipes via vozes .onnx (generate_samples_onnx)."\n'
                "    )\n\n"
                "sequence_mask = _unused\n"
                "generate_path = _unused\n"
            )


def generate_voice_clips(
    phrases: list[str],
    voice_model_paths: list[str],
    output_dir: str,
    samples_per_phrase: int,
    runner: Callable = subprocess.run,
    piper_train_stub_dir: str | None = None,
) -> None:
    """Gera clipes WAV para cada frase, usando todas as vozes pt-BR fornecidas
    em cada chamada (via múltiplas flags --model), via
    `python -m piper_sample_generator`. Cada frase é gerada num subdiretório
    temporário (o CLI sempre nomeia os arquivos 0.wav, 1.wav, ...) e depois
    movida para `output_dir` com um prefixo único para evitar colisão de nomes.
    `piper_train_stub_dir`, se informado, é prependado ao PYTHONPATH do
    subprocesso (ver ensure_piper_train_stub).
    """
    os.makedirs(output_dir, exist_ok=True)

    run_kwargs = {}
    if piper_train_stub_dir is not None:
        env = os.environ.copy()
        env["PYTHONPATH"] = piper_train_stub_dir + os.pathsep + env.get("PYTHONPATH", "")
        run_kwargs["env"] = env

    for phrase_idx, phrase in enumerate(phrases):
        phrase_dir = os.path.join(output_dir, f"_phrase_{phrase_idx}")
        cmd = [
            sys.executable, "-m", "piper_sample_generator", phrase,
            "--max-samples", str(samples_per_phrase),
            "--output-dir", phrase_dir,
        ]
        for voice_path in voice_model_paths:
            cmd.extend(["--model", voice_path])
        runner(cmd, check=True, **run_kwargs)

        if os.path.isdir(phrase_dir):
            for wav_name in os.listdir(phrase_dir):
                shutil.move(
                    os.path.join(phrase_dir, wav_name),
                    os.path.join(output_dir, f"phrase{phrase_idx}_{wav_name}"),
                )
            os.rmdir(phrase_dir)


def copy_trained_model(source_onnx_path: str, dest_path: str) -> None:
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    shutil.copyfile(source_onnx_path, dest_path)
