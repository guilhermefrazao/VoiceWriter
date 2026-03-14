import flet as ft
import argparse
import logging
import os
import sys

from frontend.main_menu import MainEditorMenu
from frontend.editor_menu import EditorMenu
from frontend.utils.recent_manager import RecentManager
from frontend.speech_menu import SpeechMenu
from frontend.widgets.mic import MicMenu

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", 
        level=logging.INFO, 
        encoding="utf-8", 
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
        logging.FileHandler("frontend.log", encoding='utf-8'), 
        logging.StreamHandler(sys.stdout)                    
        ])

class MainPage():
    def __init__(self, page: ft.Page):
        self.page = page
        self.mic_menu = MicMenu(page)
        self.menu_instance = None


    async def main(self):
        self.page.title = "Voice Writter"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.padding = 0
        

        parser = argparse.ArgumentParser(description='Voice Writter App')
        parser.add_argument('--editor', type=str, nargs="?", const="last_path", help='Abrir o editor no último caminho utilizado')
        parser.add_argument('--main_menu', type=str, nargs="?", const="Exists", help="Abrir o menu_inicial")
        args, unknown = parser.parse_known_args()

        mic_menu_container = self.mic_menu.build_ui()

        mic_window = ft.AlertDialog(
            content=mic_menu_container,
            content_padding=0,
            bgcolor=ft.Colors.TRANSPARENT,
            open=False
        )

        async def route_change():
            self.page.views.clear()

            if self.page.route == "/":
                self.menu_instance = SpeechMenu(self.page)

                speech_view = ft.View(
                    route="/",
                    padding=0,
                    spacing=0,
                    controls=[]
                )

                self.page.views.append(speech_view)

                speech_view.controls.append(self.menu_instance.build_ui())

            if self.page.route == "/main_menu":
                self.menu_instance = MainEditorMenu(self.page) 
                
                home_view = ft.View(
                    route="/main_menu",
                    padding=0, 
                    spacing=0,
                    controls=[]
                )
                
                self.page.views.append(home_view)
                
                home_view.controls.append(self.menu_instance.build_ui())

            if self.page.route == "/editor":
                current_path = self.page.current_project_path
                
                if current_path and os.path.exists(current_path):
                    self.menu_instance = EditorMenu(self.page)

                    editor_layout = ft.View(
                        route="/editor",
                        padding=0,
                        spacing=0,
                        controls=[]
                    )

                    self.page.views.append(editor_layout)

                    editor_layout.controls.append(self.menu_instance.build_ui(current_path))
                    
                else:
                    logging.info("Path inválido ou não fornecido, voltando para Home.")
                    await self.page.push_route("/")

            self.page.update()

        async def view_pop(view):
            self.page.views.pop()
            top_view = self.page.views[-1]
            await self.page.push_route(top_view.route)


        def manage_shortcuts(e: ft.KeyboardEvent):
            if e.key == "F9":
                if not mic_window.open:
                    self.page.show_dialog(mic_window)
                    self.mic_menu.handle_mic_click(mic_button=mic_window.content.content.controls[0])
                else:
                    self.page.pop_dialog()

                self.page.update()

            if e.key == "F8":
                if mic_window.open:
                    self.mic_menu.handle_mic_click(mic_button=mic_window.content.content.controls[0])
                
                elif type(self.menu_instance) == SpeechMenu:
                    self.mic_menu.handle_mic_click(self.menu_instance.mic_card.content.controls[0])
                
                elif type(self.menu_instance) == EditorMenu and self.menu_instance.can_listen == True:
                    self.menu_instance.handle_mic_click(self.menu_instance.mic_button)


        self.page.on_route_change = route_change
        self.page.on_view_pop = view_pop

        self.page.on_keyboard_event = manage_shortcuts

        if args.editor:
            manager = RecentManager().get_recents()[0]
            logging.info(f"Manager: {manager}")
            self.page.current_project_path = manager
            await self.page.push_route("/editor")
        
        elif args.main_menu:
            await self.page.push_route("/main_menu")
        
        else:
            await route_change()

async def flet_target(page:ft.Page):
    app = MainPage(page)

    await app.main()


if __name__ == "__main__":
    ft.app(target=flet_target)