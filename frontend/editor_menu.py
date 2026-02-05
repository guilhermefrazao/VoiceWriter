import flet as ft
import os
import asyncio
import logging

from frontend.widgets.context_menu import ContextMenu
from frontend.widgets.tiles_generic import Tiles
from frontend.utils.file_handler import DirectoryUtils

class EditorMenu():
    def __init__(self):
        self.home_layout = None
        self.main_area = None
        self.dir_name = None
        self.new_message = None
        self.file_tree_column = None
        self.sidebar = None
        self.last_selected_file = None
        self.current_file_path = str
        self.context_menu_right_click = ContextMenu()
        self.handler = DirectoryUtils()
        self.generic_tile = Tiles(self.load_file_to_editor)


    def get_directory_tree(self, path):
        controls = []
        try:
            items = sorted(os.listdir(path), key=lambda x: (not os.path.isdir(os.path.join(path, x))))

            for item in items:
                full_path = os.path.join(path, item)

                if os.path.isdir(full_path):
                    tile = self.generic_tile.generic_expand_tile(item, full_path, self.get_directory_tree)
                else:
                    if item.endswith(".md"):
                        tile = self.generic_tile.generic_list_tile(item, full_path)
                        
                
                controls.append( 
                            menu := ft.ContextMenu(
                            expand=True,
                            items=[
                                    ft.PopupMenuItem(
                                        content="Rename",
                                        on_click=lambda e: self.context_menu_right_click.rename_widget(),
                                    ),
                                    ft.PopupMenuItem(
                                        content="Delete",
                                        on_click=lambda e: self.context_menu_right_click.delete_widget(),
                                    ),
                                    ft.PopupMenuItem(
                                        content="Properties",
                                        on_click=lambda e: self.context_menu_right_click.open_properties(),
                                    ),
                                ],
                            content = ft.GestureDetector(
                                mouse_cursor=ft.MouseCursor.CONTEXT_MENU,
                                on_secondary_tap_down=lambda e: asyncio.create_task(self.context_menu_right_click.show_context_menu(e, menu)),
                                content=tile
                            )
                        )
                    )       
                        
        
        except Exception as e:
            logging.error(f"Exception occured {e} with {path}")

        return controls


    def refresh_sidebar(self, path):
        new_directory_controls = self.get_directory_tree(path)
        self.file_tree_column.controls = new_directory_controls
        self.sidebar.content.controls[1] = self.file_tree_column 
        self.sidebar.update()


    def load_file_to_editor(self, item_name : str, full_path: str):
        self.handler.display_markdown_information(
            item=item_name,
            path=full_path,
            dir_widget=self.dir_name,
            message_widget=self.new_message,
            main_area=self.main_area
        )


    def create_new_markdown(self):
        self.handler.name_counter(self.current_file_path, created_type="File")     
        self.refresh_sidebar(self.current_file_path)
            

    def create_new_dir(self):
        self.handler.name_counter(self.current_file_path, created_type="Dir")
        self.refresh_sidebar(self.current_file_path)


    def page(self, page: ft.Page, path: str = "C:/Users/guilh/Documents/Obsidian Vault/Ideias_Pessoais/Games"):
        page.padding = 0
        page.title = "Editor - Voice Writter"
        page.theme_mode = ft.ThemeMode.DARK
        self.current_file_path = path

        intial_tree_controls = self.get_directory_tree(path)

        topbar = ft.Container(
            width=float("inf"),
            bgcolor="#202020",
            padding=10,
            content=ft.Row(
                controls=[
                    ft.Text("Editor - Voice Writter", size=12, weight="bold", color="grey")
                ],
            ),
        )

        sidebar_icons = ft.Row(
            align=ft.Alignment.CENTER,
            controls=[
                ft.IconButton(icon=ft.Icons.PASTE, icon_color="grey", highlight_color="white", on_click=self.create_new_markdown),
                ft.IconButton(icon=ft.Icons.FOLDER, icon_color="grey", highlight_color="white", on_click=self.create_new_dir),
            ]
        )

        self.file_tree_column = ft.Column(
            controls=intial_tree_controls,
            spacing=2,
            scroll=ft.ScrollMode.AUTO,
            expand=True
        )

        self.sidebar = ft.Container(
            width=250,
            bgcolor="#202020",
            padding=10,
            content=ft.Column(
                controls=[
                    sidebar_icons,
                    self.file_tree_column,
                    ft.Column(spacing=2, horizontal_alignment=ft.CrossAxisAlignment.START, controls=[ft.IconButton(icon=ft.Icons.ARROW_BACK, icon_color="white", on_click=lambda e: asyncio.create_task(page.push_route("/"))), ft.Text("Back", size=16, color="grey")])
                ]
            )
        )

        self.dir_name = ft.Text("Default Dir.Md", size=30, weight="bold")
        
        self.new_message = ft.TextField(
            border=ft.InputBorder.NONE,
            always_call_on_tap=False,
            animate_cursor_opacity=True,
            multiline=True,
            text_size=16,
            autocorrect=True,
            expand=True,
            autofocus=True,
            on_change=lambda e: self.handler.save_changed_text(e)
        )


        self.main_area = ft.Container(
                expand=True,
                bgcolor="#1A1A1A",
                padding=20,
                content=ft.Column(
                    controls=[
                        self.dir_name,
                        self.new_message
                    ]
                )
        )

        side_layout = ft.Row(
            controls=[
                self.sidebar,
                ft.VerticalDivider(width=1, color="#0C5F49"),
                self.main_area
            ],
            expand=True,
            spacing=0
        )

        self.home_layout = ft.Column(
            controls=[
                topbar,
                ft.Divider(height=1, color="#0C5F49"),
                side_layout
            ],
            expand=True,
            spacing=0
        )
        
        return self.home_layout
    


    def main(self, page: ft.Page, path: str = "C:/Users/guilh/Documents/Obsidian Vault/Ideias_Pessoais/Games"):
        home_layout = self.page(page, path)

        page.add(home_layout)


if __name__ == "__main__":
    main = EditorMenu()
    ft.run(main.main)