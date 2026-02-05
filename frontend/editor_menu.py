import flet as ft
import os
import asyncio
import threading

from frontend.widgets.context_menu import ContextMenu
from frontend.widgets.tiles_generic import Tiles

class EditorMenu():
    def __init__(self):
        self.home_layout = ""
        self.main_area = None
        self.file_tree_column = None
        self.dir_name = None
        self.save_timer = None
        self.sidebar = None
        self.last_selected_file = None
        self.current_file_path = str
        self.context_menu_right_click = ContextMenu()
        self.generic_tile = Tiles()


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
            print(f"Exception occured {e} with {path}")

        return controls


    def refresh_sidebar(self, path):
        new_directory_controls = self.get_directory_tree(path)
        self.file_tree_column.controls = new_directory_controls
        self.sidebar.content.controls[1] = self.file_tree_column 
        self.sidebar.update()
        

    def name_counter(self, created_type="File"):
        counter = 0
        counting = True

        while counting:   
            if counter > 0:
                new_name = f"Untitled {counter}"
            else:
                new_name = "Untitled"
            
            final_path = os.path.join(self.current_file_path, new_name)
            
            if not os.path.exists(final_path):
                if created_type.lower() == "file":
                    with open(final_path + ".md", "w", encoding="utf-8") as file:
                        file.write(new_name)

                if created_type.lower() == "dir":
                    os.makedirs(final_path)

                counting = False

            counter += 1


    def create_new_markdown(self):
        self.name_counter(created_type="File")     
        self.refresh_sidebar(self.current_file_path)
            

    def create_new_dir(self):
        self.name_counter(created_type="Dir")
        self.refresh_sidebar(self.current_file_path)


    def save_changed_text(self):
        if self.save_timer:
            self.save_timer.cancel()

        self.save_timer = threading.Timer(1.0, self.save_to_disk)
        self.save_timer.start()


    def save_to_disk(self):
        if self.current_file_path:
            try:
                with open(self.current_file_path, "w", encoding="utf-8") as f:
                    f.write(self.new_message.value)

            except Exception as e:
                print(f"Erro ao salvar: {e}")


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

        sidebar_buttons = ft.Row(
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
                    sidebar_buttons,
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
            on_change=self.save_changed_text
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