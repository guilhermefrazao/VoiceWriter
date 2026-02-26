import flet as ft
import asyncio

from frontend.widgets.containers_generic import Containers  
from frontend.utils.color import hover_color_change
from speech import Speech_to_text
from interact_app import add_shortcut

class SpeechMenu():
    def __init__(self, page: ft.Page):
        self.page = page
        self.containers = Containers()
        self.speech = Speech_to_text()
        pass

    def build_ui(self):
        self.page.padding = 0
        self.page.title = "Speech Menu"

        header = ft.Row(
            controls=[
                ft.Image(src="frontend/images/Aura.webp", width=200, height=200)
            ],
            alignment=ft.MainAxisAlignment.START
        )

        mic_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.Icons.MIC, size=45, color="white"),
                        width=100,
                        height=100,
                        border_radius=50,
                        bgcolor="#1A1D24",
                        border=ft.border.all(2, "#028268"),
                        alignment=ft.Alignment.CENTER,
                        shadow=ft.BoxShadow(
                            blur_radius=30,
                            color=ft.Colors.with_opacity(0.15, "blue"),
                            spread_radius=1,
                        ),
                        on_hover=lambda e: hover_color_change(e),
                        on_click=lambda e: self.speech.main()
                        
                    ),
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

        execute_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.OutlinedButton(
                        content=ft.Text("Add New Shortcut", color="#D1D1D1", size=16),
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=10),
                            side={"": ft.BorderSide(1, "#028268")},
                        ),
                        width=250,
                        height=50,
                        on_click=lambda e: add_shortcut(),
                    ),
                    ft.OutlinedButton(
                        content=ft.Text("Open Shortcut", color="#D1D1D1", size=16),
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

