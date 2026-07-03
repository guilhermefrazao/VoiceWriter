# Design — Expandir datasets de benchmark para 30 amostras

**Data:** 2026-07-02
**Autor:** Saraiva (com Claude)
**Status:** Aprovado — pronto para plano de implementação

## Problema

Os benchmarks de ASR usam amostras insuficientes: 10 comandos de voz e 5 textos
de transcrição. Amostras de menos tornam métricas como success_rate, WER e latência
estatisticamente frágeis. Queremos **30 amostras em cada dataset**.

Além do volume, há um problema estrutural: os datasets são dicts hardcoded em
`main.py` (`execute_benchmark_pipeline` e `execute_benchmark_transcription_pipeline`).
Escalar isso para 30 entradas — com várias pessoas contribuindo gravações — é frágil,
polui o `main.py` e gera conflitos de merge.

## Decisões de design

Três decisões definidas com o usuário:

1. **Fonte do áudio:** gravações reais humanas (máximo realismo — sotaque PT-BR,
   ruído real de microfone). Não TTS, não dataset externo.
2. **Coleta:** gravador guiado por CLI (a pessoa aperta Enter e fala; o script nomeia
   o WAV e o vincula à referência automaticamente).
3. **Corpus de referência:** Claude rascunha as frases faltantes em PT-BR; a equipe
   revisa antes de gravar.

Decisões secundárias:

- **30 frases distintas, 1 gravação cada** (não 10 frases × 3 locutores). O manifesto
  suporta múltiplos locutores no futuro, mas o escopo atual é 30 frases únicas.
- WAVs versionados normalmente no git (comandos ~3 MB total; transcrições ~48 MB).
  Os áudios atuais já são versionados assim. git-LFS fica como opção futura se incomodar.

## Arquitetura

A mudança central é **externalizar os datasets para arquivos de manifesto** que passam
a ser a única fonte de verdade. Três componentes independentes:

```
voice/benchmark_wav/
├── commands.json          # manifesto: 30 comandos
├── transcriptions.json    # manifesto: 30 textos de transcrição
├── commands/              # 1.wav .. 30.wav
└── transcriptions/        # 1.wav .. 30.wav
```

> **Nota de migração:** hoje os WAVs vivem soltos em `voice/benchmark_wav/` como
> `1.wav`..`10.wav` e `1_transcription.wav`..`5_transcription.wav`. A implementação
> deve movê-los para as subpastas `commands/` e `transcriptions/` (renomeando os de
> transcrição de `N_transcription.wav` → `N.wav`) e registrá-los no manifesto com o
> `recorded_by` apropriado. Nenhum áudio existente é descartado.

### Componente 1 — Manifesto (fonte de verdade)

Formato JSON, uma lista de objetos. Consumido tanto pelo gravador (escreve) quanto
pelos pipelines de benchmark (leem). Nenhum dict Python inline permanece.

```json
[
  { "id": 1,  "filename": "1.wav",  "reference": "Abra o Google",  "recorded_by": "saraiva" },
  { "id": 11, "filename": "11.wav", "reference": "Abra o Spotify",  "recorded_by": null }
]
```

- `recorded_by: null` → ainda não gravado. É como o gravador sabe o que falta,
  permitindo **retomar** e **dividir** o trabalho entre pessoas.
- `id` único e obrigatório. `filename` derivado do `id`.

### Componente 2 — Gravador guiado (`scripts/record_benchmark.py`)

Standalone, **não importa Flet**. Uso:

```
uv run python scripts/record_benchmark.py --dataset commands
uv run python scripts/record_benchmark.py --dataset transcriptions
```

Comportamento:

- Carrega o manifesto correspondente; pula entradas já gravadas (`recorded_by != null`).
- Para cada pendente: exibe a frase → aperta **Enter** → grava pelo microfone via
  `speech_recognition` (mesmo caminho de captura do app real, com detecção de silêncio)
  → salva `N.wav` a **16 kHz mono 16-bit** (formato que `recognize_and_measure` já espera)
  → grava `recorded_by` (lido de `MEMBER_NAME` no `.env`) no manifesto.
- Teclas: `r` regravar a última, `s` pular, `q` sair salvando progresso.
- Nunca sobrescreve um WAV existente sem confirmação explícita.

### Componente 3 — Pipelines refatorados (`main.py`)

`execute_benchmark_pipeline` e `execute_benchmark_transcription_pipeline` passam a
carregar as amostras do manifesto (via um pequeno helper de leitura), em vez do dict
inline. As chamadas a `recognize_and_measure`, `ask_feedback`, `record_feedback` e
`run_benchmark_transcription` permanecem inalteradas — só a origem dos dados muda.

Um helper compartilhado (ex.: `voice/utils/benchmark_manifest.py`) encapsula
carregar/validar/salvar o manifesto, usado tanto pelo gravador quanto pelos pipelines.

## Corpus de referência (a rascunhar)

Claude preenche os manifestos:

- **Comandos (30):** reaproveita os 10 atuais + ~20 novos. Verbos variados
  (abrir/fechar/executar/parar/iniciar), apps PT-BR e EN (alinhado ao ToDo #1 sobre
  nomes em inglês), e comandos de navegação.
- **Transcrição (30):** reaproveita os 5 atuais + ~25 novos. Temas diversos, tamanhos
  variados (curto a longo).

A equipe revisa o JSON antes de gravar.

## Tratamento de erros

- Manifesto ausente/malformado → erro claro apontando o arquivo e a linha.
- `id` duplicado ou `filename` colidindo → validação falha antes de gravar/rodar.
- WAV referenciado no manifesto mas ausente no disco → aviso no pipeline (pula a amostra,
  como o código atual já faz), e o gravador o trata como pendente.
- Microfone indisponível no gravador → mensagem clara, sai sem corromper o manifesto.

## Testes

- **Parser de manifesto:** carrega, valida ids únicos, detecta arquivos faltando.
- **Gravador com microfone mockado** (sem áudio real, roda em CI): salva WAV no formato
  correto (16 kHz mono 16-bit) e atualiza `recorded_by` no manifesto.
- **Integração ponta-a-ponta:** roda 1 amostra pelo pipeline refatorado e confirma que a
  métrica calculada é idêntica ao fluxo atual (não houve regressão na medição).

## Fora de escopo

- Múltiplos locutores por frase (o manifesto suporta, mas não implementamos agora).
- git-LFS para os áudios.
- Gravador embutido na UI Flet (foi descartado em favor do CLI).
