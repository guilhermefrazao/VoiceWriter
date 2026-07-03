# Benchmark 30 Samples — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expandir os datasets de benchmark de ASR para 30 amostras cada, externalizando-os de dicts hardcoded em `main.py` para manifestos JSON, com um gravador CLI guiado para coletar gravações reais.

**Architecture:** Um manifesto JSON por dataset (`commands`, `transcriptions`) é a única fonte de verdade. Um helper (`voice/utils/benchmark_manifest.py`) carrega/valida/salva. Um gravador CLI (`scripts/record_benchmark.py`) grava áudio real via `speech_recognition` e atualiza o manifesto. Os pipelines em `main.py` passam a ler o manifesto em vez de dicts inline.

**Tech Stack:** Python 3.12+, `uv`, `speech_recognition` + `pyaudio` (captura), `wave` (stdlib, validação de formato), `pytest` (testes).

## Global Constraints

- Gerenciador de pacotes: `uv` (rodar via `uv run python ...`).
- Python: `>=3.12` (conforme `pyproject.toml`).
- WAVs de benchmark: **16 kHz, mono, 16-bit** (`convert_rate=16000, convert_width=2`).
- O gravador **não pode importar Flet** nem `main.py`.
- Conteúdo das referências em **PT-BR**.
- Diretório base dos benchmarks: `voice/benchmark_wav/`.
- Manifesto: JSON com lista de objetos `{id:int, filename:str, reference:str, recorded_by:str|null}`, `id` único.

---

### Task 1: Test infra + helper de manifesto

**Files:**
- Modify: `pyproject.toml` (adicionar `pytest` em dev-dependencies)
- Create: `voice/utils/benchmark_manifest.py`
- Create: `tests/__init__.py` (vazio)
- Create: `tests/test_benchmark_manifest.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `@dataclass BenchmarkSample(id:int, filename:str, reference:str, recorded_by:str|None)`
  - `BENCHMARK_DIR: Path` (= `Path("voice/benchmark_wav")`)
  - `manifest_path(dataset:str) -> Path`
  - `audio_dir(dataset:str) -> Path`
  - `audio_path(dataset:str, sample:BenchmarkSample) -> Path`
  - `load_manifest(dataset:str) -> list[BenchmarkSample]` (levanta `ValueError` em id duplicado / JSON malformado)
  - `save_manifest(dataset:str, samples:list[BenchmarkSample]) -> None`
  - `pending_samples(samples:list[BenchmarkSample]) -> list[BenchmarkSample]`
  - `mark_recorded(samples:list[BenchmarkSample], sample_id:int, member:str) -> None`

- [ ] **Step 1: Adicionar pytest como dev dependency**

Em `pyproject.toml`, no bloco `[tool.uv]`, alterar `dev-dependencies`:

```toml
dev-dependencies = [
    "pip",
    "pytest>=8.0",
]
```

Depois rodar:

```bash
uv sync
```

- [ ] **Step 2: Escrever os testes que falham**

Criar `tests/__init__.py` vazio. Criar `tests/test_benchmark_manifest.py`:

```python
import json
import pytest
from voice.utils import benchmark_manifest as bm


def _write(tmp_path, name, data):
    p = tmp_path / name
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_load_manifest_parses_samples(tmp_path, monkeypatch):
    monkeypatch.setattr(bm, "BENCHMARK_DIR", tmp_path)
    _write(tmp_path, "commands.json", [
        {"id": 1, "filename": "1.wav", "reference": "Abra o Google", "recorded_by": "saraiva"},
        {"id": 2, "filename": "2.wav", "reference": "Feche o Firefox", "recorded_by": None},
    ])
    samples = bm.load_manifest("commands")
    assert len(samples) == 2
    assert samples[0].id == 1
    assert samples[0].reference == "Abra o Google"
    assert samples[1].recorded_by is None


def test_load_manifest_rejects_duplicate_ids(tmp_path, monkeypatch):
    monkeypatch.setattr(bm, "BENCHMARK_DIR", tmp_path)
    _write(tmp_path, "commands.json", [
        {"id": 1, "filename": "1.wav", "reference": "a", "recorded_by": None},
        {"id": 1, "filename": "x.wav", "reference": "b", "recorded_by": None},
    ])
    with pytest.raises(ValueError, match="duplicad"):
        bm.load_manifest("commands")


def test_pending_samples_filters_unrecorded(tmp_path, monkeypatch):
    monkeypatch.setattr(bm, "BENCHMARK_DIR", tmp_path)
    _write(tmp_path, "commands.json", [
        {"id": 1, "filename": "1.wav", "reference": "a", "recorded_by": "x"},
        {"id": 2, "filename": "2.wav", "reference": "b", "recorded_by": None},
    ])
    samples = bm.load_manifest("commands")
    pending = bm.pending_samples(samples)
    assert [s.id for s in pending] == [2]


def test_mark_recorded_and_save_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(bm, "BENCHMARK_DIR", tmp_path)
    _write(tmp_path, "commands.json", [
        {"id": 1, "filename": "1.wav", "reference": "a", "recorded_by": None},
    ])
    samples = bm.load_manifest("commands")
    bm.mark_recorded(samples, 1, "saraiva")
    bm.save_manifest("commands", samples)
    reloaded = bm.load_manifest("commands")
    assert reloaded[0].recorded_by == "saraiva"


def test_audio_path_uses_dataset_subdir(tmp_path, monkeypatch):
    monkeypatch.setattr(bm, "BENCHMARK_DIR", tmp_path)
    s = bm.BenchmarkSample(id=3, filename="3.wav", reference="x", recorded_by=None)
    assert bm.audio_path("commands", s) == tmp_path / "commands" / "3.wav"
```

- [ ] **Step 3: Rodar os testes e verificar que falham**

Run: `uv run pytest tests/test_benchmark_manifest.py -v`
Expected: FAIL com `ModuleNotFoundError: voice.utils.benchmark_manifest` (ou `AttributeError`).

- [ ] **Step 4: Implementar o helper**

Criar `voice/utils/benchmark_manifest.py`:

```python
"""Fonte de verdade dos datasets de benchmark de ASR.

Carrega, valida e salva os manifestos JSON em voice/benchmark_wav/.
Consumido tanto pelo gravador CLI quanto pelos pipelines de benchmark.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

BENCHMARK_DIR = Path("voice/benchmark_wav")

VALID_DATASETS = ("commands", "transcriptions")


@dataclass
class BenchmarkSample:
    id: int
    filename: str
    reference: str
    recorded_by: str | None


def _check_dataset(dataset: str) -> None:
    if dataset not in VALID_DATASETS:
        raise ValueError(f"Dataset inválido: {dataset!r}. Use um de {VALID_DATASETS}.")


def manifest_path(dataset: str) -> Path:
    _check_dataset(dataset)
    return BENCHMARK_DIR / f"{dataset}.json"


def audio_dir(dataset: str) -> Path:
    _check_dataset(dataset)
    return BENCHMARK_DIR / dataset


def audio_path(dataset: str, sample: BenchmarkSample) -> Path:
    return audio_dir(dataset) / sample.filename


def load_manifest(dataset: str) -> list[BenchmarkSample]:
    path = manifest_path(dataset)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise ValueError(f"Manifesto não encontrado: {path}") from e
    except json.JSONDecodeError as e:
        raise ValueError(f"Manifesto malformado em {path}: {e}") from e

    samples = [
        BenchmarkSample(
            id=item["id"],
            filename=item["filename"],
            reference=item["reference"],
            recorded_by=item.get("recorded_by"),
        )
        for item in raw
    ]

    seen: set[int] = set()
    for s in samples:
        if s.id in seen:
            raise ValueError(f"id duplicado no manifesto {path}: {s.id}")
        seen.add(s.id)

    return samples


def save_manifest(dataset: str, samples: list[BenchmarkSample]) -> None:
    path = manifest_path(dataset)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [
        {
            "id": s.id,
            "filename": s.filename,
            "reference": s.reference,
            "recorded_by": s.recorded_by,
        }
        for s in samples
    ]
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def pending_samples(samples: list[BenchmarkSample]) -> list[BenchmarkSample]:
    return [s for s in samples if s.recorded_by is None]


def mark_recorded(samples: list[BenchmarkSample], sample_id: int, member: str) -> None:
    for s in samples:
        if s.id == sample_id:
            s.recorded_by = member
            return
    raise ValueError(f"id não encontrado no manifesto: {sample_id}")
```

- [ ] **Step 5: Rodar os testes e verificar que passam**

Run: `uv run pytest tests/test_benchmark_manifest.py -v`
Expected: PASS (5 passed).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock voice/utils/benchmark_manifest.py tests/__init__.py tests/test_benchmark_manifest.py
git commit -m "feat: benchmark manifest helper + pytest infra"
```

---

### Task 2: Migrar WAVs existentes + escrever manifestos (corpus 30+30)

**Files:**
- Create: `voice/benchmark_wav/commands.json`
- Create: `voice/benchmark_wav/transcriptions.json`
- Move: `voice/benchmark_wav/{1..10}.wav` → `voice/benchmark_wav/commands/{1..10}.wav`
- Move: `voice/benchmark_wav/{1..5}_transcription.wav` → `voice/benchmark_wav/transcriptions/{1..5}.wav`
- Test: `tests/test_manifest_data.py`

**Interfaces:**
- Consumes: `benchmark_manifest.load_manifest`, `audio_path` (Task 1).
- Produces: os arquivos de dados que Tasks 3 e 4 consomem.

- [ ] **Step 1: Mover os WAVs existentes para as subpastas**

```bash
mkdir -p voice/benchmark_wav/commands voice/benchmark_wav/transcriptions
git mv voice/benchmark_wav/1.wav  voice/benchmark_wav/commands/1.wav
git mv voice/benchmark_wav/2.wav  voice/benchmark_wav/commands/2.wav
git mv voice/benchmark_wav/3.wav  voice/benchmark_wav/commands/3.wav
git mv voice/benchmark_wav/4.wav  voice/benchmark_wav/commands/4.wav
git mv voice/benchmark_wav/5.wav  voice/benchmark_wav/commands/5.wav
git mv voice/benchmark_wav/6.wav  voice/benchmark_wav/commands/6.wav
git mv voice/benchmark_wav/7.wav  voice/benchmark_wav/commands/7.wav
git mv voice/benchmark_wav/8.wav  voice/benchmark_wav/commands/8.wav
git mv voice/benchmark_wav/9.wav  voice/benchmark_wav/commands/9.wav
git mv voice/benchmark_wav/10.wav voice/benchmark_wav/commands/10.wav
git mv voice/benchmark_wav/1_transcription.wav voice/benchmark_wav/transcriptions/1.wav
git mv voice/benchmark_wav/2_transcription.wav voice/benchmark_wav/transcriptions/2.wav
git mv voice/benchmark_wav/3_transcription.wav voice/benchmark_wav/transcriptions/3.wav
git mv voice/benchmark_wav/4_transcription.wav voice/benchmark_wav/transcriptions/4.wav
git mv voice/benchmark_wav/5_transcription.wav voice/benchmark_wav/transcriptions/5.wav
```

- [ ] **Step 2: Criar `voice/benchmark_wav/commands.json`**

Ids 1–10 = reaproveitados (`recorded_by: "legacy"`). Ids 11–30 = novos (`recorded_by: null`, a gravar). Conteúdo exato:

```json
[
  { "id": 1,  "filename": "1.wav",  "reference": "Abra o Google", "recorded_by": "legacy" },
  { "id": 2,  "filename": "2.wav",  "reference": "Abra o Discord", "recorded_by": "legacy" },
  { "id": 3,  "filename": "3.wav",  "reference": "Feche o Firefox", "recorded_by": "legacy" },
  { "id": 4,  "filename": "4.wav",  "reference": "Execute o AnyDesk", "recorded_by": "legacy" },
  { "id": 5,  "filename": "5.wav",  "reference": "Inicia o System Manager", "recorded_by": "legacy" },
  { "id": 6,  "filename": "6.wav",  "reference": "Abra Devil May Cry", "recorded_by": "legacy" },
  { "id": 7,  "filename": "7.wav",  "reference": "Abra o Instagram", "recorded_by": "legacy" },
  { "id": 8,  "filename": "8.wav",  "reference": "Abrir Obsidian", "recorded_by": "legacy" },
  { "id": 9,  "filename": "9.wav",  "reference": "Pode abrir o File Explorer", "recorded_by": "legacy" },
  { "id": 10, "filename": "10.wav", "reference": "Pare o Blender", "recorded_by": "legacy" },
  { "id": 11, "filename": "11.wav", "reference": "Abra o Spotify", "recorded_by": null },
  { "id": 12, "filename": "12.wav", "reference": "Feche o Visual Studio Code", "recorded_by": null },
  { "id": 13, "filename": "13.wav", "reference": "Execute o Google Chrome", "recorded_by": null },
  { "id": 14, "filename": "14.wav", "reference": "Inicie o Telegram", "recorded_by": null },
  { "id": 15, "filename": "15.wav", "reference": "Abra o WhatsApp", "recorded_by": null },
  { "id": 16, "filename": "16.wav", "reference": "Feche o Steam", "recorded_by": null },
  { "id": 17, "filename": "17.wav", "reference": "Pare o Docker Desktop", "recorded_by": null },
  { "id": 18, "filename": "18.wav", "reference": "Abra a Calculadora", "recorded_by": null },
  { "id": 19, "filename": "19.wav", "reference": "Execute o Bloco de Notas", "recorded_by": null },
  { "id": 20, "filename": "20.wav", "reference": "Feche o Microsoft Edge", "recorded_by": null },
  { "id": 21, "filename": "21.wav", "reference": "Abra o Slack", "recorded_by": null },
  { "id": 22, "filename": "22.wav", "reference": "Inicie o OBS Studio", "recorded_by": null },
  { "id": 23, "filename": "23.wav", "reference": "Abra o Gerenciador de Tarefas", "recorded_by": null },
  { "id": 24, "filename": "24.wav", "reference": "Feche o Spotify", "recorded_by": null },
  { "id": 25, "filename": "25.wav", "reference": "Abra uma nova aba", "recorded_by": null },
  { "id": 26, "filename": "26.wav", "reference": "Feche a janela atual", "recorded_by": null },
  { "id": 27, "filename": "27.wav", "reference": "Abra o navegador e pesquise por notícias", "recorded_by": null },
  { "id": 28, "filename": "28.wav", "reference": "Execute o Zoom", "recorded_by": null },
  { "id": 29, "filename": "29.wav", "reference": "Abra o Explorador de Arquivos", "recorded_by": null },
  { "id": 30, "filename": "30.wav", "reference": "Desligue o computador", "recorded_by": null }
]
```

- [ ] **Step 3: Criar `voice/benchmark_wav/transcriptions.json`**

Ids 1–5 = reaproveitados (`recorded_by: "legacy"`, referências longas idênticas às atuais de `main.py`). Ids 6–30 = novos (`recorded_by: null`), temas e tamanhos variados. Conteúdo exato:

```json
[
  { "id": 1, "filename": "1.wav", "reference": "APIs e Arquitetura REST Resumo sobre APIs e arquitetura REST para a prova de back-end. Uma API, ou Interface de Programação de Aplicações, atua como uma ponte de comunicação padronizada entre diferentes sistemas de software. No padrão REST, utilizamos os métodos nativos do protocolo HTTP, como os verbos GET, POST, PUT e DELETE, para consultar e manipular recursos no servidor.É importante notar que, na arquitetura moderna, as respostas do servidor quase sempre retornam no formato JSON. Isso substituiu o antigo padrão XML porque o JSON é mais leve e facilita imensamente o parsing dos dados no lado do front-end da aplicação.", "recorded_by": "legacy" },
  { "id": 2, "filename": "2.wav", "reference": "Modelos de Computação em Nuvem Anotações da aula de hoje sobre computação em nuvem. Basicamente, precisamos memorizar as diferenças entre os três modelos principais de serviço: IaaS, PaaS e SaaS. Quando fazemos o deploy de uma aplicação usando PaaS, ou Plataforma como Serviço, a nuvem abstrai toda a infraestrutura subjacente, o que permite que a equipe de desenvolvimento foque exclusivamente na escrita do código. Um ponto crucial para sistemas corporativos é o contrato de nível de serviço, conhecido como SLA. Os grandes provedores garantem uma disponibilidade de 99,9% de uptime anual. Isso reduz drasticamente o tempo de inatividade quando comparamos com a manutenção dos antigos servidores on-premise locais.", "recorded_by": "legacy" },
  { "id": 3, "filename": "3.wav", "reference": "Evolução do Armazenamento: HDD vs SSD Comparativo rápido de hardware de armazenamento para o guia de montagem. A principal diferença estrutural entre um HDD e um SSD é a total ausência de partes mecânicas móveis no disco de estado sólido. Enquanto um disco rígido magnético tradicional opera girando a 7200 RPM e atinge taxas de transferência na faixa de 150 megabytes por segundo, a tecnologia flash mudou tudo. Hoje, um SSD com protocolo NVMe moderno, conectado diretamente no barramento PCIe da placa-mãe, ultrapassa com extrema facilidade a marca de 3500 megabytes por segundo. Essa transição, que ganhou muita força a partir de 2012, revolucionou o tempo de boot dos sistemas operacionais de desktop.", "recorded_by": "legacy" },
  { "id": 4, "filename": "4.wav", "reference": "Segurança da Informação e LGPD Revisão para o exame de segurança cibernética. O foco do capítulo 4 foi entender os vetores de ataque modernos, principalmente os ataques de negação de serviço distribuída, a sigla DDoS, e as táticas de engenharia social focadas em phishing. Para tentar mitigar o risco de invasão de contas corporativas, a implementação do 2FA, a autenticação de dois fatores, deixou de ser um diferencial e se tornou uma exigência básica. Além da parte técnica, existe a questão legal. As empresas no Brasil precisam se adequar rigorosamente às diretrizes da LGPD, a Lei Geral de Proteção de Dados, que foi sancionada em agosto de 2018. O não cumprimento dessas regras de privacidade pode resultar em multas que chegam a 2% do faturamento da empresa.", "recorded_by": "legacy" },
  { "id": 5, "filename": "5.wav", "reference": "Fundamentos de Inteligência Artificial Conceitos iniciais do módulo de inteligência artificial. O primeiro passo é saber diferenciar os termos Machine Learning e Deep Learning. O Deep Learning é uma subcategoria que utiliza redes neurais artificiais complexas, estruturadas com múltiplas camadas ocultas, para conseguir extrair padrões de datasets gigantescos, como milhões de imagens ou horas de áudio. Ontem à noite, durante o treinamento prático do nosso modelo de visão computacional, enfrentei um clássico problema de overfitting. A precisão do modelo no conjunto de dados de treino chegou a impressionantes 98%, mas, quando fui rodar a inferência nos dados de validação, a taxa de acerto despencou para apenas 65%. Preciso ajustar os hiperparâmetros amanhã.", "recorded_by": "legacy" },
  { "id": 6, "filename": "6.wav", "reference": "A fotossíntese é o processo pelo qual as plantas convertem luz solar, água e gás carbônico em glicose e oxigênio. Esse mecanismo ocorre nos cloroplastos, organelas ricas em clorofila, o pigmento verde responsável por captar a energia luminosa.", "recorded_by": null },
  { "id": 7, "filename": "7.wav", "reference": "O Brasil é um país de dimensões continentais, com cinco regiões bastante distintas entre si. O clima varia do equatorial na Amazônia ao subtropical no extremo sul, o que gera uma enorme diversidade de fauna e flora.", "recorded_by": null },
  { "id": 8, "filename": "8.wav", "reference": "Para preparar um bom café coado, aqueça a água até cerca de noventa graus, sem deixar ferver. Coloque duas colheres de pó para cada duzentos mililitros e despeje a água aos poucos, em movimentos circulares.", "recorded_by": null },
  { "id": 9, "filename": "9.wav", "reference": "A Revolução Industrial começou na Inglaterra no final do século dezoito e transformou profundamente a economia mundial. A introdução da máquina a vapor permitiu a mecanização da produção e o surgimento das primeiras grandes fábricas.", "recorded_by": null },
  { "id": 10, "filename": "10.wav", "reference": "O sistema solar é composto por oito planetas que orbitam o Sol. Os quatro mais próximos são rochosos, enquanto os mais distantes são gigantes gasosos, como Júpiter e Saturno, conhecidos por seus impressionantes anéis.", "recorded_by": null },
  { "id": 11, "filename": "11.wav", "reference": "Lembre-se de comprar leite, ovos, pão integral e frutas no mercado hoje à tarde.", "recorded_by": null },
  { "id": 12, "filename": "12.wav", "reference": "A reunião de equipe foi remarcada para a próxima quinta-feira às quatorze horas na sala de conferências do segundo andar.", "recorded_by": null },
  { "id": 13, "filename": "13.wav", "reference": "O exercício físico regular traz inúmeros benefícios para a saúde. Além de fortalecer o coração e melhorar a circulação, a atividade física libera endorfinas, que ajudam a reduzir o estresse e a ansiedade do dia a dia.", "recorded_by": null },
  { "id": 14, "filename": "14.wav", "reference": "A inteligência artificial generativa avançou muito nos últimos anos. Modelos de linguagem de grande escala hoje são capazes de escrever textos, traduzir idiomas e até gerar código de programação com notável fluência.", "recorded_by": null },
  { "id": 15, "filename": "15.wav", "reference": "O Rio Amazonas é o maior rio do mundo em volume de água. Ele nasce nos Andes peruanos e percorre milhares de quilômetros até desaguar no Oceano Atlântico, formando um delta imenso.", "recorded_by": null },
  { "id": 16, "filename": "16.wav", "reference": "Bom dia a todos. Gostaria de começar a apresentação agradecendo a presença de cada um e reforçando que as perguntas podem ser feitas ao final de cada bloco.", "recorded_by": null },
  { "id": 17, "filename": "17.wav", "reference": "A música popular brasileira, conhecida pela sigla MPB, reúne influências do samba, do jazz e do folclore nordestino. Artistas como Tom Jobim e Elis Regina ajudaram a levar esse gênero para o mundo inteiro.", "recorded_by": null },
  { "id": 18, "filename": "18.wav", "reference": "Investir com responsabilidade exige diversificar a carteira. Distribuir o dinheiro entre renda fixa, ações e fundos imobiliários reduz o risco e protege o patrimônio contra oscilações bruscas do mercado.", "recorded_by": null },
  { "id": 19, "filename": "19.wav", "reference": "A vacina funciona estimulando o sistema imunológico a reconhecer um agente infeccioso. Assim, quando o corpo entra em contato com o vírus real, ele já possui os anticorpos necessários para combatê-lo rapidamente.", "recorded_by": null },
  { "id": 20, "filename": "20.wav", "reference": "O aquecimento global é causado principalmente pela emissão de gases do efeito estufa. O aumento da temperatura média do planeta provoca o derretimento das calotas polares e a elevação do nível dos oceanos.", "recorded_by": null },
  { "id": 21, "filename": "21.wav", "reference": "Por favor, envie o relatório finalizado para o meu e-mail até o fim do expediente. Não se esqueça de anexar a planilha com os números atualizados do trimestre.", "recorded_by": null },
  { "id": 22, "filename": "22.wav", "reference": "A cidade de Ouro Preto, em Minas Gerais, preserva um dos mais belos conjuntos arquitetônicos do período colonial. Suas igrejas barrocas e ruas de pedra atraem turistas do mundo todo.", "recorded_by": null },
  { "id": 23, "filename": "23.wav", "reference": "Na programação orientada a objetos, uma classe funciona como um molde para criar objetos. Cada objeto possui atributos, que guardam seu estado, e métodos, que definem o seu comportamento.", "recorded_by": null },
  { "id": 24, "filename": "24.wav", "reference": "O jogo terminou empatado em dois a dois, mas a torcida saiu satisfeita com a atuação do time. O técnico destacou a garra dos jogadores mesmo diante de tantas dificuldades no segundo tempo.", "recorded_by": null },
  { "id": 25, "filename": "25.wav", "reference": "A leitura é um hábito que amplia o vocabulário e estimula a imaginação. Dedicar apenas trinta minutos por dia a um bom livro já é suficiente para perceber uma grande diferença ao longo do tempo.", "recorded_by": null },
  { "id": 26, "filename": "26.wav", "reference": "O contrato de aluguel tem validade de trinta meses e prevê reajuste anual pelo índice oficial de inflação. Qualquer rescisão antecipada deve ser comunicada com sessenta dias de antecedência.", "recorded_by": null },
  { "id": 27, "filename": "27.wav", "reference": "As abelhas desempenham um papel fundamental na polinização das plantas. Sem esses pequenos insetos, boa parte da produção agrícola mundial estaria seriamente ameaçada, afetando a segurança alimentar.", "recorded_by": null },
  { "id": 28, "filename": "28.wav", "reference": "Meu voo está marcado para as seis e meia da manhã, então preciso chegar ao aeroporto pelo menos duas horas antes. Já fiz o check-in online e despacharei apenas uma mala.", "recorded_by": null },
  { "id": 29, "filename": "29.wav", "reference": "A água é uma substância essencial para a vida e cobre cerca de setenta por cento da superfície do planeta. Ainda assim, apenas uma pequena fração dela é doce e própria para o consumo humano.", "recorded_by": null },
  { "id": 30, "filename": "30.wav", "reference": "Obrigado pela atenção de todos durante esta apresentação. Espero que o conteúdo tenha sido útil e coloco-me à disposição para esclarecer qualquer dúvida que ainda possa ter ficado.", "recorded_by": null }
]
```

- [ ] **Step 4: Escrever o teste de dados**

Criar `tests/test_manifest_data.py`:

```python
from voice.utils import benchmark_manifest as bm


def test_commands_manifest_has_30_unique():
    samples = bm.load_manifest("commands")
    assert len(samples) == 30
    assert len({s.id for s in samples}) == 30


def test_transcriptions_manifest_has_30_unique():
    samples = bm.load_manifest("transcriptions")
    assert len(samples) == 30
    assert len({s.id for s in samples}) == 30


def test_legacy_wavs_exist_on_disk():
    for dataset in ("commands", "transcriptions"):
        for s in bm.load_manifest(dataset):
            if s.recorded_by == "legacy":
                assert bm.audio_path(dataset, s).exists(), f"faltando: {s.filename}"
```

- [ ] **Step 5: Rodar o teste e verificar que passa**

Run: `uv run pytest tests/test_manifest_data.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add voice/benchmark_wav/ tests/test_manifest_data.py
git commit -m "feat: migrate benchmark WAVs to subdirs and add 30+30 manifests"
```

---

### Task 3: Gravador CLI guiado

**Files:**
- Create: `scripts/record_benchmark.py`
- Test: `tests/test_record_benchmark.py`

**Interfaces:**
- Consumes: `benchmark_manifest.{load_manifest, save_manifest, pending_samples, audio_path, mark_recorded}` (Task 1).
- Produces:
  - `save_audio_wav(audio_data, out_path: Path) -> None` (salva WAV 16 kHz mono 16-bit)
  - `record_pending(dataset:str, member:str, recognizer, mic_factory, prompt_fn) -> int` (retorna nº de amostras gravadas; injeta dependências para teste)
  - `main() -> None` (CLI)

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_record_benchmark.py`:

```python
import wave
import speech_recognition as sr
from pathlib import Path
import json

import scripts.record_benchmark as rec
from voice.utils import benchmark_manifest as bm


def _silence_audio(seconds=1, rate=44100):
    # AudioData cru: silêncio 16-bit mono
    frames = b"\x00\x00" * int(rate * seconds)
    return sr.AudioData(frames, rate, 2)


def test_save_audio_wav_writes_16k_mono_16bit(tmp_path):
    out = tmp_path / "sub" / "1.wav"
    rec.save_audio_wav(_silence_audio(), out)
    assert out.exists()
    with wave.open(str(out), "rb") as w:
        assert w.getframerate() == 16000
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2


def test_record_pending_records_and_marks(tmp_path, monkeypatch):
    monkeypatch.setattr(bm, "BENCHMARK_DIR", tmp_path)
    (tmp_path / "commands.json").write_text(json.dumps([
        {"id": 1, "filename": "1.wav", "reference": "Abra o Google", "recorded_by": "legacy"},
        {"id": 2, "filename": "2.wav", "reference": "Feche o Firefox", "recorded_by": None},
    ]), encoding="utf-8")

    class FakeRecognizer:
        def adjust_for_ambient_noise(self, source, duration=1):
            pass
        def listen(self, source, timeout=None, phrase_time_limit=None):
            return _silence_audio()

    class FakeMic:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    prompts = []
    n = rec.record_pending(
        "commands",
        member="tester",
        recognizer=FakeRecognizer(),
        mic_factory=lambda: FakeMic(),
        prompt_fn=lambda text: prompts.append(text) or "record",
    )
    assert n == 1
    assert prompts == ["Feche o Firefox"]
    reloaded = bm.load_manifest("commands")
    assert reloaded[1].recorded_by == "tester"
    assert bm.audio_path("commands", reloaded[1]).exists()
```

- [ ] **Step 2: Rodar os testes e verificar que falham**

Run: `uv run pytest tests/test_record_benchmark.py -v`
Expected: FAIL com `ModuleNotFoundError: scripts.record_benchmark`.

- [ ] **Step 3: Implementar o gravador**

Criar `scripts/__init__.py` vazio (para import em teste). Criar `scripts/record_benchmark.py`:

```python
"""Gravador CLI guiado para os datasets de benchmark de ASR.

Uso:
    uv run python scripts/record_benchmark.py --dataset commands
    uv run python scripts/record_benchmark.py --dataset transcriptions

Para cada amostra pendente mostra a frase, grava pelo microfone e atualiza
o manifesto. NÃO importa Flet nem main.py.
"""
from __future__ import annotations

import argparse
import os
import wave
from pathlib import Path

import speech_recognition as sr
from dotenv import load_dotenv

from voice.utils import benchmark_manifest as bm


def save_audio_wav(audio_data: sr.AudioData, out_path: Path) -> None:
    wav_bytes = audio_data.get_wav_data(convert_rate=16000, convert_width=2)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(wav_bytes)


def _default_prompt(reference: str) -> str:
    print(f"\n📝 Frase: \"{reference}\"")
    return input("[Enter]=gravar  s=pular  q=sair > ").strip().lower()


def record_pending(
    dataset: str,
    member: str,
    recognizer,
    mic_factory,
    prompt_fn=_default_prompt,
) -> int:
    samples = bm.load_manifest(dataset)
    recorded = 0
    for sample in bm.pending_samples(samples):
        choice = prompt_fn(sample.reference)
        if choice == "q":
            break
        if choice == "s":
            continue
        with mic_factory() as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=30)
        save_audio_wav(audio, bm.audio_path(dataset, sample))
        bm.mark_recorded(samples, sample.id, member)
        bm.save_manifest(dataset, samples)
        recorded += 1
    return recorded


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Gravador de benchmark de ASR")
    parser.add_argument("--dataset", required=True, choices=bm.VALID_DATASETS)
    args = parser.parse_args()

    member = os.getenv("MEMBER_NAME", "anonimo")
    recognizer = sr.Recognizer()
    recorded = record_pending(
        args.dataset,
        member=member,
        recognizer=recognizer,
        mic_factory=sr.Microphone,
    )
    print(f"\n✅ {recorded} amostra(s) gravada(s) em '{args.dataset}'.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Rodar os testes e verificar que passam**

Run: `uv run pytest tests/test_record_benchmark.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add scripts/__init__.py scripts/record_benchmark.py tests/test_record_benchmark.py
git commit -m "feat: guided CLI recorder for benchmark samples"
```

---

### Task 4: Refatorar os pipelines em `main.py` para ler o manifesto

**Files:**
- Modify: `main.py:46-119` (`execute_benchmark_pipeline` e `execute_benchmark_transcription_pipeline`)
- Test: `tests/test_benchmark_pipeline_data.py`

**Interfaces:**
- Consumes: `benchmark_manifest.{load_manifest, audio_path}` (Task 1); `SpeechToText.recognize_and_measure`, `record_feedback`, `run_benchmark_transcription` (inalterados).
- Produces: nada novo (comportamento equivalente, origem de dados diferente).

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_benchmark_pipeline_data.py` — garante que os pipelines iteram sobre o manifesto (não mais sobre dict inline). Testamos o helper de iteração que a refatoração extrai:

```python
from voice.utils import benchmark_manifest as bm


def test_command_samples_iterate_from_manifest():
    samples = bm.load_manifest("commands")
    # os pipelines devem conseguir montar (caminho, referência) para cada amostra
    pairs = [(bm.audio_path("commands", s), s.reference) for s in samples]
    assert len(pairs) == 30
    assert all(ref for _, ref in pairs)
```

- [ ] **Step 2: Rodar o teste e verificar que passa (dados) mas o pipeline ainda usa dict**

Run: `uv run pytest tests/test_benchmark_pipeline_data.py -v`
Expected: PASS (o helper já existe). Este teste ancora o contrato de dados; a refatoração abaixo alinha `main.py` a ele.

- [ ] **Step 3: Refatorar `execute_benchmark_pipeline`**

Em `main.py`, substituir o corpo do método (o dict `dataset_benchmark` e o loop sobre `pasta_audios`) por iteração sobre o manifesto. Novo corpo:

```python
    async def execute_benchmark_pipeline(self):
        from voice.speech import SpeechToText
        from voice.utils import benchmark_manifest as bm

        samples = bm.load_manifest("commands")
        speech_app = SpeechToText()

        logging.info(f"=== Iniciando Benchmark para {len(samples)} arquivos ===")
        for sample in samples:
            caminho_audio_completo = bm.audio_path("commands", sample)

            if caminho_audio_completo.exists():
                logging.info(f"\n🎧 Processando: {sample.filename}")
                logging.info(f"📝 Referência  : '{sample.reference}'")

                result = await asyncio.to_thread(
                    speech_app.recognize_and_measure,
                    str(caminho_audio_completo),
                    sample.reference,
                )

                if result is None:
                    logging.warning(f"Reconhecimento falhou para '{sample.filename}' — pulando feedback.")
                    continue

                ok = await self.mic_menu.ask_feedback(
                    "O reconhecimento foi correto?",
                    f'"{result[1]}"',
                )
                speech_app.record_feedback(ok)
            else:
                logging.info(f"\n ERRO: O arquivo '{sample.filename}' não foi encontrado.")
```

- [ ] **Step 4: Refatorar `execute_benchmark_transcription_pipeline`**

Substituir o corpo (dict `dataset_benchmark` + loop) por:

```python
    def execute_benchmark_transcription_pipeline(self):
        from voice.speech import SpeechToText
        from voice.utils import benchmark_manifest as bm

        samples = bm.load_manifest("transcriptions")
        speech_app = SpeechToText()

        logging.info(f"=== Iniciando Benchmark para {len(samples)} arquivos ===")
        for sample in samples:
            caminho_audio_completo = bm.audio_path("transcriptions", sample)

            if caminho_audio_completo.exists():
                logging.info(f"\n🎧 Processando: {sample.filename}")
                logging.info(f"📝 Referência  : '{sample.reference}'")

                speech_app.run_benchmark_transcription(
                    audio=str(caminho_audio_completo),
                    reference=sample.reference,
                )
            else:
                logging.info(f"\n ERRO: O arquivo '{sample.filename}' não foi encontrado.")
```

- [ ] **Step 5: Verificar que `main.py` importa e os testes passam**

Run: `uv run python -c "import ast; ast.parse(open('main.py').read()); print('ok')"`
Expected: `ok`

Run: `uv run pytest tests/ -v`
Expected: PASS (todos os testes).

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_benchmark_pipeline_data.py
git commit -m "refactor: benchmark pipelines read from manifest instead of inline dicts"
```

---

## Self-Review

**Spec coverage:**
- Externalizar datasets → manifestos (Task 1 helper, Task 2 dados, Task 4 consumo). ✓
- Gravador CLI guiado, 16 kHz mono 16-bit, sem Flet (Task 3). ✓
- Corpus rascunhado 30+30 (Task 2). ✓
- Migração dos WAVs existentes p/ subpastas (Task 2 Step 1). ✓
- Testes: parser, gravador mockado, integração de dados (Tasks 1, 3, 4). ✓
- Tratamento de erros: manifesto ausente/malformado, id duplicado, WAV ausente (Task 1 helper + pipelines pulam ausentes). ✓

**Placeholder scan:** nenhum TBD/TODO; todo código e conteúdo de manifesto estão completos inline. ✓

**Type consistency:** `BenchmarkSample`, `load_manifest`, `audio_path`, `pending_samples`, `mark_recorded`, `save_manifest`, `VALID_DATASETS` usados de forma idêntica entre tasks. `save_audio_wav`/`record_pending` consistentes entre Task 3 impl e teste. ✓

## Fora de escopo (do spec)
- Múltiplos locutores por frase; git-LFS; gravador embutido na UI Flet.
