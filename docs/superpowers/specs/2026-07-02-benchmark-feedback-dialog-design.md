# Feedback do benchmark via diálogo Flet — Design

## Contexto

O pipeline de benchmark (F12, `MainPage.execute_benchmark_pipeline` em `main.py`) roda 10 áudios de
teste em sequência via `SpeechToText.run_benchmark(audio, reference)`. Esse método (`voice/speech.py`)
tinha uma chamada a `ask_user_feedback()` — uma função que pede `input()` de terminal ("O reconhecimento
foi correto? sim/não") — mas ela está comentada hoje, substituída por um `record_feedback(True)`
hardcoded, porque não funciona dentro do Docker: `docker compose up` não conecta o stdin do host ao
container (limitação conhecida do Compose, independente de `stdin_open`/`tty` no compose file), e mesmo
quando conectado (`docker attach`), bloquear em `input()` trava a mesma thread do event loop assíncrono
do Flet, congelando a janela sem nenhuma indicação visual do que está acontecendo.

O objetivo deste projeto é substituir esse feedback por terminal por um diálogo nativo do Flet
(sim/não), reaproveitando o padrão que já existe em `frontend/widgets/mic.py:_ask_command_feedback`
para o fluxo de mic ao vivo — e, requisito explícito do usuário, **sem** fazer `voice/speech.py`
depender de Flet ou de qualquer noção de UI/callback assíncrono. `speech.py` deve continuar sendo
puramente backend.

## Decisões confirmadas com o usuário

- O loop do benchmark **pausa por áudio**: roda áudio → pergunta sim/não → só então roda o próximo
  (mesmo padrão do fluxo de mic ao vivo hoje: ouvir → perguntar → registrar).
- O diálogo reaproveita/generaliza `MicMenu._ask_command_feedback` em vez de duplicar a lógica de
  `AlertDialog` + `asyncio.Event` em outro lugar.
- A orquestração (reconhecer → perguntar → registrar) fica inteiramente no frontend
  (`MainPage.execute_benchmark_pipeline`, `main.py`), não em `speech.py`. `run_benchmark()` deixa de
  existir como método empacotado — foi a abordagem escolhida em vez de injetar um callback
  `ask_feedback` como parâmetro de `run_benchmark`.

## Arquitetura

**`voice/speech.py` (backend, sem mudança de dependências):**
- Remove `run_benchmark()` (o wrapper que empacotava reconhecer+feedback) e a função solta
  `ask_user_feedback()` (terminal, hoje já sem uso real — a chamada está comentada).
- `_recognize_and_measure` passa a se chamar `recognize_and_measure` (sem underscore): deixa de ser
  "privado por acidente" porque passa a ser chamado deliberadamente de fora do módulo. Nenhuma mudança
  de lógica interna, só o nome (e os dois call sites internos que já o usam:
  `_listen_and_transcribe` e `_listen_and_transcribe_background`).
- Remove `import flet as ft` (linha 9), hoje morto — nenhum símbolo de `ft` é usado em todo o arquivo.
  Isso é a confirmação concreta de que o módulo fica livre de qualquer dependência de UI.
- `run_benchmark_transcription()` não muda — não pede feedback do usuário (usa WER automático contra a
  referência), fora do escopo deste projeto.

**`frontend/widgets/mic.py` (generaliza o diálogo existente):**
- `_ask_command_feedback(self, command_text: str) -> bool` vira
  `async def ask_feedback(self, title: str, content: str) -> bool`, parametrizando o texto do título e
  do conteúdo em vez de fixar "Comando executado com sucesso?". O mecanismo interno
  (`ft.AlertDialog` + `asyncio.Event` + `page.show_dialog`/`pop_dialog`) não muda.
- `run_speech_recognition` (fluxo de mic ao vivo) passa a chamar
  `await self.ask_feedback("Comando executado com sucesso?", f'"{text}"')` no lugar da chamada antiga —
  mesmo comportamento, só o nome/assinatura do método mudou.

**`main.py` (`MainPage`, orquestra o novo fluxo):**
- `execute_benchmark_pipeline` vira `async def`. Para cada áudio do dataset:
  1. `result = await asyncio.to_thread(speech_app.recognize_and_measure, audio, reference)` — offload
     para thread, mesmo padrão de `mic.py` (`asyncio.to_thread(self.speech.listen_for_command)`), para
     não bloquear o event loop do Flet durante a inferência.
  2. Se `result is None` (reconhecimento falhou — exceção já engolida e logada dentro de
     `recognize_and_measure`), loga aviso e pula para o próximo áudio, sem diálogo nem
     `record_feedback` para esse item.
  3. Caso contrário: `ok = await self.mic_menu.ask_feedback("O reconhecimento foi correto?", f'"{texto_referencia}"')`.
  4. `speech_app.record_feedback(ok)`.
- O atalho **F12**, hoje uma chamada síncrona direta dentro do handler síncrono `manage_shortcuts`, passa
  a agendar a coroutine via `self.page.run_task(self.execute_benchmark_pipeline)` — mesmo padrão usado em
  `mic.py:handle_mic_click` para `run_speech_recognition`. Isso é necessário porque agora o método faz
  `await`, e um handler de teclado síncrono não pode chamar uma coroutine diretamente.
- `execute_benchmark_transcription_pipeline` (Ctrl+P) não muda — não usa feedback de diálogo.

## Fluxo de dados

```
F12 (manage_shortcuts, síncrono)
        |
        v
page.run_task(execute_benchmark_pipeline)   -- agenda sem bloquear o event loop
        |
        v
for each (audio, reference) in dataset:
        |
        v
  await asyncio.to_thread(speech_app.recognize_and_measure, audio, reference)  -- roda em thread
        |
        +-- None? --> loga aviso, continue (próximo áudio)
        |
        v
  ok = await mic_menu.ask_feedback(titulo, conteudo)   -- AlertDialog + asyncio.Event, não bloqueia UI
        |
        v
  speech_app.record_feedback(ok)   -- grava métrica (CSV/Supabase), como já funciona hoje
```

Isso resolve os dois problemas originais: não depende mais de stdin de terminal (irrelevante dentro ou
fora do Docker), e nem a inferência nem a espera pelo clique do usuário bloqueiam a thread do event loop
— a janela do Flet continua responsiva durante todo o benchmark.

## Tratamento de erros

- Falha de reconhecimento por áudio individual (já tratada dentro de `recognize_and_measure` via
  `except sr.UnknownValueError` / `except Exception`, retornando `None`): pula feedback para aquele
  item, loga aviso, e o loop segue para o próximo áudio — não interrompe o benchmark inteiro.
- Nenhuma mudança no tratamento de erro de `SpeechToText()` (construção) ou de arquivos de áudio
  ausentes — comportamento já existente em `execute_benchmark_pipeline`, fora do escopo.

## Verificação

Não há suíte de testes automatizados para este fluxo (é um pipeline de benchmark manual, dependente de
GPU/áudio real). Verificação end-to-end manual:

1. Rodar o app (`python main.py`, local ou via `docker compose up` com X11 forwarding configurado).
2. Pressionar **F12** com `voice/benchmark_wav/` populado.
3. Confirmar que a janela do Flet continua respondendo (redimensionar/mover) enquanto cada áudio é
   processado — evidência de que a inferência está de fato rodando em thread separada.
4. Confirmar que o diálogo "O reconhecimento foi correto?" aparece após cada áudio, e que o benchmark só
   avança para o próximo áudio após clicar Sim/Não.
5. Conferir `voice/data/metrics.csv` (ou Supabase) após o run: `user_success` de cada linha deve
   corresponder à resposta clicada no diálogo, não mais sempre `True`.
6. Confirmar que o fluxo de mic ao vivo (F9/F8) continua pedindo feedback normalmente após a
   generalização de `ask_feedback` (sem regressão no caminho existente).
