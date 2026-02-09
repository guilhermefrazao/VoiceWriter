import flet as ft
import os
import asyncio
import logging

from frontend.widgets.context_menu import ContextMenu
from frontend.widgets.tiles_generic import Tiles
from frontend.utils.file_handler import DirectoryUtils
from frontend.widgets.containers_generic import Containers
from frontend.utils.recent_manager import RecentManager
from frontend.utils.color import hover_color_change

class EditorMenu():
    def __init__(self, page : ft.Page):
        self.page = page
        self.home_layout = None
        self.main_area = None
        self.dir_name = None
        self.new_message = ft.TextField(
            border=ft.InputBorder.NONE,
            always_call_on_tap=False,
            animate_cursor_opacity=True,
            multiline=True,
            text_size=16,
            autocorrect=True,
            expand=False,
            autofocus=True,
            disabled=True,
            on_change=lambda e: self.handler.save_changed_text(e)
        )
        self.file_tree_column = None
        self.sidebar = None
        self.current_file_path = str
        self.context_menu_right_click = ContextMenu()
        self.handler = DirectoryUtils()
        self.container = Containers()
        self.recent_manager = RecentManager()
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
                                on_secondary_tap_down=lambda e: asyncio.create_task(self.context_menu_right_click.show_context_menu(e)),
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

    def create_and_open_new_markdown(self):
        final_path, new_name = self.create_new_markdown()
        self.load_file_to_editor(new_name + ".md", final_path + ".md")


    def create_new_markdown(self):
        final_path, new_name = self.handler.name_counter(self.current_file_path, created_type="File")     
        self.refresh_sidebar(self.current_file_path)

        return final_path, new_name
            

    def create_new_dir(self):
        final_path, new_name = self.handler.name_counter(self.current_file_path, created_type="Dir")
        self.refresh_sidebar(self.current_file_path)


    def route_to_main_menu(self, page: ft.Page):
        asyncio.create_task(page.push_route("/"))


    def open_new_editor(self, e):
        logging.info(f"Navegando para {e.control.data}")
        self.page.views.clear()

        new_editor = ft.View(
                    route="/editor",
                    padding=0,
                    spacing=0,
                    controls=[]
                )

        self.page.views.append(new_editor)

        new_editor.controls.append(self.build_ui(path=e.control.data))

        self.page.update()


    def routes_menu(self):
        paths = self.recent_manager._load_from_disk()

        menu_items = []

        for path in paths:
            if path != self.current_file_path:
                folder_name = os.path.basename(path)
                menu_items.append(
                    ft.PopupMenuItem(
                        content=folder_name,
                        data=path,
                        on_click=lambda e: self.open_new_editor(e)
                    )
                )

 
        popup_menu = ft.PopupMenuButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.UNFOLD_MORE_DOUBLE_ROUNDED, size=16, color="#858585"),
                    ft.Text(os.path.basename(self.current_file_path), size=14, weight="bold", color="#858585", overflow=ft.TextOverflow.ELLIPSIS),
                ],
                spacing=5,
                alignment=ft.MainAxisAlignment.START,
            ),
            items=menu_items,
        )

        return ft.Container(
            content=popup_menu,
            padding=10,
            border_radius=5,
            bgcolor= ft.Colors.TRANSPARENT,
            on_hover=lambda e: hover_color_change(e),
        )


    def build_ui(self, path: str = "C:/Users/guilh/Documents/VoiceWriter/testes_folder"):
        self.page.padding = 0
        self.page.title = "Editor - Voice Writter"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.current_file_path = path

        intial_tree_controls = self.get_directory_tree(path)

        topbar = ft.Container(
            width=float("inf"),
            bgcolor="#202020",
            padding=10,
            content=ft.Row(
                controls=[
                    ft.Text("Editor - Voice Writter", size=12, weight="bold", color="#858585")
                ],
            ),
        )


        sidebar_icons = ft.Row(
            align=ft.Alignment.CENTER,
            controls=[
                ft.IconButton(icon=ft.Icons.PASTE, icon_color="#858585", highlight_color="#D4D4D4", on_click=self.create_new_markdown),
                ft.IconButton(icon=ft.Icons.FOLDER, icon_color="#858585", highlight_color="#D4D4D4", on_click=self.create_new_dir),
            ]
        )

        self.file_tree_column = ft.Column(
            controls=intial_tree_controls,
            spacing=2,
            scroll=ft.ScrollMode.AUTO,
            expand=True
        )

        routes_menu = self.routes_menu()

        self.sidebar = ft.Container(
            width=250,
            bgcolor="#202020",
            padding=10,
            content=ft.Column(
                controls=[
                    sidebar_icons,
                    self.file_tree_column,
                    ft.Column(spacing=2, horizontal_alignment=ft.CrossAxisAlignment.START, controls=[ft.IconButton(icon=ft.Icons.ARROW_BACK, icon_color="#D4D4D4", on_click=lambda e: self.route_to_main_menu(self.page)), ft.Text("Back", size=16, color="#858585")]),
                    ft.Divider(height=1, color="#0C5F49"),
                    routes_menu
                ]
            )
        )


        self.dir_name = ft.Column(
            align=ft.Alignment.CENTER,
            spacing=20,
            controls=[ ft.Text("Create new file", size=14, weight="bold", color="#0C5F49", selectable=True, on_tap=self.create_and_open_new_markdown), 
                    ft.Text("Open recent file", size=14, weight="bold", color="#0C5F49",selectable=True, on_tap=lambda e: print("Open Recent"))])


        self.main_area = ft.Container(
                expand=True,
                bgcolor="#11111",
                padding=300,
                align=ft.Alignment.CENTER,
                content=ft.Column(
                    align=ft.Alignment.CENTER,
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
                ft.Divider(height=1, color="#0C5F49"),
                side_layout
            ],
            expand=True,
            spacing=0
        )
        
        return self.home_layout
    

