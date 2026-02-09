import flet as ft
import argparse
import logging
import os
import sys

from frontend.main_menu import MainEditorMenu
from frontend.editor_menu import EditorMenu
from frontend.utils.recent_manager import RecentManager


logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO, encoding="utf-8", handlers=[
        logging.FileHandler("frontend.log", encoding='utf-8'), 
        logging.StreamHandler(sys.stdout)                    
        ])

async def main(page: ft.Page):
    page.title = "Voice Writter"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0

    parser = argparse.ArgumentParser(description='Voice Writter App')
    parser.add_argument('--editor', type=str, nargs="?", const="last_path", help='Abrir o editor no último caminho utilizado')
    args, unknown = parser.parse_known_args()

    async def route_change():
        page.views.clear()

        if page.route == "/":
            menu_instance = MainEditorMenu(page) 
            
            home_view = ft.View(
                route="/",
                padding=0, 
                spacing=0,
                controls=[]
            )
            
            page.views.append(home_view)
            
            home_view.controls.append(menu_instance.build_ui())

        if page.route == "/editor":
            current_path = page.current_project_path
            
            if current_path and os.path.exists(current_path):
                editor_instance = EditorMenu(page)

                editor_layout = ft.View(
                    route="/editor",
                    padding=0,
                    spacing=0,
                    controls=[]
                )

                page.views.append(editor_layout)

                editor_layout.controls.append(editor_instance.build_ui(current_path))
                
            else:
                logging.info("Path inválido ou não fornecido, voltando para Home.")
                await page.push_route("/")

        page.update()

    async def view_pop(view):
        page.views.pop()
        top_view = page.views[-1]
        await page.push_route(top_view.route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop

    if args.editor:
        manager = RecentManager().get_recents()[0]
        logging.info(f"Manager: {manager}")
        page.current_project_path = manager
        await page.push_route("/editor")
    else:
        await route_change()


if __name__ == "__main__":
    ft.run(main)