import flet as ft

class DirectoryUtils():
    def __init__(self):
        pass

    async def open_explorer(self) -> str:
        return await ft.FilePicker().get_directory_path()
    

    def display_markdown_information(self, item: str, path: str, dir_widget, message_widget, main_area):
        with open(path, "r", encoding="uft-8") as f:
            content = f.read()

        dir_widget.value = item
        message_widget.value = content
        
        main_area.update()