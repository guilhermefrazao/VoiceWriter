import flet as ft
import os
import threading
import logging
import shutil

from frontend.utils.color import hover_color_change

class DirectoryUtils():
    def __init__(self):
        self.save_timer = None
        self.old_path = None
        self.selected_tile = None
        pass

    async def open_explorer(self) -> str:
        return await ft.FilePicker().get_directory_path()
    

    def display_markdown_information(self, item: str, path: str, dir_widget, message_widget, main_area, refresh_sidebar):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        if item.endswith(".md"):
            display_name = item.removesuffix(".md")
            markdown = True

        self.old_path = path

        dir_widget.controls = [ft.TextField(display_name,  border=ft.InputBorder.NONE, text_size=30,  multiline=False, autofocus=False, color="#D4D4D4", on_change=lambda e: self.change_directory_title_name(e, refresh_sidebar, markdown), expand=True)]
        message_widget.value = content
        message_widget.data = path
        message_widget.disabled = False
        message_widget.autofocus = True
        message_widget.expand = True

        main_area.padding = 20
        
        main_area.update()

    
    def handle_tile_change(self, e: ft.Event[ft.ExpansionTile], on_file_open, selected_tile):
        self.on_file_selected(e, on_file_open, selected_tile=selected_tile, file_type="Folder")
        e.control.leading.icon = (
            ft.Icons.KEYBOARD_ARROW_RIGHT   
            if e.control.leading.icon == ft.Icons.KEYBOARD_ARROW_DOWN  
            else ft.Icons.KEYBOARD_ARROW_DOWN
        )
        e.page.update()


    def on_file_selected(self, e: ft.Event[ft.ExpansionTile], on_file_open, selected_tile=None, file_type="files"):
        if selected_tile:
            self.selected_tile = selected_tile

        if isinstance(e.control, ft.ExpansionTile):
            return 

        if self.selected_tile == e.control:
            e.control.shape = ft.RoundedRectangleBorder(side=ft.BorderSide(width=1,  color="#D4D4D4"), radius=5)
            e.control.update()
            return 

        
        if self.selected_tile:
            if file_type == "files":
                self.selected_tile.bgcolor = ft.Colors.TRANSPARENT
                self.selected_tile.shape = None
                self.selected_tile.update()
            else:
                self.selected_tile.collapsed_bgcolor = ft.Colors.TRANSPARENT
                self.selected_tile.shape = None
                self.selected_tile.update()
            
        if file_type == "files":
            e.control.bgcolor = "#37373d"
            e.control.shape = None
            e.control.update()
        else:
            e.control.collapsed_bgcolor = "#37373d"
            e.control.shape = None
            e.control.update()

        self.selected_tile = e.control

        if on_file_open:
            item_name = e.control.title.value
            full_path = e.control.data
            on_file_open(item_name, full_path)


    def name_counter(self, current_path: str, created_type: str ="File") -> tuple[str, str]:
        counter = 0
        counting = True

        while counting:   
            if counter > 0:
                new_name = f"Untitled {counter}"
            else:
                new_name = "Untitled"
            
            final_path = os.path.join(current_path, new_name)


            if created_type.lower() == "file":
                if not os.path.exists(final_path + ".md"):
                    with open(final_path + ".md", "w", encoding="utf-8") as file:
                        file.write(new_name)
                        counting = False
            
            if created_type.lower() == "dir":
                if not os.path.exists(final_path):
                        os.makedirs(final_path)
                        counting = False

            counter += 1

        return final_path, new_name

   
    def save_changed_text(self, e):
        if self.save_timer:
            self.save_timer.cancel()

        self.save_timer = threading.Timer(1.0, self.save_to_disk, args=[e.control.data, e.data])
        self.save_timer.start()

   
    def save_to_disk(self, file_path, new_message):
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(new_message)

            except Exception as e:
                print(f"Erro ao salvar: {e}")

   
    def change_directory_title_name(self, e, refresh_sidebar, markdown: bool=True):
        dir_name = os.path.dirname(self.old_path)

        logging.info(f"data controls {dir_name}")

        new_path = os.path.join(dir_name, e.control.value.strip())

        if markdown:
            new_path = new_path + ".md"

        if new_path.strip() == ".md":
            os.rename(self.old_path, "Untitled.md")
        else:
            os.rename(self.old_path, new_path)

        refresh_sidebar()

        self.old_path = new_path


    def _on_drag_start(self, e, tile_wrapper, tile_type: str):
        if tile_type == "files":
            tile_wrapper.bgcolor = "#055b5f"
        else:
            tile_wrapper.collapsed_bgcolor = "#055b5f"
        tile_wrapper.update()


    def _on_drag_end(self, e, tile_wrapper, tile_type: str):
        if tile_type == "files":
            tile_wrapper.bgcolor = ft.Colors.TRANSPARENT
        else:
            tile_wrapper.collapsed_bgcolor = ft.Colors.TRANSPARENT
        tile_wrapper.update()


    def _create_drag_feedback(self, item_name, is_folder):
        icon = ft.Icons.FOLDER if is_folder else ft.Icons.DESCRIPTION
        
        feedback_card = ft.Container(
            bgcolor="#202020", 
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            border_radius=6,
            content=ft.Row(
                controls=[
                    ft.Icon(icon, color="#858585", size=16),
                    ft.Text(
                        item_name, 
                        color="#858585", 
                        size=14, 
                        overflow=ft.TextOverflow.ELLIPSIS
                    ),
                ],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
        )
        
        return feedback_card


    def make_draggable(self, tile, full_path, tile_type: str = "files"):

        feedback_widget = self._create_drag_feedback(os.path.basename(full_path), tile_type)

        return ft.Draggable(
            group="folder",
            content=tile,
            content_feedback=feedback_widget,
            data=full_path,
            on_drag_start=lambda e: self._on_drag_start(e, tile, tile_type),
            on_drag_complete=lambda e: self._on_drag_end(e, tile, tile_type),
        )
    

    def move_file_on_drop(self, e: ft.DragStartEvent, dst_dir, refresh_sidebar):
        src_path = e.src.data
        file_name = os.path.basename(src_path)
        final_destination = os.path.join(dst_dir, file_name)

        try:
            if src_path == final_destination:
                return

            shutil.move(src_path, final_destination)
            
            logging.info(f"Movido: {src_path} -> {final_destination}")
            
            refresh_sidebar()

        except Exception as ex:
            logging.error(f"Erro ao mover arquivo: {ex}")