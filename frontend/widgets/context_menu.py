import flet as ft
import os
import logging

from send2trash import send2trash

class ContextMenu():
    def __init__(self):
        self.current_selected_item = None
        self.directory_column = None


    async def show_context_menu(self, e: ft.TapEvent[ft.GestureDetector]):
        self.current_selected_item = e.control.content
        self.directory_column = e.control.parent
        
        await self.directory_column.open(
            local_position=e.local_position,
            global_position=e.global_position
        )


    def revert_to_text(self, tile, name):
        tile.title = ft.Text(
            name, 
            size=14, 
            color="#A4A5A5", 
            max_lines=1, 
            overflow=ft.TextOverflow.ELLIPSIS, 
            tooltip=name
        )
        tile.update()
    

    def finish_rename(self, e, tile, old_name):
        new_name = tile.title.value
        
        if not new_name or new_name == old_name:
            self.revert_to_text(tile, old_name)
            return

        old_path = tile.data 
        parent_dir = os.path.dirname(old_path)

        if old_name.endswith(".md"):
            new_name = new_name + ".md"

        new_path = os.path.join(parent_dir, new_name)

        try:
            os.rename(old_path, new_path)
            tile.data = new_path
            self.revert_to_text(tile, new_name)
        except Exception as ex:
            print(f"Erro ao renomear: {ex}")
            self.revert_to_text(tile, old_name)

        pass

    
    def rename_widget(self):
        current_name: str = self.current_selected_item.title.value
        
        edit_field = ft.TextField(
            value=current_name,
            dense=True,
            text_size=14,
            content_padding=5,
            autofocus=True, 
            on_submit=lambda e: self.finish_rename(e, self.current_selected_item, current_name),
            on_blur=lambda e: self.finish_rename(e, self.current_selected_item, current_name) 
        )
        
        if current_name.endswith(".md"):
            correct_name = current_name.strip(".md")
            edit_field.value = correct_name
        
        self.current_selected_item.title = edit_field
        self.current_selected_item.update()


    def delete_widget(self):
        tile = self.current_selected_item
        path_to_delete = tile.data 
        if not path_to_delete:
            return
        try:
            if os.path.isdir(path_to_delete):
                send2trash(path_to_delete)
            else:
                send2trash(path_to_delete)   

            main_container = self.directory_column.parent 
            if main_container and  self.directory_column in main_container.controls:
                logging.info(main_container)
                main_container.controls.remove(self.directory_column)
                main_container.update()
                
            print(f"Sucesso ao deletar: {path_to_delete}")

        except Exception as ex:
            print(f"Erro ao deletar: {ex}")
    

    def open_properties(self):
        pass