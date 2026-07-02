# Wakeword Runtime Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make VoiceWriter listen for the "transcrição" wakeword continuously in the background (window minimized to system tray) and, on detection, trigger the exact same command-listening flow that F9 already triggers.

**Architecture:** A `WakewordListener` runs openWakeWord inference in a daemon thread reading from its own PyAudio stream. On detection it calls `page.run_task(...)`, which is thread-safe in Flet (`asyncio.run_coroutine_threadsafe` under the hood), to invoke a new shared `MainPage.trigger_mic_listen()` coroutine — the same coroutine the F9 hotkey now calls. The listener pauses itself while `listen_for_command()` is capturing a command, releasing the microphone device. A `pystray`-based system tray icon keeps the process alive when the window is closed (X hides instead of quitting), so the listener keeps running in the background. Both the tray and the listener only start on native Windows execution; Docker/headless (`--type-at-cursor`) are unaffected.

**Tech Stack:** Python 3.12, Flet 0.80.2, openwakeword 0.6.0 (onnx inference), pystray 0.19.5, PyAudio (already a dependency), pytest (new dev dependency — no test framework exists yet in this repo).

## Global Constraints

- Pin new dependencies exactly, matching this repo's existing style: `openwakeword==0.6.0`, `pystray==0.19.5` in both `requirements.txt` and `pyproject.toml`; `pytest==9.1.1` as a `pyproject.toml` dev-dependency only (not needed in the Docker runtime image).
- The wakeword model file (`voice/wakeword/models/transcricao.onnx`) is produced by the separate training plan (`docs/superpowers/plans/2026-07-02-wakeword-training-pipeline.md`) and is NOT committed to git — add it to `.gitignore`. Code in this plan must work correctly when the file is absent (listener simply doesn't start, app behaves exactly as today with F9 only).
- Tray + wakeword listener must only start on native Windows (`platform.system() == "Windows"`), and any failure to start either (missing model, missing tray backend, import errors) must be caught and logged, never crash the app — this preserves the existing Docker/Linux code path untouched.
- Follow the project's existing threading style: plain functions/classes run via `threading.Thread(target=..., daemon=True).start()` (see `main.py:188`, `voice/speech.py:303`), not `Thread` subclasses.
- No new configuration system — hardcoded constants in `main.py`, matching the existing `ASR_MODEL_KEY` pattern (`main.py:17`).

---

### Task 1: Test infrastructure (pytest)

This repo has zero test files today. Set up pytest so later tasks can write real, runnable tests.

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/test_smoke.py`

**Interfaces:**
- Produces: a working `pytest` command runnable from the repo root that discovers `tests/**/test_*.py` and can import top-level packages (`voice`, `frontend`) without `PYTHONPATH` gymnastics.

- [ ] **Step 1: Add pytest as a dev dependency and configure test discovery**

Edit `pyproject.toml`, changing the `[tool.uv]` section and adding a new `[tool.pytest.ini_options]` section:

```toml
[tool.uv]
package = false
dev-dependencies = [
    "pip",
    "pytest==9.1.1",
]
override-dependencies = [
    "pywin32 ; sys_platform == 'win32'",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 2: Install the new dev dependency**

Run: `uv sync`
Expected: completes without error, `pytest` importable from the project venv.

- [ ] **Step 3: Write a smoke test**

Create `tests/test_smoke.py`:

```python
def test_true() -> None:
    assert True
```

- [ ] **Step 4: Run pytest to verify discovery works**

Run: `uv run pytest -v`
Expected: 1 test collected from `tests/test_smoke.py`, PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock tests/test_smoke.py
git commit -m "chore: add pytest test infrastructure"
```

---

### Task 2: Fix the broken dialog API and extract the F9 flow into a reusable method

`main.py:135,138` and `frontend/widgets/mic.py:87,92,106` call `page.show_dialog(...)` / `page.pop_dialog()`, which **do not exist** on `flet.Page` in the installed `flet==0.80.2` (verified: no such methods anywhere in the installed package, no monkeypatch in this repo). These calls currently raise `AttributeError` at runtime, meaning F9's mic dialog and the "Comando executado com sucesso?" feedback dialog are currently broken. This task fixes both, using the working pattern already present in `frontend/widgets/context_menu.py:15-16,68` (`page.overlay.append(dialog)` + `dialog.open = True/False` + `page.update()`), and extracts the F9 dialog-toggle logic into a `MainPage.trigger_mic_listen()` coroutine so the wakeword listener (Task 5) can call the exact same code path.

Note: `frontend/utils/file_handler.py:40,45,59` has the same broken calls in an unrelated flow (Linux directory picker) — intentionally left untouched here as out of scope for wakeword; flag it to the user as a separate follow-up.

**Files:**
- Modify: `main.py:41-174` (the `MainPage` class)
- Modify: `frontend/widgets/mic.py:81-108` (`MicMenu._ask_command_feedback`)
- Test: `tests/frontend/test_mic_menu.py`

**Interfaces:**
- Produces: `MainPage.trigger_mic_listen(self) -> None` (async method) — toggles `self.mic_window` open/closed via `page.overlay` and, when opening, calls `self.mic_menu.handle_mic_click(...)`. This is the method Task 5's wakeword callback will invoke via `page.run_task(main_page.trigger_mic_listen)`.
- Produces: `MainPage.mic_window: ft.AlertDialog` (hoisted from a local variable to an instance attribute).
- Consumes (from existing code, unchanged): `MicMenu.handle_mic_click(mic_button, e=None)` (`frontend/widgets/mic.py:24`).

- [ ] **Step 1: Add `pytest-asyncio` (needed for this task's async test)**

Edit `pyproject.toml`'s `[tool.uv]` section:

```toml
[tool.uv]
package = false
dev-dependencies = [
    "pip",
    "pytest==9.1.1",
    "pytest-asyncio==1.4.0",
]
override-dependencies = [
    "pywin32 ; sys_platform == 'win32'",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
asyncio_mode = "auto"
```

Run: `uv sync`
Expected: completes without error.

- [ ] **Step 2: Write a failing test for the fixed feedback dialog**

Create `tests/frontend/test_mic_menu.py`:

```python
import asyncio
from unittest.mock import MagicMock

import pytest

from frontend.widgets.mic import MicMenu


async def test_ask_command_feedback_uses_overlay_not_show_dialog():
    page = MagicMock(spec=["overlay", "update"])
    page.overlay = []
    menu = MicMenu(page)

    async def click_sim_after_open():
        await asyncio.sleep(0)  # let _ask_command_feedback add the dialog to overlay first
        dialog = page.overlay[-1]
        sim_button = dialog.actions[0]
        await sim_button.on_click(None)

    result, _ = await asyncio.gather(
        menu._ask_command_feedback("abrir chrome"),
        click_sim_after_open(),
    )

    assert result is True
    assert page.overlay[-1].open is False
    page.update.assert_called()
```

`page = MagicMock(spec=["overlay", "update"])` restricts the mock to only these two attributes, so the old `page.show_dialog(...)`/`page.pop_dialog()` calls raise `AttributeError` instead of silently auto-creating mock methods — this is what makes the test actually exercise (and fail against) the current broken code.

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/frontend/test_mic_menu.py -v`
Expected: FAIL with `AttributeError: Mock object has no attribute 'show_dialog'`.

- [ ] **Step 4: Fix `_ask_command_feedback` in `frontend/widgets/mic.py`**

Replace lines 81-108:

```python
    async def _ask_command_feedback(self, command_text: str) -> bool:
        answered = asyncio.Event()
        result: dict[str, bool] = {}

        async def on_sim(_):
            result["ok"] = True
            dialog.open = False
            self.page.update()
            answered.set()

        async def on_nao(_):
            result["ok"] = False
            dialog.open = False
            self.page.update()
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

        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
        await answered.wait()
        return result.get("ok", False)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/frontend/test_mic_menu.py -v`
Expected: PASS.

- [ ] **Step 6: Hoist `mic_window` to `self.mic_window` and add `trigger_mic_listen` in `main.py`**

In `main.py`, inside `MainPage.main()`, replace:

```python
        mic_window = ft.AlertDialog(
            content=mic_menu_container,
            content_padding=0,
            bgcolor=ft.Colors.TRANSPARENT,
            open=False
        )
```

with:

```python
        self.mic_window = ft.AlertDialog(
            content=mic_menu_container,
            content_padding=0,
            bgcolor=ft.Colors.TRANSPARENT,
            open=False
        )
```

Add this new method to the `MainPage` class (place it right after `__init__`):

```python
    async def trigger_mic_listen(self) -> None:
        if not self.mic_window.open:
            if self.mic_window not in self.page.overlay:
                self.page.overlay.append(self.mic_window)
            self.mic_window.open = True
            self.mic_menu.handle_mic_click(mic_button=self.mic_window.content.content.controls[0])
        else:
            self.mic_window.open = False

        self.page.update()
```

Replace the `F9` branch inside `manage_shortcuts`:

```python
            if e.key == "F9":
                if not mic_window.open:
                    self.page.show_dialog(mic_window)
                    self.mic_menu.handle_mic_click(mic_button=mic_window.content.content.controls[0])
                else:
                    self.page.pop_dialog()

                self.page.update()
```

with:

```python
            if e.key == "F9":
                self.page.run_task(self.trigger_mic_listen)
```

Replace the two remaining references to the old local `mic_window` variable inside the `F8` branch:

```python
            if e.key == "F8":
                from frontend.speech_menu import SpeechMenu
                from frontend.editor_menu import EditorMenu
                if mic_window.open:
                    self.mic_menu.handle_mic_click(mic_button=mic_window.content.content.controls[0])
```

with:

```python
            if e.key == "F8":
                from frontend.speech_menu import SpeechMenu
                from frontend.editor_menu import EditorMenu
                if self.mic_window.open:
                    self.mic_menu.handle_mic_click(mic_button=self.mic_window.content.content.controls[0])
```

- [ ] **Step 7: Manual sanity check**

Run: `uv run python main.py`
Press F9 with the window focused. Expected: the mic dialog opens (no `AttributeError` in `frontend.log`/console), and pressing F9 again closes it.

- [ ] **Step 8: Commit**

```bash
git add main.py frontend/widgets/mic.py tests/frontend/test_mic_menu.py pyproject.toml uv.lock
git commit -m "fix: replace nonexistent page.show_dialog/pop_dialog with page.overlay pattern; extract F9 flow into trigger_mic_listen"
```

---

### Task 3: `WakewordListener` core detection logic (TDD, no hardware/model dependency)

**Files:**
- Create: `voice/wakeword/__init__.py` (empty)
- Create: `voice/wakeword/detector.py`
- Test: `tests/wakeword/test_detector.py`

**Interfaces:**
- Produces: `WakewordListener(model, on_detected, model_name, threshold=0.5, debounce_seconds=2.0, frame_generator=None)`.
  - `model`: any object with `.predict(frame: np.ndarray) -> dict[str, float]` (duck-typed; production passes an `openwakeword.model.Model` instance from Task 4's `load_model`).
  - `on_detected: Callable[[], None]` — called (synchronously, from the listener's own thread) when a detection above threshold occurs, after debounce filtering.
  - `frame_generator: Callable[[], Iterator[np.ndarray]] | None` — injectable for tests; defaults to `self._microphone_frames` in production.
- Produces methods: `.start()`, `.stop()`, `.pause()`, `.resume()`, `.run()` (the loop body, callable directly and synchronously in tests without spawning a thread).

- [ ] **Step 1: Create the empty package init**

Create `voice/wakeword/__init__.py` (empty file).

- [ ] **Step 2: Write failing tests for detection, threshold, and debounce**

Create `tests/wakeword/test_detector.py`:

```python
import numpy as np

from voice.wakeword.detector import WakewordListener


class _FakeModel:
    def __init__(self, scores: list[float]):
        self._scores = iter(scores)
        self.calls: list[np.ndarray] = []

    def predict(self, frame: np.ndarray) -> dict[str, float]:
        self.calls.append(frame)
        return {"transcricao": next(self._scores)}


def _frame() -> np.ndarray:
    return np.zeros(1280, dtype=np.int16)


def test_process_frame_triggers_callback_above_threshold():
    model = _FakeModel([0.9])
    detected = []
    listener = WakewordListener(
        model=model, on_detected=lambda: detected.append(True),
        model_name="transcricao", threshold=0.5,
    )

    listener._process_frame(_frame())

    assert detected == [True]


def test_process_frame_does_not_trigger_below_threshold():
    model = _FakeModel([0.1])
    detected = []
    listener = WakewordListener(
        model=model, on_detected=lambda: detected.append(True),
        model_name="transcricao", threshold=0.5,
    )

    listener._process_frame(_frame())

    assert detected == []


def test_process_frame_debounces_repeated_detections():
    model = _FakeModel([0.9, 0.9])
    detected = []
    listener = WakewordListener(
        model=model, on_detected=lambda: detected.append(True),
        model_name="transcricao", threshold=0.5, debounce_seconds=10.0,
    )

    listener._process_frame(_frame())
    listener._process_frame(_frame())

    assert detected == [True]


def test_process_frame_allows_new_detection_after_debounce_window():
    model = _FakeModel([0.9, 0.9])
    detected = []
    listener = WakewordListener(
        model=model, on_detected=lambda: detected.append(True),
        model_name="transcricao", threshold=0.5, debounce_seconds=0.0,
    )

    listener._process_frame(_frame())
    listener._process_frame(_frame())

    assert detected == [True, True]


def test_run_processes_frames_from_injected_generator():
    model = _FakeModel([0.9])
    detected = []

    def frame_generator():
        yield _frame()

    listener = WakewordListener(
        model=model, on_detected=lambda: detected.append(True),
        model_name="transcricao", threshold=0.5, frame_generator=frame_generator,
    )

    listener.run()

    assert detected == [True]


def test_run_skips_processing_while_paused():
    model = _FakeModel([0.9, 0.9])
    detected = []

    def frame_generator():
        yield _frame()
        yield _frame()

    listener = WakewordListener(
        model=model, on_detected=lambda: detected.append(True),
        model_name="transcricao", threshold=0.5, frame_generator=frame_generator,
    )
    listener.pause()

    listener.run()

    assert model.calls == []
    assert detected == []


def test_model_exception_is_caught_and_does_not_propagate():
    class _RaisingModel:
        def predict(self, frame):
            raise RuntimeError("onnxruntime boom")

    detected = []
    listener = WakewordListener(
        model=_RaisingModel(), on_detected=lambda: detected.append(True),
        model_name="transcricao", threshold=0.5,
    )

    listener._process_frame(_frame())  # must not raise

    assert detected == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/wakeword/test_detector.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'voice.wakeword.detector'`.

- [ ] **Step 4: Implement `voice/wakeword/detector.py`**

```python
import logging
import os
import threading
import time
from typing import Callable, Iterator

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHUNK_SAMPLES = 1280  # 80ms @ 16kHz — the frame size openWakeWord expects


def load_model(model_path: str, inference_framework: str = "onnx"):
    """Carrega o modelo openWakeWord a partir de um arquivo .onnx.
    Retorna None se o arquivo não existir ou o carregamento falhar — nesses
    casos o app deve continuar funcionando normalmente, só sem o listener.
    """
    if not os.path.exists(model_path):
        return None
    try:
        from openwakeword.model import Model
        return Model(wakeword_models=[model_path], inference_framework=inference_framework)
    except Exception:
        logger.exception("Falha ao carregar o modelo de wakeword em '%s'", model_path)
        return None


class WakewordListener:
    def __init__(
        self,
        model,
        on_detected: Callable[[], None],
        model_name: str,
        threshold: float = 0.5,
        debounce_seconds: float = 2.0,
        frame_generator: Callable[[], Iterator[np.ndarray]] | None = None,
    ):
        self._model = model
        self._on_detected = on_detected
        self._model_name = model_name
        self._threshold = threshold
        self._debounce_seconds = debounce_seconds
        self._frame_generator = frame_generator or self._microphone_frames

        self._stop_event = threading.Event()
        self._paused = threading.Event()
        self._last_detection_time = 0.0
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def pause(self) -> None:
        self._paused.set()

    def resume(self) -> None:
        self._paused.clear()

    def run(self) -> None:
        """Loop de detecção. Roda em thread própria via start(), mas pode ser
        chamado diretamente e de forma síncrona (usado nos testes)."""
        for frame in self._frame_generator():
            if self._stop_event.is_set():
                break
            if not self._paused.is_set():
                self._process_frame(frame)

    def _process_frame(self, frame: np.ndarray) -> None:
        try:
            predictions = self._model.predict(frame)
        except Exception:
            logger.exception("Falha ao processar frame de áudio no wakeword listener")
            return

        score = predictions.get(self._model_name, 0.0)
        now = time.monotonic()
        if score >= self._threshold and (now - self._last_detection_time) >= self._debounce_seconds:
            self._last_detection_time = now
            logger.info("Wakeword detectada (score=%.2f)", score)
            self._on_detected()

    def _microphone_frames(self) -> Iterator[np.ndarray]:
        import pyaudio

        pa = pyaudio.PyAudio()
        stream = None
        try:
            while not self._stop_event.is_set():
                if self._paused.is_set():
                    if stream is not None:
                        stream.stop_stream()
                        stream.close()
                        stream = None
                    time.sleep(0.1)
                    continue

                if stream is None:
                    stream = pa.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=DEFAULT_SAMPLE_RATE,
                        input=True,
                        frames_per_buffer=DEFAULT_CHUNK_SAMPLES,
                    )

                data = stream.read(DEFAULT_CHUNK_SAMPLES, exception_on_overflow=False)
                yield np.frombuffer(data, dtype=np.int16)
        finally:
            if stream is not None:
                stream.stop_stream()
                stream.close()
            pa.terminate()
```

Note: `_microphone_frames` actively closes the PyAudio stream while paused (not just skipping inference) so the audio device is fully released for `speech_recognition` to open exclusively during `listen_for_command()` — this is what Task 5 relies on to avoid device-contention errors on Windows.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/wakeword/test_detector.py -v`
Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add voice/wakeword/__init__.py voice/wakeword/detector.py tests/wakeword/test_detector.py
git commit -m "feat: add WakewordListener core detection loop"
```

---

### Task 4: `load_model` behavior when the model file is missing or invalid

**Files:**
- Modify: `voice/wakeword/detector.py` (already has `load_model`, from Task 3)
- Test: `tests/wakeword/test_load_model.py`

**Interfaces:**
- Consumes: `voice.wakeword.detector.load_model(model_path: str, inference_framework: str = "onnx")` (defined in Task 3).

- [ ] **Step 1: Write failing tests**

Create `tests/wakeword/test_load_model.py`:

```python
from voice.wakeword.detector import load_model


def test_load_model_returns_none_when_file_missing(tmp_path):
    missing_path = str(tmp_path / "does_not_exist.onnx")

    result = load_model(missing_path)

    assert result is None


def test_load_model_returns_none_and_logs_when_load_raises(tmp_path, monkeypatch, caplog):
    fake_model_path = tmp_path / "broken.onnx"
    fake_model_path.write_bytes(b"not a real onnx file")

    result = load_model(str(fake_model_path))

    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail or pass for the wrong reason**

Run: `uv run pytest tests/wakeword/test_load_model.py -v`
Expected: the missing-file test should already PASS (Task 3's `load_model` already checks `os.path.exists`). The broken-file test exercises the `except Exception` branch — run it to confirm it PASSES too (openWakeWord's `Model(...)` constructor should raise on a malformed onnx file, which is caught). If both pass, this task is a verification-only task; if either fails, proceed to Step 3.

- [ ] **Step 3: Fix `load_model` if needed**

If the broken-file test failed because `Model(...)` doesn't raise synchronously in `__init__` for malformed content, wrap the whole function body defensively (this should already be the case from Task 3's implementation — no code change expected here in the common case).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/wakeword/test_load_model.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/wakeword/test_load_model.py
git commit -m "test: cover WakewordListener.load_model failure paths"
```

---

### Task 5: Wire the listener into `main.py` and pause/resume it around command listening

**Files:**
- Modify: `main.py`
- Modify: `frontend/widgets/mic.py`
- Test: `tests/frontend/test_mic_menu.py` (extend)

**Interfaces:**
- Consumes: `WakewordListener`, `load_model` (Task 3/4); `MainPage.trigger_mic_listen` (Task 2).
- Produces: `MicMenu.wakeword_listener: WakewordListener | None` attribute (defaults to `None`), read by `run_speech_recognition` to pause/resume.

- [ ] **Step 1: Write a failing test for pause/resume wiring in `MicMenu`**

Extend `tests/frontend/test_mic_menu.py`, adding:

```python
@pytest.mark.asyncio
async def test_run_speech_recognition_pauses_and_resumes_wakeword_listener():
    page = MagicMock(spec=["overlay", "update", "run_task"])
    menu = MicMenu(page)
    menu._speech = MagicMock()
    menu._speech.listen_for_command = MagicMock(return_value=None)
    listener = MagicMock()
    menu.wakeword_listener = listener

    await menu.run_speech_recognition()

    listener.pause.assert_called_once()
    listener.resume.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/frontend/test_mic_menu.py -v`
Expected: FAIL — `MicMenu` has no `wakeword_listener` attribute and `run_speech_recognition` never calls `.pause()`/`.resume()`.

- [ ] **Step 3: Add `wakeword_listener` attribute and pause/resume calls in `frontend/widgets/mic.py`**

In `MicMenu.__init__` (`frontend/widgets/mic.py:9-14`), add the attribute:

```python
class MicMenu():
    def __init__(self, page: ft.Page):
        self.page = page
        self._speech = None
        self.is_listening = False
        self.container = Containers()
        self.wakeword_listener = None
```

Replace `run_speech_recognition` (`frontend/widgets/mic.py:68-79`):

```python
    async def run_speech_recognition(self):
        if self.wakeword_listener is not None:
            self.wakeword_listener.pause()
        try:
            text = await asyncio.to_thread(self.speech.listen_for_command)

            if text:
                sr = await self._ask_command_feedback(text)
                self.speech.record_feedback(sr)

        except Exception as e:
            logging.error(f"Erro no reconhecimento: {e}")
        finally:
            self.is_listening = False
            if self.wakeword_listener is not None:
                self.wakeword_listener.resume()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/frontend/test_mic_menu.py -v`
Expected: PASS.

- [ ] **Step 5: Start the listener from `main.py` and hand it to `MicMenu`**

Add near the top of `main.py`, after the `ASR_MODEL_KEY` constants:

```python
WAKEWORD_MODEL_PATH = "voice/wakeword/models/transcricao.onnx"
WAKEWORD_THRESHOLD = 0.5


def _start_wakeword_listener(page: ft.Page, main_page: "MainPage"):
    if platform.system() != "Windows":
        return None

    try:
        from voice.wakeword.detector import WakewordListener, load_model

        model = load_model(WAKEWORD_MODEL_PATH)
        if model is None:
            logging.warning(
                "Wakeword: modelo não encontrado em '%s'. Detecção por voz desativada; use F9.",
                WAKEWORD_MODEL_PATH,
            )
            return None

        def _on_detected():
            page.run_task(main_page.trigger_mic_listen)

        listener = WakewordListener(
            model=model,
            on_detected=_on_detected,
            model_name="transcricao",
            threshold=WAKEWORD_THRESHOLD,
        )
        listener.start()
        return listener
    except Exception:
        logging.exception("Falha ao iniciar o listener de wakeword")
        return None
```

In `MainPage.main()`, after the line `self.page.on_keyboard_event = manage_shortcuts` and before the final `threading.Thread(target=_prewarm_speech, ...)` line, add:

```python
        self.wakeword_listener = _start_wakeword_listener(self.page, self)
        self.mic_menu.wakeword_listener = self.wakeword_listener
```

- [ ] **Step 6: Manual sanity check with a stand-in model**

The real `transcricao.onnx` doesn't exist yet (produced by the training plan). Verify graceful degradation:

Run: `uv run python main.py`
Expected: app starts normally, `frontend.log` contains a line `Wakeword: modelo não encontrado em 'voice/wakeword/models/transcricao.onnx'. Detecção por voz desativada; use F9.`, and F9 still works (from Task 2).

- [ ] **Step 7: Commit**

```bash
git add main.py frontend/widgets/mic.py tests/frontend/test_mic_menu.py
git commit -m "feat: start WakewordListener on native Windows and wire it into the F9 flow"
```

---

### Task 6: System tray (`frontend/utils/tray.py`)

**Files:**
- Create: `frontend/utils/tray.py`
- Test: `tests/frontend/test_tray.py`

**Interfaces:**
- Produces: `SystemTray(icon_path: str, on_open: Callable[[], None], on_quit: Callable[[], None])` with `.start()`, `.stop()`, and `.notify(message: str, title: str | None = None)`.

- [ ] **Step 1: Write failing tests**

Create `tests/frontend/test_tray.py`:

```python
from PIL import Image

from frontend.utils.tray import SystemTray


def _make_test_icon(tmp_path) -> str:
    path = tmp_path / "icon.png"
    Image.new("RGB", (16, 16), "black").save(path)
    return str(path)


def test_handle_open_calls_on_open_callback(tmp_path):
    events = []
    tray = SystemTray(
        _make_test_icon(tmp_path),
        on_open=lambda: events.append("open"),
        on_quit=lambda: events.append("quit"),
    )

    tray._handle_open(tray._icon, None)

    assert events == ["open"]


def test_handle_quit_calls_on_quit_and_stops_icon(tmp_path):
    events = []
    tray = SystemTray(
        _make_test_icon(tmp_path),
        on_open=lambda: events.append("open"),
        on_quit=lambda: events.append("quit"),
    )
    stopped = []
    tray._icon.stop = lambda: stopped.append(True)

    tray._handle_quit(tray._icon, None)

    assert events == ["quit"]
    assert stopped == [True]


def test_notify_delegates_to_icon_notify(tmp_path):
    tray = SystemTray(
        _make_test_icon(tmp_path),
        on_open=lambda: None,
        on_quit=lambda: None,
    )
    calls = []
    tray._icon.notify = lambda message, title=None: calls.append((message, title))

    tray.notify("Ouvindo comando...", "VoiceWriter")

    assert calls == [("Ouvindo comando...", "VoiceWriter")]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/frontend/test_tray.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'frontend.utils.tray'`.

- [ ] **Step 3: Add `pystray` dependency**

Run: `uv add pystray==0.19.5`

Also add the same pin to `requirements.txt` (used by the Docker build):

```
pystray==0.19.5
```

- [ ] **Step 4: Implement `frontend/utils/tray.py`**

```python
import logging
import threading
from typing import Callable

import pystray
from PIL import Image

logger = logging.getLogger(__name__)


class SystemTray:
    def __init__(self, icon_path: str, on_open: Callable[[], None], on_quit: Callable[[], None]):
        self._on_open = on_open
        self._on_quit = on_quit
        self._icon = pystray.Icon(
            "voicewriter",
            Image.open(icon_path),
            "VoiceWriter",
            menu=pystray.Menu(
                pystray.MenuItem("Abrir", self._handle_open, default=True),
                pystray.MenuItem("Sair", self._handle_quit),
            ),
        )
        self._thread: threading.Thread | None = None

    def _handle_open(self, icon: pystray.Icon, item) -> None:
        self._on_open()

    def _handle_quit(self, icon: pystray.Icon, item) -> None:
        self._on_quit()
        icon.stop()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._icon.stop()

    def notify(self, message: str, title: str | None = None) -> None:
        self._icon.notify(message, title)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/frontend/test_tray.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add frontend/utils/tray.py tests/frontend/test_tray.py pyproject.toml uv.lock requirements.txt
git commit -m "feat: add SystemTray wrapper around pystray"
```

---

### Task 7: Wire the tray and minimize-on-close behavior into `main.py`

**Files:**
- Modify: `main.py`

**Interfaces:**
- Consumes: `SystemTray` (Task 6), `MainPage.wakeword_listener` (Task 5).

- [ ] **Step 1: Add window-close interception and tray startup in `MainPage.main()`**

In `main.py`, inside `MainPage.main()`, right after `self.page.window.icon = "frontend/images/icon.png"`, add:

```python
        self.page.window.prevent_close = True

        def _handle_window_event(e: ft.WindowEvent) -> None:
            if e.type == ft.WindowEventType.CLOSE:
                self.page.window.visible = False
                self.page.update()

        self.page.window.on_event = _handle_window_event
```

After the `self.wakeword_listener = _start_wakeword_listener(...)` / `self.mic_menu.wakeword_listener = ...` lines added in Task 5, add:

```python
        self.tray = _start_tray(self.page, self)
```

Add the `_start_tray` helper function near `_start_wakeword_listener`, and a `_restore_window`/`_quit_app` pair as methods on `MainPage`:

```python
def _start_tray(page: ft.Page, main_page: "MainPage"):
    if platform.system() != "Windows":
        return None

    try:
        from frontend.utils.tray import SystemTray

        def _on_open():
            page.run_task(main_page._restore_window)

        def _on_quit():
            if main_page.wakeword_listener is not None:
                main_page.wakeword_listener.stop()
            os._exit(0)

        tray = SystemTray(icon_path="frontend/images/icon.png", on_open=_on_open, on_quit=_on_quit)
        tray.start()
        return tray
    except Exception:
        logging.exception("Falha ao iniciar o ícone da bandeja")
        return None
```

Add `import os` to `main.py`'s existing import block if not already present (it is not — `main.py` currently imports `os` already at line 4, so no change needed there).

Add this method to `MainPage` (near `trigger_mic_listen`):

```python
    async def _restore_window(self) -> None:
        self.page.window.visible = True
        self.page.window.minimized = False
        await self.page.window.to_front()
        self.page.update()
```

- [ ] **Step 2: Show a toast notification when the wakeword fires**

The design spec requires a visible signal that the app "heard" the wakeword, since the window may be hidden in the tray at that moment (`docs/superpowers/specs/2026-07-02-wakeword-design.md`, Component 3 note). `pystray.Icon.notify(message, title=None)` shows a native OS notification and only makes sense once the tray exists, so it's wired here rather than in Task 5.

In `main.py`, update the `_on_detected` closure inside `_start_wakeword_listener` (added in Task 5) to:

```python
        def _on_detected():
            if main_page.tray is not None:
                main_page.tray.notify("Ouvindo comando...", "VoiceWriter")
            page.run_task(main_page.trigger_mic_listen)
```

Add a `tray` default attribute to `MainPage.__init__` so this check is always valid even in the (currently impossible, but defensive) case detection fires before `_start_tray` has run:

```python
    def __init__(self, page: ft.Page):
        self.page = page
        self.mic_menu = MicMenu(page)
        self.menu_instance = None
        self.wakeword_listener = None
        self.tray = None
```

(`self.wakeword_listener = None` and `self.tray = None` replace the plain assignments added in Task 5/this task's Step 1 with pre-declared defaults — keep the later `self.wakeword_listener = _start_wakeword_listener(...)` and `self.tray = _start_tray(...)` lines in `main()` as-is; they simply overwrite these defaults once each subsystem actually starts.)

- [ ] **Step 3: Manual verification**

Run: `uv run python main.py`
1. Confirm the app window opens normally.
2. Click the window's X button. Expected: window disappears, but the process keeps running (check Task Manager / `frontend.log` keeps being written), and a "VoiceWriter" icon appears in the Windows system tray.
3. Right-click the tray icon → "Abrir". Expected: window reappears in front.
4. Right-click the tray icon → "Sair". Expected: process fully exits (no longer in Task Manager).
5. (Requires Task 9's stand-in model) With the window minimized to tray, say the wakeword. Expected: a Windows toast notification "Ouvindo comando..." appears before/alongside the mic dialog logic running.

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat: minimize to system tray on window close instead of exiting"
```

---

### Task 8: `.gitignore` entry for the (untrained) model file

**Files:**
- Modify: `.gitignore`
- Create: `voice/wakeword/models/.gitkeep`

- [ ] **Step 1: Add the ignore rule**

Append to `.gitignore`:

```
voice/wakeword/models/*.onnx
voice/wakeword/models/*.tflite
```

- [ ] **Step 2: Keep the directory tracked in git despite being empty**

Create `voice/wakeword/models/.gitkeep` (empty file).

- [ ] **Step 3: Commit**

```bash
git add .gitignore voice/wakeword/models/.gitkeep
git commit -m "chore: ignore trained wakeword model files, keep models/ dir tracked"
```

---

### Task 9: End-to-end manual smoke test with a stand-in pretrained model

The real `transcricao.onnx` doesn't exist until the training plan runs. This task verifies the full wiring (mic release/reacquire, dialog, tray) works using one of openWakeWord's bundled English demo models as a stand-in, so Components 2-4 are provably correct independent of Component 1 (training).

**Files:**
- None (manual verification only — documents the procedure for the person running this plan).

- [ ] **Step 1: Add `openwakeword` as a runtime dependency**

Run: `uv add openwakeword==0.6.0`

Also add to `requirements.txt`:

```
openwakeword==0.6.0
```

- [ ] **Step 2: Fetch a pretrained demo model as a stand-in**

```bash
uv run python -c "import openwakeword.utils; openwakeword.utils.download_models(['hey_jarvis'])"
```

Expected: downloads `hey_jarvis_v0.1.onnx` (and its melspectrogram/embedding feature models) into openWakeWord's default model cache directory.

Find the cached path (printed by the command above, typically `~/.cache/openwakeword/...` or similar on Windows under the user profile), then copy it into place as the stand-in:

```bash
cp <path-printed-above>/hey_jarvis_v0.1.onnx voice/wakeword/models/transcricao.onnx
```

- [ ] **Step 3: Run the app and verify end-to-end detection**

Run: `uv run python main.py`

1. Minimize to tray (click X).
2. Say "hey jarvis" clearly near the microphone.
3. Expected: the tray-hidden window doesn't need to be visible — the mic dialog should still open (verify via `frontend.log`: look for `Wakeword detectada (score=...)` followed by the same log lines F9 normally produces).
4. While the mic dialog is capturing a command, say "hey jarvis" again. Expected: no second detection fires (listener is paused — no "Wakeword detectada" log line during this window).
5. After the command flow finishes, say "hey jarvis" again. Expected: detects again (listener resumed).

- [ ] **Step 4: Remove the stand-in model**

```bash
rm voice/wakeword/models/transcricao.onnx
```

(Leave `openwakeword`/`pystray` as permanent dependencies — only the stand-in model file is temporary.)

- [ ] **Step 5: Commit the dependency additions**

```bash
git add pyproject.toml uv.lock requirements.txt
git commit -m "chore: add openwakeword runtime dependency"
```
