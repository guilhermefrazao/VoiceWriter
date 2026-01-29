import flet as ft
import os
import asyncio
import threading
from widgets.context_menu import ContextMenu

class EditorMenu():
    def __init__(self):
        self.home_layout = ""
        self.page_var = ft.Page
        self.main_area = ft.Container
        self.file_tree_column = ft.Column
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
            on_change=self.on_change_text
        )
        self.save_timer = None
        self.current_file_path = str
        self.sidebar = ft.Container
        self.last_selected_file = None
        self.context_menu_right_click = ContextMenu()


    def get_directory_tree(self, path):
        controls = []
        try:
            items = sorted(os.listdir(path), key=lambda x: (not os.path.isdir(os.path.join(path, x))))

            for item in items:
                full_path = os.path.join(path, item)

                if os.path.isdir(full_path):
                        expand_tile = ft.ExpansionTile(
                            title = ft.Text(item, size=14, color="#A4A5A5", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, tooltip=item),
                            leading=ft.Icon(ft.Icons.KEYBOARD_ARROW_RIGHT, size=12, color="grey"),
                            animation_style=ft.AnimationStyle(duration=20, reverse_duration=20),
                            affinity=ft.TileAffinity.LEADING,
                            collapsed_shape=ft.RoundedRectangleBorder(),
                            shape=ft.RoundedRectangleBorder(),
                            tile_padding=ft.Padding.symmetric(horizontal=10, vertical=0),
                            data=full_path,
                            controls_padding=ft.Padding.only(left=20),
                            controls=[ft.Container(border=ft.Border.only(left=ft.BorderSide(1, "#0C5F49")),
                                                   padding=ft.Padding.only(left=10),
                                                   content=ft.Column(controls=self.get_directory_tree(full_path),spacing=0))],
                            on_change=self.handle_tile_change,
                        )

                        controls.append(
                            menu := ft.ContextMenu(
                            expand=True,
                            items=[
                                    ft.PopupMenuItem(
                                        content="Rename",
                                        on_click=lambda e: self.rename_widget(e),
                                    ),
                                    ft.PopupMenuItem(
                                        content="Delete",
                                        on_click=lambda e: self.delete_widget(),
                                    ),
                                    ft.PopupMenuItem(
                                        content="Properties",
                                        on_click=lambda e: self.open_properties(),
                                    ),
                                ],
                            content=ft.GestureDetector(
                            mouse_cursor=ft.MouseCursor.CONTEXT_MENU,
                            on_secondary_tap_down=lambda e: asyncio.create_task(self.context_menu_right_click.show_context_menu(e, menu, is_folder=True)),
                            content=expand_tile
                            )
                        )
                    )
                else:
                    if item.endswith(".md"):
                        list_tile = ft.ListTile(
                                title=ft.Text(item, size=14, color="grey", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, tooltip=item),
                                height=50,
                                content_padding=ft.Padding.symmetric(horizontal=10, vertical=0),
                                hover_color="black",
                                data=full_path,
                                is_three_line=False,
                                on_click=lambda e, p=full_path: self.display_markdown_information(item, p, e)
                            )
                        
                        controls.append( 
                            menu := ft.ContextMenu(
                            expand=True,
                            items=[
                                    ft.PopupMenuItem(
                                        content="Rename",
                                        on_click=lambda e: self.rename_widget(e),
                                    ),
                                    ft.PopupMenuItem(
                                        content="Delete",
                                        on_click=lambda e: self.delete_widget(),
                                    ),
                                    ft.PopupMenuItem(
                                        content="Properties",
                                        on_click=lambda e: self.open_properties(),
                                    ),
                                ],
                            content = ft.GestureDetector(
                                mouse_cursor=ft.MouseCursor.CONTEXT_MENU,
                                on_secondary_tap=lambda e: asyncio.create_task(self.context_menu_right_click.show_context_menu(e, menu, is_folder=False)),
                                content=list_tile
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


    def on_file_click(self, e: ft.Event[ft.ExpansionTile]):
        if isinstance(e.control, ft.ExpansionTile):
            return 

        
        if self.last_selected_file == e.control:
            e.control.shape = ft.RoundedRectangleBorder(side=ft.BorderSide(width=1,  color="white"), radius=5)
            e.control.update()
            return 

        
        if self.last_selected_file:
            self.last_selected_file.bgcolor = ft.Colors.TRANSPARENT
            self.last_selected_file.shape = None
            self.last_selected_file.update()
            
        e.control.bgcolor = "#37373d"
        e.control.shape = None
        e.control.update()

        self.last_selected_file = e.control
        full_path = e.control.data
        


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


    def on_change_text(self):
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


    def display_markdown_information(self, item, path, e: ft.Event[ft.ListTile]):
        self.on_file_click(e)
        self.dir_name.value = item

        f = open(path, "r")
        self.new_message.value = f.read()

        self.main_area.content.controls = [self.dir_name, self.new_message]

        self.main_area.update()


    def handle_tile_change(self, e: ft.Event[ft.ExpansionTile]):
        self.on_file_click(e)
        e.control.leading.icon = (
            ft.Icons.KEYBOARD_ARROW_RIGHT   
            if e.control.leading.icon == ft.Icons.KEYBOARD_ARROW_DOWN  
            else ft.Icons.KEYBOARD_ARROW_DOWN
        )
        self.page_var.update()

    def activate_edit(self):
        pass

    def rename_widget(self, e: ft.Event[ft.ExpansionTile]):
        current_text = e.control.content 

        current_text.title = ""

        pass

    def delete_widget(self):
        pass
    
    def open_properties(self):
        pass

    def page(self, page: ft.Page, path: str = "C:/Users/guilh/Documents/Obsidian Vault/Ideias_Pessoais/Games"):
        page.padding = 0
        page.title = "Editor - Voice Writter"
        page.theme_mode = ft.ThemeMode.DARK
        self.page_var = page
        self.current_file_path = path

        intial_tree_controls = self.get_directory_tree(path)

        topbar = ft.Container(
            width=float("inf"),
            bgcolor="#202020",
            padding=10,
            content=ft.Row(
                controls=[
                    ft.Text("Upbar", size=12, weight="bold", color="grey")
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

        self.main_area = ft.Container(
                expand=True,
                bgcolor="#11111",
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