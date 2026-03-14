import flet as ft
import asyncio
import keyboard
import logging

from frontend.widgets.containers_generic import Containers
from voice.speech import SpeechToText

class MicMenu():
    def __init__(self, page: ft.Page):
        self.page = page
        self.speech = SpeechToText()
        self.containers = Containers()


    def handle_mic_click(self, mic_button, e=None):
        if getattr(self, "is_listening", False):
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
            await asyncio.to_thread(self.speech.main_commands)
            
        except Exception as e:
            print(f"Erro no reconhecimento: {e}")
        finally:
            self.is_listening = False


    def build_ui(self):
        self.page.padding = 0
        self.page.title = "Mic Menu"

        mic_button = self.containers.generic_container_with_mic_button(on_click=self.handle_mic_click)

        mic_card = ft.Container(
            content=ft.Column(
                controls=[
                    mic_button,
                    ft.Text("Detect Voice", size=18, color="#858585")
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

        return mic_card
    
