import flet as ft
import asyncio
import time
import logging

from frontend.widgets.containers_generic import Containers
from constant import ASR_MODEL_KEY


class MicMenu():
    def __init__(self, page: ft.Page):
        self.page = page
        self._speech = None
        self.is_listening = False
        self.container = Containers()

    @property
    def speech(self):
        if self._speech is None:
            from voice.speech import SpeechToText
            self._speech = SpeechToText()
        return self._speech


    def handle_mic_click(self, mic_button, e=None):
        self.speech._startup_start_time = time.time()
        if self.is_listening:
            self.is_listening = False
            self.speech.stop_listen()
            return

        self.is_listening = True
        
        self.page.run_task(self.run_speech_recognition)

        self.page.run_task(self.pulse_animation, mic_button)


    async def pulse_animation(self, container_button: ft.Container):
        await asyncio.sleep(0.75)
        while self.is_listening:
            container_button.scale = 1.15
            container_button.shadow.color = ft.Colors.with_opacity(0.6, "#028268") 
            container_button.shadow.spread_radius = 5
            container_button.content.color = "#028268" 
            container_button.update()
            
            await asyncio.sleep(0.5)
            
            if not self.is_listening:
                break
                
            container_button.scale = 1.0
            container_button.shadow.color = ft.Colors.with_opacity(0.15, "blue")
            container_button.shadow.spread_radius = 1
            container_button.content.color = "white"
            container_button.update()
            
            await asyncio.sleep(0.5) 


        container_button.scale = 1.0
        container_button.shadow.color = ft.Colors.with_opacity(0.15, "blue")
        container_button.shadow.spread_radius = 1
        container_button.content.color = "white"
        container_button.update()


    async def run_speech_recognition(self):
        try:
            text = await asyncio.to_thread(self.speech.listen_for_command)

            if text:
                sr = await self.ask_feedback("Comando executado com sucesso?", f'"{text}"')
                self.speech.record_feedback(sr)

        except Exception as e:
            logging.error(f"Erro no reconhecimento: {e}")
        finally:
            self.is_listening = False

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

    async def wait_for_model_load(self):
        speech_instance = self.speech 
        model_key = speech_instance._current_model_key
        
        event = speech_instance._model_events.get(model_key)
        
        if event and not event.is_set():
            await asyncio.to_thread(event.wait)
        
        self.mic_button.disabled = False
        self.mic_button.opacity = 1.0 
        self.status_text.value = "Detect Voice"
        self.status_text.color = "#858585"
        self.page.update()


    def build_ui(self):
        self.page.padding = 0
        self.page.title = "Mic Menu"

        self.mic_button = self.container.generic_container_with_mic_button(on_click=self.handle_mic_click)
        self.status_text = ft.Text(f"Waiting for {ASR_MODEL_KEY} to load...", size=18, color="#555555", italic=True)


        self.mic_button.disabled = True
        self.mic_button.opacity = 0.3

        mic_card = ft.Container(
            content=ft.Column(
                controls=[
                    self.mic_button,
                    self.status_text
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=20
            ),
            bgcolor="#15171E", 
            width=450,
            height=280,
            border_radius=20,
            border=ft.border.all(1, "#028268") 
        )

        self.page.run_task(self.wait_for_model_load)

        return mic_card
    
