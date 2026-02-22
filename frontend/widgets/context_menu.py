import flet as ft
import os
import logging

from send2trash import send2trash
from frontend.utils.color import hover_color_change

class ContextMenu():
    def __init__(self, page):
        self.page = page
        self.current_menu = None


    def close_menu(self, e=None):
        if self.current_menu in self.page.overlay:
            self.page.overlay.remove(self.current_menu)
            self.current_menu = None
            self.page.update()


    def show_menu(self, e, w, tile, callbacks):
        self.close_menu()

        menu_items = []
        for title, action in callbacks.items():
            menu_items.append(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.CIRCLE, size=8, color="#858585"), 
                        ft.Text(title, size=14, color="#D4D4D4")
                    ]),
                    padding=10,
                    border_radius=4,
                    on_click=lambda ev, func=action: [func(ev, w, tile), self.close_menu()],
                    on_hover=lambda e: hover_color_change(e)
                )
            )

        card_content = ft.Container(
            content=ft.Column(controls=menu_items, spacing=0),
            bgcolor="#1e1e1e", 
            border=ft.border.all(1, "#333333"),
            border_radius=8,
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=15,
                color=ft.Colors.with_opacity(0.5, "black"),
            ),
            padding=5,
            width=200, 
        )

        self.current_menu = ft.Stack([
            ft.Container(
                expand=True,
                width=self.page.window.width,
                height=self.page.window.height,
                bgcolor=ft.Colors.TRANSPARENT,
                on_click=self.close_menu
            ),
            ft.Container(
                content=card_content,
                left=e.global_position.x,
                top=e.global_position.y,
            )
        ])

        self.page.overlay.append(self.current_menu)
        self.page.update()


    def _revert_to_text(self, wrapper, tile, name):
        tile.title = ft.Text(
            name, 
            size=14, 
            color="#858585", 
            max_lines=1, 
            overflow=ft.TextOverflow.ELLIPSIS, 
            tooltip=name
        )
        wrapper.update()
    

    def _finish_rename(self, e, wrapper, tile, old_name):
        new_name = tile.title.value
        
        if not new_name or new_name == old_name:
            self._revert_to_text(wrapper, tile, old_name)
            return

        old_path = tile.data 

        parent_dir = os.path.dirname(old_path)

        if old_name.endswith(".md"):
            new_name = new_name + ".md"

        new_path = os.path.join(parent_dir, new_name)

        try:
            os.rename(old_path, new_path)
            tile.data = new_path
            self._revert_to_text(wrapper, tile, new_name)
        
        except Exception as ex:
            logging.info(f"Erro ao renomear: {ex}")
            self._revert_to_text(wrapper, tile, old_name)

    
    def rename_widget(self, e: ft.TapEvent, parent_wrapper, tile):
        current_name: str = os.path.basename(tile.data)

        display_name = current_name.removesuffix(".md") if current_name.endswith(".md") else current_name

        edit_field = ft.TextField(
            value=display_name,
            dense=True,
            text_size=14,
            content_padding=5,
            autofocus=True, 
            on_submit=lambda e: self._finish_rename(e, parent_wrapper, tile, current_name),
            on_blur=lambda e: self._finish_rename(e, parent_wrapper, tile, current_name) 
        )
        
        tile.title = edit_field
        parent_wrapper.update()


    def delete_widget(self, e: ft.TapEvent, parent_wrapper, tile):
        path_to_delete = tile.data 
        if not path_to_delete:
            return
        try:
            if os.path.isdir(path_to_delete):
                send2trash(path_to_delete)
            else:
                send2trash(path_to_delete)   
           
            gesture_detector = parent_wrapper.parent
            parent_collum = gesture_detector.parent
            if parent_collum and gesture_detector in parent_collum.controls:
                parent_collum.controls.remove(gesture_detector)
                parent_collum.update()
                
            logging.info(f"Sucesso ao deletar: {path_to_delete}")

        except Exception as ex:
            logging.error(f"Erro ao deletar: {ex}")
    

    def open_properties(self, e: ft.TapEvent, parent_wrapper, tile):
        pass