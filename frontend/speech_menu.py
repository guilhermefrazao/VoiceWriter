import flet as ft
import asyncio
import time

from frontend.widgets.containers_generic import Containers  
from voice.speech import SpeechToText
from frontend.widgets.mic import Mic_menu

class SpeechMenu():
    def __init__(self, page: ft.Page):
        self.page = page
        self.containers = Containers()
        self.speech = SpeechToText()
        self.mic_menu = Mic_menu(page)

    def build_ui(self):
        self.page.padding = 0
        self.page.title = "Speech Menu"

        header = ft.Row(
            controls=[
                ft.Image(src="frontend/images/Aura.webp", width=200, height=200)
            ],
            alignment=ft.MainAxisAlignment.START
        )

        mic_card = self.mic_menu.build_ui()

        execute_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.OutlinedButton(
                        content=ft.Text("Open Editor", color="#D1D1D1", size=16),
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=10),
                            side={"": ft.BorderSide(1, "#028268")},
                        ),
                        width=250,
                        height=50,
                        on_click=lambda e: asyncio.create_task(self.page.push_route("/main_menu"))
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER
            ),
            bgcolor="#15171E",
            width=450,
            height=180,
            border_radius=20,
            border=ft.border.all(1, "#028268")
        )

        speech_layout = ft.Row(
                    expand=True,
                    spacing=200,
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        header,
                        ft.Column(
                            controls=[mic_card, execute_card],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=20
                        )
                    ]
                )


        return speech_layout

