# Métricas ASR — Guia do Estudo Científico

## Visão Geral

Este documento descreve o sistema de coleta de métricas para comparação científica de modelos ASR no VoiceWriter. Os dados são centralizados no Supabase e coletados por cada membro da equipe.

---

## Setup Inicial (uma vez por membro)

### 1. Criar conta no Supabase

1. Acesse [supabase.com](https://supabase.com) e crie uma conta gratuita
2. Crie um novo projeto
3. Em **SQL Editor**, cole e execute o conteúdo de `scripts/setup_supabase.sql`
4. Em **Project Settings → API**, copie:
   - `Project URL` → `SUPABASE_URL`
   - `anon public` key → `SUPABASE_KEY`

### 2. Configurar variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto (nunca commite esse arquivo):

```env
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=sua-chave-anon
MEMBER_NAME=saraiva    # use seu nome/apelido consistentemente
```

### 3. Instalar dependências

```bash
pip install -r requirements.txt
```

---

## Modos de Avaliação

### Modo Benchmark (WER objetivo)

O membro lê frases pré-definidas da tabela `benchmark_phrases` em voz alta. O modelo transcreve e o sistema calcula WER/CER comparando com a referência exata. **Este é o modo principal para o estudo científico.**

- `is_benchmark = True`
- `reference_text` preenchido
- WER, CER, BLEU calculados automaticamente

### Modo Orgânico (uso real)

O membro usa o app normalmente (ditado livre). O sistema captura latência e RTF. O usuário pode confirmar se a transcrição foi correta (botão de feedback).

- `is_benchmark = False`
- `reference_text = NULL`
- `user_success = True/False` (feedback explícito)

---

## Métricas Definidas

### Transcrição (ditado)

| Métrica | Fórmula | Interpretação |
|---|---|---|
| **WER** | (S + D + I) / N | Taxa de erro por palavra. 0 = perfeito, 1 = 100% errado |
| **CER** | Levenshtein(ref, hyp) / len(ref) | Mais sensível que WER para erros parciais |
| **WER Normalizado** | WER após lowercase + sem pontuação | Comparação justa entre modelos com pontuação diferente |
| **Substituições** | S / N | Palavras trocadas por outra |
| **Deleções** | D / N | Palavras da referência que o modelo perdeu |
| **Inserções** | I / N | Palavras que o modelo inventou |
| **BLEU** | n-gram precision com smoothing | Captura fluência. 1.0 = perfeito, 0.0 = sem sobreposição |
| **RTF** | latência / duração do áudio | < 1.0 = mais rápido que tempo real. Objetivo: < 0.3 |
| **Latência** | ms do início ao fim da inferência | Impacto direto na UX |
| **Confiança** | Média de probabilidade por palavra | Requer `word_timestamps=True` no Whisper |
| **Cold Start** | Flag na 1ª inferência da sessão | Separa aquecimento de performance estável |
| **Peak Memory** | MB de pico GPU/RAM | Custo de hardware do modelo |

### Comandos de voz

| Métrica | Descrição |
|---|---|
| **Success** | O comando foi executado corretamente? (True/False) |
| **Latência** | ms até execução do comando |
| **Expected vs Recognized** | Para benchmark: comparação de intenção |

---

## Interpretação do WER Breakdown

O breakdown em S/D/I é mais informativo que o WER total:

- **Alto em Substituições** → o modelo troca palavras (ex: "casa" → "cassa") — problema de vocabulário
- **Alto em Deleções** → o modelo perde palavras — problema de segmentação/VAD
- **Alto em Inserções** → o modelo inventa palavras — alucinação / ruído de fundo

---

## Integrando um Novo Modelo

O sistema usa uma interface mínima (`voice/utils/model_interface.py`). Para integrar um modelo:

```python
from voice.utils.model_interface import ASRModel, TranscriptionResult

class MeuModeloASR:
    def transcribe(self, audio_path: str, language: str) -> TranscriptionResult:
        # sua implementação aqui
        return TranscriptionResult(
            text="texto transcrito",
            language=language,
            segments=[],           # segmentos com timestamps se disponível
            audio_duration_s=3.5,
            latency_s=0.9,
            peak_memory_mb=512.0,
        )

    def get_name(self) -> str:
        return "meu-modelo-v1"

    def get_source(self) -> str:
        return "huggingface"  # ou "nemo" ou "local"
```

Para registrar a sessão e salvar resultados:

```python
from voice.utils.metrics_storage import create_session, save_transcription_result
from voice.utils.asr_metrics import analyze_transcription
import os

session_id = create_session(
    member_name=os.getenv("MEMBER_NAME", "anonimo"),
    model_name=modelo.get_name(),
    model_source=modelo.get_source(),
    scenario="dictation",
    hardware_info={"gpu": "RTX 3060", "cuda": "12.1"},
)

result = modelo.transcribe("audio.wav", language="pt")

metrics = analyze_transcription(
    hypothesis=result.text,
    reference="texto de referência",   # None em modo orgânico
    start_time=t0,
    end_time=t1,
    audio_duration_s=result.audio_duration_s,
    segments=result.segments,
    cold_start=True,                   # True apenas na 1ª inferência
    peak_memory_mb=result.peak_memory_mb,
)

save_transcription_result(session_id, metrics)
```

---

## Sync Offline

Se a internet falhar durante uma sessão, os dados ficam em `voice/data/offline_queue.json`. Para sincronizar depois:

```bash
python scripts/sync_offline.py
```

---

## Frases de Benchmark (PT-BR)

As frases já estão inseridas na tabela `benchmark_phrases` pelo script SQL. Para consultar:

```sql
SELECT * FROM benchmark_phrases ORDER BY difficulty, category;
```

Para adicionar novas frases:

```sql
INSERT INTO benchmark_phrases (text, language, category, difficulty)
VALUES ('sua frase aqui', 'pt-br', 'dictation', 'medium');
```

---

## Dashboard no Supabase Studio

O Supabase Studio tem um editor de tabelas e permite queries SQL diretamente. Para comparar modelos:

```sql
-- WER médio por modelo
SELECT model_name, AVG(wer) as wer_medio, AVG(rtf) as rtf_medio, COUNT(*) as amostras
FROM transcription_results tr
JOIN sessions s ON tr.session_id = s.id
WHERE tr.is_benchmark = TRUE
GROUP BY model_name
ORDER BY wer_medio;
```
