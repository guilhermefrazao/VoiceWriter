import flet as ft
import argparse
import logging
import os
import platform
import sys
import threading

from dotenv import load_dotenv
load_dotenv()

from frontend.utils.recent_manager import RecentManager
from frontend.widgets.mic import MicMenu

ASR_MODEL_KEY = "faster-whisper:turbo"
#ASR_MODEL_KEY = "canary-v2:small"
#ASR_MODEL_KEY = "parakeet-v3:small"
#ASR_MODEL_KEY = "voxtral-mini:small"



def _prewarm_speech():
    try:
        from voice.speech import SpeechToText
        stt = SpeechToText()
        stt.load_model(ASR_MODEL_KEY)
        logging.info("Pre-warm concluído.")
    except Exception as e:
        logging.warning(f"Pre-warm falhou: {e}")


def _run_wakeword_listener():
    try:
        from voice.run_wakeword import wakeword_loop
        wakeword_loop()
    except Exception as e:
        logging.warning(f"Wakeword listener falhou: {e}")


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
        self.page.window.icon = "frontend/images/icon.png"


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
                from frontend.speech_menu import SpeechMenu
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
                from frontend.main_menu import MainEditorMenu
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
                    from frontend.editor_menu import EditorMenu
                    self.menu_instance = EditorMenu(self.page, self.mic_menu)

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
                from frontend.speech_menu import SpeechMenu
                from frontend.editor_menu import EditorMenu
                if mic_window.open:
                    self.mic_menu.handle_mic_click(mic_button=mic_window.content.content.controls[0])

                elif type(self.menu_instance) == SpeechMenu:
                    self.mic_menu.handle_mic_click(self.menu_instance.mic_card.content.controls[0])

                elif type(self.menu_instance) == EditorMenu and self.menu_instance.can_listen == True:
                    self.menu_instance.handle_mic_click(self.menu_instance.mic_button)

            if e.key == "F7":
                if hasattr(self.menu_instance, "speech"):
                    self.menu_instance.speech.stop_listen()

            if e.key == "F6":
                pass

            if e.ctrl and e.key == "P":
                if hasattr(self.menu_instance, "create_and_open_new_markdown"):
                    self.menu_instance.create_and_open_new_markdown()

            if e.ctrl and e.key == "N":
                if hasattr(self.menu_instance, "create_new_dir"):
                    self.menu_instance.create_new_dir()

            if e.ctrl and e.key == "S":
                if hasattr(self.menu_instance, "_save_now"):
                    self.menu_instance._save_now()


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

        threading.Thread(target=_prewarm_speech, daemon=True).start()
        threading.Thread(target=_run_wakeword_listener, daemon=True).start()

async def flet_target(page:ft.Page):
    app = MainPage(page)

    await app.main()


if __name__ == "__main__":
    if "--type-at-cursor" in sys.argv:
        from voice.type_at_cursor import TypeAtCursorMode
        TypeAtCursorMode().run()
        sys.exit(0)
    ft.run(flet_target, view=ft.AppView.FLET_APP)