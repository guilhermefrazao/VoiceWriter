import flet as ft
import os
import threading
import logging
import shutil

class DirectoryUtils():
    def __init__(self):
        self.save_timer = None
        self.old_path = None
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

        main_area.padding = 20
        
        main_area.update()


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


    def make_draggable(self, tile, full_path):
        return ft.Draggable(
            group="folder",
            content=tile,
            content_feedback=tile,
            content_when_dragging=tile,
            data=full_path
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