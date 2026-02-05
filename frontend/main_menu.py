import flet as ft
import os
import asyncio
import logging

from frontend.widgets.containers_generic import Containers
from frontend.editor_menu import EditorMenu
from frontend.utils.animation import AnimationUtils
from frontend.utils.file_handler import DirectoryUtils

class MainEditorMenu():
    def __init__(self):
        self.page = ""
        self.tf1 = ""
        self.tf2 = ""
        self.home_menu = ""
        self.editor_path = ""
        self.editor_menu = EditorMenu()
        self.animation = AnimationUtils()
        self.explorer = DirectoryUtils()


    def route_change(self, e=None):
        self.page.views.clear()
        self.page.views.append(
            ft.View(
                route="/",
                padding=0, 
                spacing=0,
                controls=[
                    self.home_menu
                ],
            )
        )
        
        if self.page.route == "/editor":
            layout_editor = self.editor_menu.page(self.page, self.editor_path)
            self.page.views.append(
                ft.View(
                    route="/editor",
                    padding=0,
                    spacing=0,
                    controls=[
                        layout_editor
                    ],
                )
            )
        
        self.page.update()

    async def view_pop(self, e):
        if e.view is not None:
            print("View pop:", e.view)
            self.page.views.remove(e.view)
            top_view = self.page.views[-1]
            await self.page.push_route(top_view.route)

   
    def create_and_open_new_vault(self, page: ft.Page, e: ft.Event[ft.Button]):
        new_dir = self.tf1.content.controls[-1].value
        
        original_path = self.tf2.content.controls[0].controls[-1].value

        path = os.path.join(original_path, new_dir)

        os.makedirs(path, exist_ok=True)

        logging.info(f"New Vault path: {path}")

        self.editor_path = path

        asyncio.create_task(page.push_route("/editor"))


    async def open_editor(self, e: ft.Event[ft.Button]):
        path_editor = await self.explorer.open_explorer()
        
        self.editor_path = path_editor
        
        if not isinstance(path_editor, str):
            pass
        else:
            asyncio.create_task(self.page.push_route("/editor"))


    async def select_editor_path(self, e: ft.Event[ft.Button]):
        path_editor = await self.explorer.open_explorer()

        self.tf2.content.controls[0].controls.append(ft.Text(path_editor, size=12, color="#0C5F49"))
        self.tf2.update()


    def main(self, page: ft.Page):  
        self.page = page 
        page.padding = 0
        page.title = "Voice Writter"
        page.theme_mode = ft.ThemeMode.DARK


        directory_container = ft.Container(
            bgcolor="#202020",
            padding=10,
            border=ft.Border.only(right=ft.border.BorderSide(1, "#0C5F49"), top=ft.border.BorderSide(1, "#0C5F49")),
            content=ft.Column(
                spacing=5,
                controls=[
                        Containers().generic_text_container_with_right_context_menu("Folder_name_1", "Folder_path_1"),
                        Containers().generic_text_container_with_right_context_menu("Folder_name_2", "Folder_path_2"),
                        Containers().generic_text_container_with_right_context_menu("Folder_name_3", "Folder_path_3"),
                        Containers().generic_text_container_with_right_context_menu("Folder_name_4", "Folder_path_4"),
                        ]
            ),
            expand=True
        )


        options_container_1 = ft.Column(
            spacing=10,
            controls=[
                Containers().generic_text_container_with_right_button("Create new vault", "Create a new vault under a folder.", "Create", lambda e : self.animation.fade(animation_switcher, options_container_1, options_container_2)),
                Containers().generic_text_container_with_right_button("Open a Folder", "Open Folder with files.", "Open", self.open_editor, True)
                ]
            )       


        options_container_2 = ft.Column(
            spacing=10,
            controls=[
                ft.Column(spacing=2, horizontal_alignment=ft.CrossAxisAlignment.START, controls=[ft.IconButton(icon=ft.Icons.ARROW_BACK, icon_color="white", on_click=lambda e: self.animation.fade(animation_switcher, options_container_1, options_container_2)), ft.Text("Back", size=16, color="grey")]),
                tf1 := Containers().generic_text_container_with_right_text_field("Vault name", "Pick a name to gain Aura.", "Aura name"),
                tf2 := Containers().generic_text_container_with_right_button("Location", "Pick a place to create the Aura + Ego", "Browse", self.select_editor_path, False),
                ft.Button(content="Create", color="#028268", height=40,style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)), on_click=lambda e: self.create_and_open_new_vault(page, e))
                ]
            )

        self.tf1 = tf1
        self.tf2 = tf2


        animation_switcher = ft.AnimatedSwitcher(
            content=options_container_1,
            transition=ft.AnimatedSwitcherTransition.FADE,
            duration=500,
            reverse_duration=100,
            switch_in_curve=ft.AnimationCurve.BOUNCE_OUT,
            switch_out_curve=ft.AnimationCurve.BOUNCE_IN,
        )  


        main_container = ft.Container(
            bgcolor="#11111",
            padding=20,
            border=ft.Border.only(top=ft.border.BorderSide(1, "#0C5F49")),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=15,
                controls=[ft.Image(src="frontend/images/Aura.webp", width=100, height=100),
                        ft.Text(value="VoiceWritter", size=30, weight="bold"),
                        animation_switcher,
                        ]
            ),
            expand=True
        )


        self.home_menu = ft.Row(
            controls=[
                directory_container,
                main_container
            ],
            expand=True,
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH
        )


        page.on_route_change = self.route_change
        page.on_view_pop = self.view_pop


        self.route_change()


if __name__ == "__main__":
    logging.basicConfig(filename="frontend.log", format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO, encoding="utf-8")
    main = MainEditorMenu()
    ft.run(main.main)

