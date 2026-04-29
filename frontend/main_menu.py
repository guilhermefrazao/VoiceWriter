import flet as ft
import os
import asyncio
import logging

from frontend.widgets.containers_generic import Containers
from frontend.utils.animation import AnimationUtils
from frontend.utils.file_handler import DirectoryUtils
from frontend.utils.recent_manager import RecentManager

class MainEditorMenu():
    def __init__(self, page: ft.Page):
        self.page = page
        self.tf1 = ""
        self.tf2 = ""
        self.home_menu = ""
        self.folder_path = ""
        self.directory_container = ""
        self.path_editor = None
        self.animation = AnimationUtils()
        self.explorer = DirectoryUtils()
        self.recent_folder = RecentManager()

   
    def create_and_open_new_vault(self, e: ft.Event[ft.Button]):
        new_dir = self.tf1.content.controls[-1].value

        if self.path_editor and new_dir:
            original_path = self.path_editor

            path = os.path.join(original_path, new_dir)

            os.makedirs(path, exist_ok=True)

            logging.info(f"New Vault path: {path}")

            self.folder_path = path

            self.route_to_editor(path, self.recent_folder, self.page)

        else:
            logging.info("Not all information was put")        


    async def open_editor(self, e: ft.Event[ft.Button]):
        path_editor = await self.explorer.open_explorer()
        
        self.folder_path = path_editor
        
        if not isinstance(path_editor, str):
            pass
        else:
            self.route_to_editor(path_editor, self.recent_folder, self.page)
            
    async def open_speech_menu(self, e: ft.Event[ft.Button]):
        asyncio.create_task(self.page.push_route("/"))


    async def select_editor_path(self, e: ft.Event[ft.Button]):
        self.path_editor = await self.explorer.open_explorer()

        self.tf2.content.controls[0].controls.append(ft.Text(self.path_editor, size=12, color="#055b5f"))
        self.tf2.update()


    def route_to_editor(self, folder_path : str, recent_folder: RecentManager, page: ft.Page) -> None:
        recent_folder.add_path(folder_path)
        page.current_project_path = folder_path
        asyncio.create_task(page.push_route("/editor"))


    def build_directory_container(self):
        paths = self.recent_folder.get_recents()
        directory_container = ft.Container(
                bgcolor="#181818",
                padding=10,
                border=ft.Border.only(right=ft.border.BorderSide(1, "#055b5f"), top=ft.border.BorderSide(1, "#055b5f")),
                content=ft.Column(
                    spacing=5,
                    controls=[
                            
                            ]
                ),
                expand=True
            )

        if not paths:
            directory_container.content.controls.append(ft.Text("Nenhuma pasta recente.", size=24, color="grey", text_align=ft.TextAlign.CENTER))

        
        else:
            for path in paths:
                folder_name = os.path.basename(path)
                directory_container.content.controls.append(Containers().generic_text_container_with_right_context_menu(folder_name, path, color_2="#055b5f", on_click=lambda e, p=path: self.route_to_editor(p, self.recent_folder, self.page)))
                
        return directory_container


    def build_ui(self):   
        self.page.padding = 0
        self.page.title = "Voice Writter"
        self.page.theme_mode = ft.ThemeMode.DARK


        options_container_1 = ft.Column(
            spacing=10,
            controls=[
                Containers().generic_text_container_with_right_button("Create new vault", "Create a new vault under a folder.", "Create", "#028268", "#00302d", lambda e : self.animation.fade(animation_switcher, options_container_1, options_container_2)),
                Containers().generic_text_container_with_right_button("Open a Folder", "Open Folder with files.", "Open", "#028268", "#00302d", self.open_editor, True),
                Containers().generic_text_container_with_right_button("Return to Main_Menu", "Returns to main_menu", "Back", "#028268", "#00302d", self.open_speech_menu)
                ]
            )       


        options_container_2 = ft.Column(
            spacing=10,
            controls=[
                ft.Column(spacing=2, horizontal_alignment=ft.CrossAxisAlignment.START, controls=[ft.IconButton(icon=ft.Icons.ARROW_BACK, icon_color="white", on_click=lambda e: self.animation.fade(animation_switcher, options_container_1, options_container_2)), ft.Text("Back", size=16, color="grey")]),
                tf1 := Containers().generic_text_container_with_right_text_field("Vault name", "Pick a name to gain Aura.", "Aura name", container_color="#00302d"),
                tf2 := Containers().generic_text_container_with_right_button("Location", "Pick a place to create the Aura + Ego", "Browse", "#028268", "#00302d",  self.select_editor_path, False),
                ft.Button(content="Create", color="#028268", height=40,style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)), on_click=lambda e: self.create_and_open_new_vault(e))
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
            bgcolor="#1111",
            padding=20,
            border=ft.Border.only(top=ft.border.BorderSide(1, "#055b5f")),
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

        self.directory_container = self.build_directory_container()

        self.home_menu = ft.Row(
            controls=[
                self.directory_container,
                main_container
            ],
            expand=True,
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH
        )

        return self.home_menu



