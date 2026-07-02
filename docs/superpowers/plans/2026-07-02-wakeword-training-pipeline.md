# Wakeword Training Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI tool that trains a custom openWakeWord model for the Portuguese wakeword "transcrição" (`voice/wakeword/models/transcricao.onnx`), consumed by the runtime listener built in `docs/superpowers/plans/2026-07-02-wakeword-runtime-integration.md`.

**Architecture:** openWakeWord's own training code (`train.py`, `data.py`) ships inside the `openwakeword` pip package and only needs raw positive/negative WAV clips on disk plus a YAML config — it doesn't require cloning any GitHub repo. The blocker is upstream: `train.py`'s built-in `--generate_clips` phase depends on an English-only synthetic-speech generator, which cannot pronounce "transcrição". This plan works around that by generating positive and negative clips ourselves with the `rhasspy/piper-sample-generator` CLI using four public pt_BR Piper voices (faber, edresson, jeff, cadu), writing them into the exact directory layout `train.py` expects, then invoking `train.py --augment_clips --train_model` (skipping `--generate_clips` entirely) for augmentation, feature extraction, training, and ONNX export — all upstream, unmodified code.

**Tech Stack:** Python 3.12, `openwakeword` (already a runtime dependency after the other plan), `piper-sample-generator` (PyPI, training-only), `torch`/`torchinfo`/`torchmetrics`/`datasets`/`pyyaml`/`scipy`/`tqdm` (training-only, NOT added to the main app's dependencies — they're heavy and irrelevant to runtime detection).

## Global Constraints

- Nothing in this plan touches `pyproject.toml`'s main `dependencies` list or `requirements.txt` (the Docker runtime image) — training-only packages are installed separately, documented in a `voice/wakeword/README.md` this plan creates.
- All heavy artifacts (cloned voice files, downloaded datasets, intermediate clips, training checkpoints) live under a gitignored `.wakeword_training/` directory at the repo root — never committed.
- Deterministic, non-network logic (config building, clip file organization, model copy) gets real unit tests per this repo's new `tests/` convention (see the runtime-integration plan's Task 1 for pytest setup — this plan assumes that task already ran). The dataset-download and actual model-training steps are inherently heavy (network, GPU-recommended, hours of compute) and are documented as manual/integration steps, not automated tests — this mirrors what was already agreed in `docs/superpowers/specs/2026-07-02-wakeword-design.md`'s Testing section.
- Target phrase variants: `["transcrição", "transcrição por favor"]` — a short list keeps the positive-clip vocabulary focused on the actual wakeword while giving the model slightly more phonetic context.

---

### Task 1: Config builder and YAML writer

**Files:**
- Create: `voice/wakeword/training.py`
- Test: `tests/wakeword/test_training_config.py`

**Interfaces:**
- Produces: `build_training_config(target_phrase, model_name, output_dir, piper_sample_generator_stub_dir, background_paths, rir_paths, feature_data_files, false_positive_validation_data_path, n_samples=2000, n_samples_val=500, steps=20000) -> dict`
- Produces: `write_training_config(config: dict, path: str) -> None`

- [ ] **Step 1: Write failing tests**

Create `tests/wakeword/test_training_config.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/wakeword/test_training_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'voice.wakeword.training'`.

- [ ] **Step 3: Implement `voice/wakeword/training.py` (config parts only)**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/wakeword/test_training_config.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add voice/wakeword/training.py tests/wakeword/test_training_config.py
git commit -m "feat: add wakeword training config builder"
```

---

### Task 2: `generate_samples` import stub for `train.py`

`train.py` unconditionally runs `from generate_samples import generate_samples` at import time (`sys.path.insert(0, config["piper_sample_generator_path"])`), even when only `--augment_clips --train_model` are used. Since we're deliberately not using the English-only tool that module normally comes from, we need a stub module that satisfies the import without ever being called.

**Files:**
- Modify: `voice/wakeword/training.py`
- Test: `tests/wakeword/test_training_stub.py`

**Interfaces:**
- Produces: `ensure_piper_sample_generator_stub(stub_dir: str) -> None`

- [ ] **Step 1: Write failing test**

Create `tests/wakeword/test_training_stub.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/wakeword/test_training_stub.py -v`
Expected: FAIL with `ImportError: cannot import name 'ensure_piper_sample_generator_stub'`.

- [ ] **Step 3: Add `ensure_piper_sample_generator_stub` to `voice/wakeword/training.py`**

Append:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/wakeword/test_training_stub.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add voice/wakeword/training.py tests/wakeword/test_training_stub.py
git commit -m "feat: add generate_samples import stub for openwakeword.train compatibility"
```

---

### Task 3: Positive/negative clip generation via `piper_sample_generator`

**Files:**
- Modify: `voice/wakeword/training.py`
- Test: `tests/wakeword/test_generate_voice_clips.py`

**Interfaces:**
- Produces: `PT_BR_VOICES: dict[str, str]` (voice name → Hugging Face download URL), `NEGATIVE_PHRASES: list[str]`.
- Produces: `generate_voice_clips(phrases: list[str], voice_model_paths: list[str], output_dir: str, samples_per_phrase: int, runner: Callable = subprocess.run) -> None`.

- [ ] **Step 1: Write failing test**

Create `tests/wakeword/test_generate_voice_clips.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/wakeword/test_generate_voice_clips.py -v`
Expected: FAIL with `ImportError: cannot import name 'generate_voice_clips'`.

- [ ] **Step 3: Add `PT_BR_VOICES`, `NEGATIVE_PHRASES`, and `generate_voice_clips` to `voice/wakeword/training.py`**

Add near the top of the file (after the imports):

```python
import shutil
import subprocess
from typing import Callable


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
```

Append to the end of the file:

```python
def generate_voice_clips(
    phrases: list[str],
    voice_model_paths: list[str],
    output_dir: str,
    samples_per_phrase: int,
    runner: Callable = subprocess.run,
) -> None:
    """Gera clipes WAV para cada frase, ciclando entre as vozes pt-BR fornecidas,
    via `python -m piper_sample_generator`. Cada frase é gerada num subdiretório
    temporário (o CLI sempre nomeia os arquivos 0.wav, 1.wav, ...) e depois
    movida para `output_dir` com um prefixo único para evitar colisão de nomes.
    """
    os.makedirs(output_dir, exist_ok=True)
    for phrase_idx, phrase in enumerate(phrases):
        phrase_dir = os.path.join(output_dir, f"_phrase_{phrase_idx}")
        cmd = [
            "python", "-m", "piper_sample_generator", phrase,
            "--max-samples", str(samples_per_phrase),
            "--output-dir", phrase_dir,
        ]
        for voice_path in voice_model_paths:
            cmd.extend(["--model", voice_path])
        runner(cmd, check=True)

        if os.path.isdir(phrase_dir):
            for wav_name in os.listdir(phrase_dir):
                shutil.move(
                    os.path.join(phrase_dir, wav_name),
                    os.path.join(output_dir, f"phrase{phrase_idx}_{wav_name}"),
                )
            os.rmdir(phrase_dir)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/wakeword/test_generate_voice_clips.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add voice/wakeword/training.py tests/wakeword/test_generate_voice_clips.py
git commit -m "feat: generate pt-BR positive/negative wakeword clips via piper_sample_generator"
```

---

### Task 4: Copy the trained model into place

**Files:**
- Modify: `voice/wakeword/training.py`
- Test: `tests/wakeword/test_copy_trained_model.py`

**Interfaces:**
- Produces: `copy_trained_model(source_onnx_path: str, dest_path: str) -> None`

- [ ] **Step 1: Write failing test**

Create `tests/wakeword/test_copy_trained_model.py`:

```python
from pathlib import Path

from voice.wakeword.training import copy_trained_model


def test_copy_trained_model_creates_dest_dirs_and_copies_bytes(tmp_path):
    source = tmp_path / "my_custom_model" / "transcricao" / "transcricao.onnx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"fake onnx bytes")
    dest = tmp_path / "voice" / "wakeword" / "models" / "transcricao.onnx"

    copy_trained_model(str(source), str(dest))

    assert dest.read_bytes() == b"fake onnx bytes"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/wakeword/test_copy_trained_model.py -v`
Expected: FAIL with `ImportError: cannot import name 'copy_trained_model'`.

- [ ] **Step 3: Add `copy_trained_model` to `voice/wakeword/training.py`**

Append:

```python
def copy_trained_model(source_onnx_path: str, dest_path: str) -> None:
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    shutil.copyfile(source_onnx_path, dest_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/wakeword/test_copy_trained_model.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add voice/wakeword/training.py tests/wakeword/test_copy_trained_model.py
git commit -m "feat: add copy_trained_model helper"
```

---

### Task 5: CLI entrypoint, dataset bootstrap, and setup docs

This ties Tasks 1-4 together with the (inherently heavy, network/GPU-bound, not-unit-testable) dataset bootstrap and the final `openwakeword.train` invocation. Verification for this task is manual, documented in Step 6.

**Files:**
- Create: `scripts/train_wakeword.py`
- Create: `voice/wakeword/README.md`
- Modify: `.gitignore`

**Interfaces:**
- Consumes everything from Tasks 1-4: `build_training_config`, `write_training_config`, `ensure_piper_sample_generator_stub`, `generate_voice_clips`, `copy_trained_model`, `PT_BR_VOICES`, `NEGATIVE_PHRASES`.

- [ ] **Step 1: Ignore the training workspace**

Append to `.gitignore`:

```
.wakeword_training/
```

- [ ] **Step 2: Write `voice/wakeword/README.md`**

```markdown
# Treinamento do wakeword "transcrição"

Este documento descreve como (re)treinar `voice/wakeword/models/transcricao.onnx`.

## Por que não é o pipeline 100% automático do openWakeWord

A geração sintética oficial do openWakeWord (`--generate_clips`) só fala inglês
(gerador treinado em LibriTTS). Como nosso wakeword é "transcrição" (português),
geramos os clipes positivos e negativos nós mesmos com 4 vozes Piper pt-BR
(faber, edresson, jeff, cadu) via `rhasspy/piper-sample-generator`, e
reaproveitamos o resto do pipeline oficial do openWakeWord (`train.py
--augment_clips --train_model`) sem modificações.

## Setup (uma vez)

Estas dependências são **só para treino**, não fazem parte do app (`pyproject.toml`
não é tocado):

```bash
pip install piper-sample-generator torch torchinfo torchmetrics datasets pyyaml scipy tqdm
```

Baixe as 4 vozes pt-BR:

```bash
mkdir -p .wakeword_training/voices
python scripts/train_wakeword.py --download-voices
```

## Rodando o treino

```bash
python scripts/train_wakeword.py --all
```

Isso executa, em ordem: geração dos clipes pt-BR, download dos datasets de
ruído/RIR/features negativas pré-computadas (alguns GB, cacheados em
`.wakeword_training/`), aumento de dados, treino, e cópia do modelo final para
`voice/wakeword/models/transcricao.onnx`.

Para rodar só uma etapa: `--generate-positive`, `--generate-negative`,
`--download-datasets`, `--augment`, `--train`.

Treino demora bem menos com GPU (o `train.py` do openWakeWord detecta CUDA
automaticamente via `torch.cuda.is_available()`).
```

- [ ] **Step 3: Implement `scripts/train_wakeword.py`**

```python
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


def download_voices() -> list[str]:
    os.makedirs(VOICES_DIR, exist_ok=True)
    paths = []
    for name, url in PT_BR_VOICES.items():
        onnx_path = os.path.join(VOICES_DIR, f"pt_BR-{name}.onnx")
        json_path = onnx_path + ".json"
        if not os.path.exists(onnx_path):
            logger.info("Baixando voz '%s'...", name)
            urllib.request.urlretrieve(url, onnx_path)
            urllib.request.urlretrieve(url + ".json", json_path)
        paths.append(onnx_path)
    return paths


def download_negative_datasets() -> tuple[list[str], dict[str, str], str]:
    """Baixa RIRs, ruído de fundo e features negativas pré-computadas.
    Reaproveita as mesmas fontes do notebook oficial do openWakeWord
    (dscripka/MIT_environmental_impulse_responses, features ACAV100M e o
    dataset de validação, ambos hospedados no Hugging Face por davidscripka).
    Idempotente: pula qualquer etapa cujo diretório/arquivo já exista.
    """
    import numpy as np
    import scipy.io.wavfile
    import datasets

    rir_dir = os.path.join(WORKSPACE, "mit_rirs")
    if not os.path.exists(rir_dir):
        os.makedirs(rir_dir)
        logger.info("Baixando Room Impulse Responses...")
        rir_dataset = datasets.load_dataset(
            "davidscripka/MIT_environmental_impulse_responses", split="train", streaming=True
        )
        for row in rir_dataset:
            name = row["audio"]["path"].split("/")[-1]
            scipy.io.wavfile.write(
                os.path.join(rir_dir, name), 16000, (row["audio"]["array"] * 32767).astype(np.int16)
            )

    features_path = os.path.join(WORKSPACE, "openwakeword_features_ACAV100M_2000_hrs_16bit.npy")
    if not os.path.exists(features_path):
        logger.info("Baixando features negativas pré-computadas (ACAV100M, vários GB)...")
        urllib.request.urlretrieve(
            "https://huggingface.co/datasets/davidscripka/openwakeword_features/resolve/main/"
            "openwakeword_features_ACAV100M_2000_hrs_16bit.npy",
            features_path,
        )

    validation_path = os.path.join(WORKSPACE, "validation_set_features.npy")
    if not os.path.exists(validation_path):
        logger.info("Baixando dataset de validação de falsos-positivos...")
        urllib.request.urlretrieve(
            "https://huggingface.co/datasets/davidscripka/openwakeword_features/resolve/main/"
            "validation_set_features.npy",
            validation_path,
        )

    return [rir_dir], {"ACAV100M_sample": features_path}, validation_path


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

    rir_paths, feature_data_files, validation_path = (
        download_negative_datasets() if (args.download_datasets or args.all) else ([], {}, "")
    )

    stub_dir = os.path.join(WORKSPACE, "piper_sample_generator_stub")
    ensure_piper_sample_generator_stub(stub_dir)

    config = build_training_config(
        target_phrase=TARGET_PHRASES,
        model_name=MODEL_NAME,
        output_dir=OUTPUT_DIR,
        piper_sample_generator_stub_dir=stub_dir,
        background_paths=[os.path.join(WORKSPACE, "mit_rirs")] if rir_paths else [],
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
```

- [ ] **Step 4: Verify the CLI's argument handling without running real training**

Run: `uv run python scripts/train_wakeword.py`
Expected: exits with the argparse error `Especifique ao menos uma flag (ou --all).` (confirms the script imports cleanly and argparse wiring works, without needing `torch`/`piper-sample-generator` installed yet).

- [ ] **Step 5: Run the full existing test suite to confirm nothing broke**

Run: `uv run pytest -v`
Expected: all tests from this plan and the runtime-integration plan still pass.

- [ ] **Step 6: Manual end-to-end training run (heavy, one-time, not part of CI)**

Follow `voice/wakeword/README.md`:

```bash
pip install piper-sample-generator torch torchinfo torchmetrics datasets pyyaml scipy tqdm
python scripts/train_wakeword.py --all
```

Expected after completion (this takes a long time — plan for at least several hours on CPU, much less with a CUDA GPU, plus one-time multi-GB downloads):
- `voice/wakeword/models/transcricao.onnx` exists.
- Say "transcrição" near the mic while running the app from the runtime-integration plan (with the real trained model now in place instead of the `hey_jarvis` stand-in from that plan's Task 9) — confirm the mic dialog opens.
- Say a phrase from `NEGATIVE_PHRASES` (e.g. "abrir chrome") without the wakeword prefix — confirm it does NOT trigger.

- [ ] **Step 7: Commit**

```bash
git add scripts/train_wakeword.py voice/wakeword/README.md .gitignore
git commit -m "feat: add wakeword training CLI and setup docs"
```
