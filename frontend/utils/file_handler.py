import flet as ft
import os
import threading

class DirectoryUtils():
    def __init__(self):
        self.save_timer = None
        pass

    async def open_explorer(self) -> str:
        return await ft.FilePicker().get_directory_path()
    

    def display_markdown_information(self, item: str, path: str, dir_widget, message_widget, main_area):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        dir_widget.value = item
        message_widget.value = content
        message_widget.data = path
        
        main_area.update()


    def name_counter(self, current_path, created_type="File"):
        counter = 0
        counting = True

        while counting:   
            if counter > 0:
                new_name = f"Untitled {counter}"
            else:
                new_name = "Untitled"
            
            final_path = os.path.join(current_path, new_name)
            
            if not os.path.exists(final_path):
                if created_type.lower() == "file":
                    with open(final_path + ".md", "w", encoding="utf-8") as file:
                        file.write(new_name)

                if created_type.lower() == "dir":
                    os.makedirs(final_path)

                counting = False

            counter += 1

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