-- VoiceWriter ASR Benchmark — Schema Supabase
-- Execute este script no SQL Editor do Supabase Studio (uma única vez).
-- Acesse: https://app.supabase.com → seu projeto → SQL Editor

-- Sessões de avaliação (uma por execução do benchmark)
CREATE TABLE IF NOT EXISTS sessions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    member_name  TEXT NOT NULL,          -- ex: "saraiva", "guilherme"
    model_name   TEXT NOT NULL,          -- ex: "distil-large-v3", "voxtral-mini-3b"
    model_source TEXT NOT NULL,          -- "huggingface" | "nemo" | "local"
    scenario     TEXT NOT NULL,          -- "dictation" | "command"
    started_at   TIMESTAMPTZ DEFAULT NOW(),
    hardware_info JSONB                  -- {"gpu": "RTX 3060", "cuda": "12.1", "ram_gb": 16}
);

-- Resultados de transcrições de ditado
CREATE TABLE IF NOT EXISTS transcription_results (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id        UUID REFERENCES sessions(id) ON DELETE CASCADE,
    audio_duration_ms FLOAT,
    transcribed_text  TEXT,
    reference_text    TEXT,              -- NULL em modo orgânico (sem referência fixa)
    is_benchmark      BOOLEAN DEFAULT FALSE,
    wer               FLOAT,            -- Word Error Rate (NULL se sem referência)
    cer               FLOAT,            -- Character Error Rate
    wer_normalized    FLOAT,            -- WER sem maiúsculas/pontuação (comparação justa)
    wer_substitutions FLOAT,            -- Taxa de palavras trocadas
    wer_deletions     FLOAT,            -- Taxa de palavras perdidas
    wer_insertions    FLOAT,            -- Taxa de palavras inventadas
    bleu_score        FLOAT,            -- BLEU score com smoothing
    rtf               FLOAT,            -- Real-Time Factor (< 1.0 = mais rápido que tempo real)
    latency_ms        FLOAT,
    avg_confidence    FLOAT,            -- Confiança média por palavra (Whisper word_timestamps)
    cold_start        BOOLEAN DEFAULT FALSE,  -- TRUE na 1ª inferência da sessão
    peak_memory_mb    FLOAT,
    user_success      BOOLEAN,          -- Feedback do usuário; NULL em modo benchmark
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Resultados de comandos de voz
CREATE TABLE IF NOT EXISTS command_results (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id         UUID REFERENCES sessions(id) ON DELETE CASCADE,
    spoken_text        TEXT,
    expected_command   TEXT,            -- NULL em modo orgânico
    recognized_command TEXT,
    success            BOOLEAN,
    latency_ms         FLOAT,
    created_at         TIMESTAMPTZ DEFAULT NOW()
);

-- Frases de referência para benchmark controlado
CREATE TABLE IF NOT EXISTS benchmark_phrases (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    text       TEXT NOT NULL,
    language   TEXT NOT NULL,           -- "pt-br" | "en"
    category   TEXT NOT NULL,           -- "dictation" | "command" | "technical"
    difficulty TEXT NOT NULL            -- "easy" | "medium" | "hard"
);

-- Políticas de acesso (RLS) — permite que a chave anon insira e leia dados
-- Projeto interno de pesquisa: todas as operações são permitidas
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE transcription_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE command_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE benchmark_phrases ENABLE ROW LEVEL SECURITY;

CREATE POLICY "allow_all_sessions" ON sessions FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all_transcription" ON transcription_results FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all_commands" ON command_results FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all_benchmark" ON benchmark_phrases FOR ALL USING (true) WITH CHECK (true);

-- Frases de benchmark sugeridas (PT-BR)
INSERT INTO benchmark_phrases (text, language, category, difficulty) VALUES
  ('o cachorro correu pelo parque ontem de tarde', 'pt-br', 'dictation', 'easy'),
  ('a reunião foi adiada para a próxima semana', 'pt-br', 'dictation', 'easy'),
  ('por favor abra o navegador e acesse o email', 'pt-br', 'dictation', 'easy'),
  ('o relatório financeiro do terceiro trimestre apresentou crescimento de doze por cento', 'pt-br', 'dictation', 'medium'),
  ('a implementação do algoritmo de reconhecimento de voz requer processamento em tempo real', 'pt-br', 'dictation', 'medium'),
  ('os parâmetros de configuração do modelo devem ser ajustados conforme o ambiente de produção', 'pt-br', 'dictation', 'hard'),
  ('a transformada rápida de Fourier é amplamente utilizada em processamento de sinais digitais', 'pt-br', 'dictation', 'hard'),
  ('abra o chrome', 'pt-br', 'command', 'easy'),
  ('feche o spotify', 'pt-br', 'command', 'easy'),
  ('abra o visual studio code', 'pt-br', 'command', 'medium'),
  ('feche o microsoft teams', 'pt-br', 'command', 'medium');
