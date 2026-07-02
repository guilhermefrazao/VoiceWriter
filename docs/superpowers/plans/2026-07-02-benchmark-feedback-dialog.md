# Benchmark Feedback via Flet Dialog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the terminal-based `ask_user_feedback()` in the F12 benchmark pipeline with a Flet `AlertDialog` (reusing the existing pattern from the live-mic flow), without giving `voice/speech.py` any dependency on Flet or UI callbacks.

**Architecture:** `voice/speech.py` stays pure backend (no Flet import, no callback parameters). `frontend/widgets/mic.py` generalizes its existing yes/no dialog into a reusable `ask_feedback(title, content)` coroutine. `main.py`'s `MainPage.execute_benchmark_pipeline` becomes `async def` and directly orchestrates recognize → dialog → record_feedback per audio file, offloading inference to a thread via `asyncio.to_thread` so the dialog wait and the recognition never block the Flet event loop.

**Tech Stack:** Python 3, Flet (`ft.AlertDialog`, `page.show_dialog`/`pop_dialog`, `page.run_task`), `asyncio` (`asyncio.Event`, `asyncio.to_thread`).

## Global Constraints

- `voice/speech.py` must not import `flet` or accept any callback/UI parameter — spec requirement, confirmed with user.
- The benchmark loop must pause per audio file: run recognition → ask feedback → wait for the click → only then move to the next file (confirmed with user, not "process all then ask").
- Reuse `MicMenu`'s existing `AlertDialog` + `asyncio.Event` pattern (`frontend/widgets/mic.py`) instead of writing a second, separate dialog implementation (confirmed with user).
- Any inference call (`recognize_and_measure`) invoked from an `async def` on the Flet event loop must be wrapped in `asyncio.to_thread(...)` — mirrors the existing `mic.py:71` pattern (`asyncio.to_thread(self.speech.listen_for_command)`) and is required to avoid freezing the GUI during model inference.
- If recognition returns `None` (exception already caught and logged inside `recognize_and_measure`), skip the dialog and `record_feedback` for that audio file — do not ask the user to judge a transcription that doesn't exist.

Spec: `docs/superpowers/specs/2026-07-02-benchmark-feedback-dialog-design.md`

---

### Task 1: Rename `_recognize_and_measure` to `recognize_and_measure` in `voice/speech.py`

**Files:**
- Modify: `voice/speech.py:392` (call site in `_listen_and_transcribe`)
- Modify: `voice/speech.py:413` (call site in `_listen_and_transcribe_background`)
- Modify: `voice/speech.py:461` (method definition)

**Interfaces:**
- Consumes: nothing new.
- Produces: `SpeechToText.recognize_and_measure(self, audio, reference: str | None = None) -> tuple[dict, str] | None` — a public method, same signature and behavior as the old `_recognize_and_measure`. Task 3 will call this from `main.py`.

This is a pure rename (no logic change) — it turns an accidentally-private method into a deliberate public entry point, since `main.py` will call it directly starting in Task 3.

- [ ] **Step 1: Rename the method definition**

In `voice/speech.py`, find:

```python
    def _recognize_and_measure(self, audio, reference: str | None = None) -> tuple[dict, str] | None:
```

Replace with:

```python
    def recognize_and_measure(self, audio, reference: str | None = None) -> tuple[dict, str] | None:
```

- [ ] **Step 2: Update the two internal call sites**

In `voice/speech.py`, inside `_listen_and_transcribe`, find:

```python
                result = self._recognize_and_measure(audio)
```

Replace with:

```python
                result = self.recognize_and_measure(audio)
```

Inside `_listen_and_transcribe_background`, find:

```python
            result = self._recognize_and_measure(audio)
```

Replace with:

```python
            result = self.recognize_and_measure(audio)
```

- [ ] **Step 3: Update the `run_benchmark_transcription` call site**

In `voice/speech.py`, find:

```python
    def run_benchmark_transcription(self, audio, reference):
        self._recognize_and_measure(audio, reference)
```

Replace with:

```python
    def run_benchmark_transcription(self, audio, reference):
        self.recognize_and_measure(audio, reference)
```

- [ ] **Step 4: Verify no stale references remain and the module still compiles**

Run: `grep -n "_recognize_and_measure" voice/speech.py`
Expected: no output (empty — every reference has been renamed).

Run: `python -m py_compile voice/speech.py && echo OK`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add voice/speech.py
git commit -m "refactor: make recognize_and_measure a public SpeechToText method"
```

---

### Task 2: Generalize the feedback dialog in `frontend/widgets/mic.py`

**Files:**
- Modify: `frontend/widgets/mic.py:74` (call site in `run_speech_recognition`)
- Modify: `frontend/widgets/mic.py:82-109` (method definition, currently `_ask_command_feedback`)

**Interfaces:**
- Consumes: `self.page` (`ft.Page`, already available on `MicMenu`).
- Produces: `MicMenu.ask_feedback(self, title: str, content: str) -> bool` (async, public) — replaces `_ask_command_feedback(self, command_text: str) -> bool`. Task 3 calls this as `self.mic_menu.ask_feedback(title, content)` from `main.py`.

Same `AlertDialog` + `asyncio.Event` mechanism as before — only the method name and its two hardcoded strings (`"Comando executado com sucesso?"` and the quoted text) become parameters.

- [ ] **Step 1: Rename the method and parameterize the dialog text**

In `frontend/widgets/mic.py`, find:

```python
    async def _ask_command_feedback(self, command_text: str) -> bool:
        answered = asyncio.Event()
        result: dict[str, bool] = {}

        async def on_sim(_):
            result["ok"] = True
            self.page.pop_dialog()
            answered.set()

        async def on_nao(_):
            result["ok"] = False
            self.page.pop_dialog()
            answered.set()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Comando executado com sucesso?"),
            content=ft.Text(f'"{command_text}"', italic=True),
            actions=[
                ft.Button("Sim", bgcolor="#055b5f", on_click=on_sim),
                ft.Button("Não", bgcolor="#FF2C2C", on_click=on_nao),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.show_dialog(dialog)
        await answered.wait()
        return result.get("ok", False)
```

Replace with:

```python
    async def ask_feedback(self, title: str, content: str) -> bool:
        answered = asyncio.Event()
        result: dict[str, bool] = {}

        async def on_sim(_):
            result["ok"] = True
            self.page.pop_dialog()
            answered.set()

        async def on_nao(_):
            result["ok"] = False
            self.page.pop_dialog()
            answered.set()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(title),
            content=ft.Text(content, italic=True),
            actions=[
                ft.Button("Sim", bgcolor="#055b5f", on_click=on_sim),
                ft.Button("Não", bgcolor="#FF2C2C", on_click=on_nao),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.show_dialog(dialog)
        await answered.wait()
        return result.get("ok", False)
```

- [ ] **Step 2: Update the call site in `run_speech_recognition`**

In `frontend/widgets/mic.py`, find:

```python
            if text:
                sr = await self._ask_command_feedback(text)
                self.speech.record_feedback(sr)
```

Replace with:

```python
            if text:
                sr = await self.ask_feedback("Comando executado com sucesso?", f'"{text}"')
                self.speech.record_feedback(sr)
```

- [ ] **Step 3: Verify no stale references remain and the module still compiles**

Run: `grep -n "_ask_command_feedback" frontend/widgets/mic.py`
Expected: no output (empty).

Run: `python -m py_compile frontend/widgets/mic.py && echo OK`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add frontend/widgets/mic.py
git commit -m "refactor: generalize MicMenu's yes/no dialog into ask_feedback(title, content)"
```

---

### Task 3: Wire the benchmark pipeline to the dialog and remove the terminal-based feedback code

**Files:**
- Modify: `voice/speech.py` (remove dead `import flet as ft`, remove `ask_user_feedback()`, remove `run_benchmark()`)
- Modify: `main.py:1-46` (add `import asyncio`, make `execute_benchmark_pipeline` async and orchestrate feedback)
- Modify: `main.py:220-221` (F12 handler schedules the now-async pipeline via `page.run_task`)

**Interfaces:**
- Consumes: `SpeechToText.recognize_and_measure(audio, reference)` (Task 1), `MicMenu.ask_feedback(title, content)` (Task 2), `SpeechToText.record_feedback(ok: bool)` (unchanged, already public).
- Produces: `MainPage.execute_benchmark_pipeline(self)` becomes a coroutine; nothing else depends on its return value (F12 handler just schedules it, fire-and-forget via `page.run_task`).

This task must land as one commit: removing `run_benchmark()` from `speech.py` and rewriting `main.py`'s pipeline are two halves of the same change — `main.py` would break (`AttributeError: 'SpeechToText' object has no attribute 'run_benchmark'`) if committed separately.

- [ ] **Step 1: Remove the dead `flet` import and the terminal-based feedback code from `voice/speech.py`**

In `voice/speech.py`, find:

```python
import speech_recognition as sr
import logging
import os
import time
import sys
import io
import numpy as np
import threading
import flet as ft
from pathlib import Path
```

Replace with:

```python
import speech_recognition as sr
import logging
import os
import time
import sys
import io
import numpy as np
import threading
from pathlib import Path
```

Then find:

```python
def ask_user_feedback() -> bool:
        """
        Pede o input do usuário via terminal e retorna True para 'sim' e False para 'não'.
        """
        while True:
            # Pega o input, remove espaços em branco nas pontas e joga para minúsculas
            resposta = input("O reconhecimento foi correto? (sim/não): ").strip().lower()
            
            # Aceita variações comuns de "sim"
            if resposta in ['sim', 's', 'yes', 'y']:
                return True
            # Aceita variações comuns de "não"
            elif resposta in ['não', 'nao', 'n', 'no']:
                return False
            else:
                # Se digitar algo diferente, o loop repete a pergunta
                print("⚠️ Entrada inválida. Por favor, responda apenas com 'sim' ou 'não'.")

def _parse_model_key(model_key: str) -> tuple[str, str]:
```

Replace with:

```python
def _parse_model_key(model_key: str) -> tuple[str, str]:
```

Then find:

```python
    # Benchmark

    def run_benchmark(self, audio, reference):
        self.recognize_and_measure(audio, reference)
        #sr = ask_user_feedback()
        self.record_feedback(True)

    def run_benchmark_transcription(self, audio, reference):
```

Replace with:

```python
    # Benchmark

    def run_benchmark_transcription(self, audio, reference):
```

- [ ] **Step 2: Verify `voice/speech.py` still compiles and has no leftover references**

Run: `grep -n "ask_user_feedback\|run_benchmark(\|import flet" voice/speech.py`
Expected: no output (empty).

Run: `python -m py_compile voice/speech.py && echo OK`
Expected: `OK`

- [ ] **Step 3: Add `import asyncio` to `main.py`**

In `main.py`, find:

```python
import flet as ft
import argparse
import logging
import os
from pathlib import Path
import sys
import threading
```

Replace with:

```python
import flet as ft
import argparse
import asyncio
import logging
import os
from pathlib import Path
import sys
import threading
```

- [ ] **Step 4: Rewrite `execute_benchmark_pipeline` as an async orchestrator**

In `main.py`, find:

```python
    def execute_benchmark_pipeline(self):
        from voice.speech import SpeechToText
        pasta_audios = Path(r"voice/benchmark_wav")

        dataset_benchmark = {
            "1.wav": "Abra o Google",
            "2.wav": "Abra o Discord",
            "3.wav": "Feche o Fire Fox",
            "4.wav": "Execute o Any Desk",
            "5.wav": "Inicia o System Manager",
            "6.wav": "Abra Devil may Cry",
            "7.wav": "Abre o Intagram",
            "8.wav": "Abrir Obsidian",
            "9.wav": "Pode abrir o File Explorer",
            "10.wav": "Pare o Blender",
        }
        speech_app = SpeechToText()

        logging.info(f"=== Iniciando Benchmark para {len(dataset_benchmark)} arquivos ===")
        for nome_arquivo, texto_referencia in dataset_benchmark.items():
            
            caminho_audio_completo = pasta_audios / nome_arquivo
            
            if caminho_audio_completo.exists():
                logging.info(f"\n🎧 Processando: {nome_arquivo}")
                logging.info(f"📝 Referência  : '{texto_referencia}'")
                
                speech_app.run_benchmark(
                    audio=str(caminho_audio_completo), 
                    reference=texto_referencia
                )
            else:
                logging.info(f"\n ERRO: O arquivo '{nome_arquivo}' não foi encontrado na pasta.")
```

Replace with:

```python
    async def execute_benchmark_pipeline(self):
        from voice.speech import SpeechToText
        pasta_audios = Path(r"voice/benchmark_wav")

        dataset_benchmark = {
            "1.wav": "Abra o Google",
            "2.wav": "Abra o Discord",
            "3.wav": "Feche o Fire Fox",
            "4.wav": "Execute o Any Desk",
            "5.wav": "Inicia o System Manager",
            "6.wav": "Abra Devil may Cry",
            "7.wav": "Abre o Intagram",
            "8.wav": "Abrir Obsidian",
            "9.wav": "Pode abrir o File Explorer",
            "10.wav": "Pare o Blender",
        }
        speech_app = SpeechToText()

        logging.info(f"=== Iniciando Benchmark para {len(dataset_benchmark)} arquivos ===")
        for nome_arquivo, texto_referencia in dataset_benchmark.items():
            
            caminho_audio_completo = pasta_audios / nome_arquivo
            
            if caminho_audio_completo.exists():
                logging.info(f"\n🎧 Processando: {nome_arquivo}")
                logging.info(f"📝 Referência  : '{texto_referencia}'")

                result = await asyncio.to_thread(
                    speech_app.recognize_and_measure,
                    str(caminho_audio_completo),
                    texto_referencia,
                )

                if result is None:
                    logging.warning(f"Reconhecimento falhou para '{nome_arquivo}' — pulando feedback.")
                    continue

                ok = await self.mic_menu.ask_feedback(
                    "O reconhecimento foi correto?",
                    f'"{texto_referencia}"',
                )
                speech_app.record_feedback(ok)
            else:
                logging.info(f"\n ERRO: O arquivo '{nome_arquivo}' não foi encontrado na pasta.")
```

- [ ] **Step 5: Schedule the async pipeline from the F12 handler instead of calling it directly**

In `main.py`, find:

```python
            if e.key == "F12":
                self.execute_benchmark_pipeline()
```

Replace with:

```python
            if e.key == "F12":
                self.page.run_task(self.execute_benchmark_pipeline)
```

- [ ] **Step 6: Verify `main.py` compiles and there are no leftover references to the removed API**

Run: `grep -n "run_benchmark(audio\|\.run_benchmark(" main.py`
Expected: no output (empty — only `run_benchmark_transcription` calls remain, which is a different, untouched method).

Run: `python -m py_compile main.py && echo OK`
Expected: `OK`

- [ ] **Step 7: Simulate the control flow with a standalone script (no GPU/audio/Flet required)**

This project has no automated test suite (confirmed during design — it's a manual-verification-only benchmark tool). To verify the control flow (thread offload, skip-on-`None`, pause-until-dialog-answered, in-order feedback) without needing the real GPU models, Flet window, or audio hardware, write a throwaway script with fake stand-ins that mirror the real signatures.

Create `C:\Users\guilh\AppData\Local\Temp\claude\C--Users-guilh-Documents-VoiceWriter\197e970d-7e19-477b-88eb-355e82eb4e06\scratchpad\repro_benchmark_flow.py`:

```python
import asyncio
import threading

calls = []


class FakeSpeech:
    def recognize_and_measure(self, audio, reference):
        calls.append(("recognize", threading.current_thread().name, audio))
        if audio == "bad.wav":
            return None
        return ({"wer": 0.0}, "texto reconhecido")

    def record_feedback(self, ok):
        calls.append(("record_feedback", ok))


class FakeMicMenu:
    def __init__(self, answers):
        self._answers = iter(answers)

    async def ask_feedback(self, title, content):
        calls.append(("ask_feedback", title, content, threading.current_thread().name))
        return next(self._answers)


async def run_pipeline(speech_app, mic_menu, dataset):
    for audio, reference in dataset.items():
        result = await asyncio.to_thread(speech_app.recognize_and_measure, audio, reference)
        if result is None:
            calls.append(("skip", audio))
            continue
        ok = await mic_menu.ask_feedback("O reconhecimento foi correto?", f'"{reference}"')
        speech_app.record_feedback(ok)


async def main():
    main_thread = threading.current_thread().name
    dataset = {"1.wav": "Abra o Google", "bad.wav": "Ref para falha", "2.wav": "Abra o Discord"}
    speech_app = FakeSpeech()
    mic_menu = FakeMicMenu(answers=[True, False])

    await run_pipeline(speech_app, mic_menu, dataset)

    # 1. Inference ran off the main/event-loop thread.
    recognize_threads = {name for kind, name, _ in calls if kind == "recognize"}
    assert main_thread not in recognize_threads, f"recognize_and_measure ran on the event loop thread: {recognize_threads}"

    # 2. The failing audio was skipped (no ask_feedback/record_feedback for it).
    assert ("skip", "bad.wav") in calls, "expected bad.wav to be skipped"

    # 3. Exactly two feedback dialogs were shown (for the two audios that succeeded), in order.
    ask_calls = [c for c in calls if c[0] == "ask_feedback"]
    assert len(ask_calls) == 2, f"expected 2 ask_feedback calls, got {len(ask_calls)}"

    # 4. record_feedback received exactly the dialog's answers, in order.
    record_calls = [c[1] for c in calls if c[0] == "record_feedback"]
    assert record_calls == [True, False], f"expected [True, False], got {record_calls}"

    # 5. Recognize -> ask_feedback -> record_feedback happen strictly in order per audio
    #    (no audio's dialog fires before its own recognize call completes).
    kinds = [c[0] for c in calls if c[0] != "skip"]
    assert kinds == ["recognize", "ask_feedback", "record_feedback", "recognize", "recognize", "ask_feedback", "record_feedback"], kinds

    print("ALL ASSERTIONS PASSED")
    print(calls)


asyncio.run(main())
```

- [ ] **Step 8: Run the reproduction script**

Run: `python "C:\Users\guilh\AppData\Local\Temp\claude\C--Users-guilh-Documents-VoiceWriter\197e970d-7e19-477b-88eb-355e82eb4e06\scratchpad\repro_benchmark_flow.py"`
Expected: `ALL ASSERTIONS PASSED` followed by the recorded call list. If any assertion fails, re-check Step 4's control flow against the assertion it violated before moving on.

- [ ] **Step 9: Commit**

```bash
git add voice/speech.py main.py
git commit -m "feat: ask benchmark feedback via Flet dialog instead of terminal input()"
```

---

### Task 4: Manual end-to-end verification (human-in-the-loop)

**Files:** none — this task drives the real app, it doesn't change code.

This step needs a real display, microphone, and the ASR models loaded — it can't be automated from this environment. Whoever runs this (the user, or an agent with GUI/screenshot access) must perform it before considering the feature done.

- [ ] **Step 1: Start the app**

Run: `python main.py` (or `docker compose up` if testing the containerized path with X11 forwarding already configured per the README).

- [ ] **Step 2: Trigger the benchmark**

With `voice/benchmark_wav/` populated, focus the app window and press **F12**.

- [ ] **Step 3: Confirm the GUI stays responsive during inference**

While the first audio is being processed (before the dialog appears), try resizing or moving the app window. It should respond immediately — if it freezes until the dialog shows up, `asyncio.to_thread` isn't actually offloading the call (re-check Task 3 Step 4).

- [ ] **Step 4: Confirm the dialog gates progress**

Confirm the "O reconhecimento foi correto?" dialog appears after each audio finishes, and that the next audio is not processed until you click "Sim" or "Não".

- [ ] **Step 5: Confirm the recorded feedback matches what you clicked**

After the run finishes, check `voice/data/metrics.csv` (last N rows) — `user_success` should match what you actually clicked per audio, not a hardcoded value.

- [ ] **Step 6: Confirm no regression in the live-mic flow**

Press **F9**, speak a command, and confirm the "Comando executado com sucesso?" dialog still appears and behaves as before (this exercises the renamed `ask_feedback` from Task 2).
