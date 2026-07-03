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

## Teste rápido com um wakeword pronto ("hey jarvis")

Antes de investir num treino completo, dá pra validar a detecção pelo microfone
usando um modelo **pré-treinado** do openWakeWord (não precisa deste pipeline de
treino nenhum):

```bash
pip install openwakeword pyaudio
python scripts/test_wakeword_mic.py --model hey_jarvis
```

Fale "hey jarvis" perto do microfone e observe os scores no terminal (Ctrl-C
para sair). Isso baixa `hey_jarvis_v0.1.onnx` automaticamente e roda inferência
via backend ONNX (o backend `tflite` padrão conflita com numpy 2.x nesta venv
de treino).
