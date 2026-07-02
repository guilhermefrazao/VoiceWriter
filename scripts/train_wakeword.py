"""CLI para treinar o modelo de wakeword "transcrição" (pt-BR).

Ver voice/wakeword/README.md para o setup de dependências e o passo a passo.
"""
import argparse
import logging
import os
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice.wakeword.training import (  # noqa: E402
    NEGATIVE_PHRASES,
    PT_BR_VOICES,
    build_training_config,
    copy_trained_model,
    ensure_piper_sample_generator_stub,
    generate_voice_clips,
    write_training_config,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

WORKSPACE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".wakeword_training")
VOICES_DIR = os.path.join(WORKSPACE, "voices")
MODEL_NAME = "transcricao"
TARGET_PHRASES = ["transcrição", "transcrição por favor"]
OUTPUT_DIR = os.path.join(WORKSPACE, "output")
CONFIG_PATH = os.path.join(WORKSPACE, "transcricao_training_config.yaml")
FINAL_MODEL_DEST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "voice", "wakeword", "models", "transcricao.onnx",
)


def _download_to(url: str, dest_path: str) -> None:
    """Baixa `url` para um arquivo temporário e só promove para `dest_path`
    (via rename atômico) depois que o download termina com sucesso, para que
    uma interrupção (Ctrl-C, queda de conexão) nunca deixe um arquivo parcial
    que uma próxima execução aceitaria como completo.
    """
    tmp_path = dest_path + ".part"
    urllib.request.urlretrieve(url, tmp_path)
    os.replace(tmp_path, dest_path)


def download_voices() -> list[str]:
    os.makedirs(VOICES_DIR, exist_ok=True)
    paths = []
    for name, url in PT_BR_VOICES.items():
        onnx_path = os.path.join(VOICES_DIR, f"pt_BR-{name}.onnx")
        json_path = onnx_path + ".json"
        if not os.path.exists(onnx_path):
            logger.info("Baixando voz '%s'...", name)
            _download_to(url, onnx_path)
        if not os.path.exists(json_path):
            logger.info("Baixando metadata da voz '%s'...", name)
            _download_to(url + ".json", json_path)
        paths.append(onnx_path)
    return paths


def download_negative_datasets() -> tuple[list[str], list[str], dict[str, str], str]:
    """Baixa RIRs, ruído de fundo e features negativas pré-computadas.
    Reaproveita as mesmas fontes do notebook oficial do openWakeWord
    (dscripka/MIT_environmental_impulse_responses, rudraml/fma para ruído de
    fundo, e features ACAV100M + dataset de validação, hospedados no Hugging
    Face por davidscripka).
    Idempotente: pula qualquer etapa cujo diretório/arquivo já esteja
    completo (diretórios de streaming usam um marker ".complete" gravado só
    ao final do loop; arquivos únicos são baixados para ".part" e promovidos
    via rename atômico só após o download terminar).

    Retorna (rir_paths, background_paths, feature_data_files, validation_path).
    """
    import numpy as np
    import scipy.io.wavfile
    import datasets

    rir_dir = os.path.join(WORKSPACE, "mit_rirs")
    rir_marker = os.path.join(rir_dir, ".complete")
    if not os.path.exists(rir_marker):
        os.makedirs(rir_dir, exist_ok=True)
        logger.info("Baixando Room Impulse Responses...")
        rir_dataset = datasets.load_dataset(
            "davidscripka/MIT_environmental_impulse_responses", split="train", streaming=True
        )
        for row in rir_dataset:
            name = row["audio"]["path"].split("/")[-1]
            scipy.io.wavfile.write(
                os.path.join(rir_dir, name), 16000, (row["audio"]["array"] * 32767).astype(np.int16)
            )
        with open(rir_marker, "w") as f:
            f.write("done")

    background_dir = os.path.join(WORKSPACE, "background_noise")
    background_marker = os.path.join(background_dir, ".complete")
    if not os.path.exists(background_marker):
        os.makedirs(background_dir, exist_ok=True)
        logger.info("Baixando ruído de fundo (FMA, ~1h)...")
        fma_dataset = datasets.load_dataset("rudraml/fma", name="small", split="train", streaming=True)
        fma_dataset = iter(fma_dataset.cast_column("audio", datasets.Audio(sampling_rate=16000)))
        n_hours = 1
        for _ in range(n_hours * 3600 // 30):
            try:
                row = next(fma_dataset)
            except StopIteration:
                break
            name = row["audio"]["path"].split("/")[-1].replace(".mp3", ".wav")
            scipy.io.wavfile.write(
                os.path.join(background_dir, name), 16000, (row["audio"]["array"] * 32767).astype(np.int16)
            )
        with open(background_marker, "w") as f:
            f.write("done")

    features_path = os.path.join(WORKSPACE, "openwakeword_features_ACAV100M_2000_hrs_16bit.npy")
    if not os.path.exists(features_path):
        logger.info("Baixando features negativas pré-computadas (ACAV100M, vários GB)...")
        _download_to(
            "https://huggingface.co/datasets/davidscripka/openwakeword_features/resolve/main/"
            "openwakeword_features_ACAV100M_2000_hrs_16bit.npy",
            features_path,
        )

    validation_path = os.path.join(WORKSPACE, "validation_set_features.npy")
    if not os.path.exists(validation_path):
        logger.info("Baixando dataset de validação de falsos-positivos...")
        _download_to(
            "https://huggingface.co/datasets/davidscripka/openwakeword_features/resolve/main/"
            "validation_set_features.npy",
            validation_path,
        )

    return [rir_dir], [background_dir], {"ACAV100M_sample": features_path}, validation_path


def generate_positive_clips(voice_paths: list[str]) -> None:
    positive_train = os.path.join(OUTPUT_DIR, MODEL_NAME, "positive_train")
    positive_test = os.path.join(OUTPUT_DIR, MODEL_NAME, "positive_test")
    generate_voice_clips(TARGET_PHRASES, voice_paths, positive_train, samples_per_phrase=250)
    generate_voice_clips(TARGET_PHRASES, voice_paths, positive_test, samples_per_phrase=50)


def generate_negative_clips(voice_paths: list[str]) -> None:
    negative_train = os.path.join(OUTPUT_DIR, MODEL_NAME, "negative_train")
    negative_test = os.path.join(OUTPUT_DIR, MODEL_NAME, "negative_test")
    generate_voice_clips(NEGATIVE_PHRASES, voice_paths, negative_train, samples_per_phrase=50)
    generate_voice_clips(NEGATIVE_PHRASES, voice_paths, negative_test, samples_per_phrase=10)


def run_train_phase(flags: list[str]) -> None:
    import openwakeword

    train_script = os.path.join(os.path.dirname(openwakeword.__file__), "train.py")
    cmd = [sys.executable, train_script, "--training_config", CONFIG_PATH, *flags]
    logger.info("Executando: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-voices", action="store_true")
    parser.add_argument("--generate-positive", action="store_true")
    parser.add_argument("--generate-negative", action="store_true")
    parser.add_argument("--download-datasets", action="store_true")
    parser.add_argument("--augment", action="store_true")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    if not any(vars(args).values()):
        parser.error("Especifique ao menos uma flag (ou --all).")

    voice_paths = download_voices() if (args.download_voices or args.all) else [
        os.path.join(VOICES_DIR, f"pt_BR-{name}.onnx") for name in PT_BR_VOICES
    ]

    if args.generate_positive or args.all:
        generate_positive_clips(voice_paths)

    if args.generate_negative or args.all:
        generate_negative_clips(voice_paths)

    # Idempotente (pula qualquer artefato já baixado), então é seguro chamar
    # incondicionalmente: --augment/--train standalone (ex.: re-treinar depois
    # que os datasets já foram baixados uma vez) precisam desses caminhos no
    # config tanto quanto --download-datasets/--all.
    rir_paths, background_paths, feature_data_files, validation_path = download_negative_datasets()

    stub_dir = os.path.join(WORKSPACE, "piper_sample_generator_stub")
    ensure_piper_sample_generator_stub(stub_dir)

    config = build_training_config(
        target_phrase=TARGET_PHRASES,
        model_name=MODEL_NAME,
        output_dir=OUTPUT_DIR,
        piper_sample_generator_stub_dir=stub_dir,
        background_paths=background_paths,
        rir_paths=rir_paths,
        feature_data_files=feature_data_files,
        false_positive_validation_data_path=validation_path,
    )
    write_training_config(config, CONFIG_PATH)

    if args.augment or args.all:
        run_train_phase(["--augment_clips"])

    if args.train or args.all:
        run_train_phase(["--train_model"])
        trained_model_path = os.path.join(OUTPUT_DIR, MODEL_NAME, f"{MODEL_NAME}.onnx")
        copy_trained_model(trained_model_path, FINAL_MODEL_DEST)
        logger.info("Modelo copiado para %s", FINAL_MODEL_DEST)


if __name__ == "__main__":
    main()
