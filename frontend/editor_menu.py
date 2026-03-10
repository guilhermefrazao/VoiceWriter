import flet as ft
import os
import asyncio
import logging
import keyboard

from frontend.widgets.context_menu import ContextMenu
from frontend.widgets.tiles_generic import Tiles
from frontend.utils.file_handler import DirectoryUtils
from frontend.widgets.containers_generic import Containers
from frontend.utils.recent_manager import RecentManager
from frontend.utils.color import hover_color_change
from voice.speech import SpeechToText
from frontend.widgets.toolbar import TopToolbar 

class EditorMenu():
    def __init__(self, page : ft.Page):
        self.page = page
        keyboard.add_hotkey("ctrl+p", self.create_and_open_new_markdown)
        keyboard.add_hotkey("ctrl+n", self.create_new_dir)
        self.new_message = ft.TextField(
            border=ft.InputBorder.NONE,
            always_call_on_tap=False,
            animate_cursor_opacity=True,
            multiline=True,
            text_size=14,
            border_color="#333333",
            color="#D4D4D4",
            focused_border_color="#555555",
            autocorrect=True,
            expand=False,
            disabled=True,
            autofocus=True,
            on_change=lambda e: self.handler.save_changed_text(e)
        )
        self.current_file_path = str
        self.context_menu_right_click = ContextMenu(page)
        self.handler = DirectoryUtils()
        self.container = Containers()
        self.recent_manager = RecentManager()
        self.generic_tile = Tiles()
        self.speech = SpeechToText()
        self.can_listen = False
        self.open_file_path = str



    def get_directory_tree(self, path):
        controls = []
        try:
            items = sorted(os.listdir(path), key=lambda x: (not os.path.isdir(os.path.join(path, x))))

            for item in items:
                full_path = os.path.join(path, item)
                
                if os.path.isdir(full_path):
                    wrapper, tile = self.generic_tile.generic_expand_tile(item, full_path, self.get_directory_tree, self.refresh_sidebar)
                else:
                    if item.endswith(".md"):
                        wrapper, tile = self.generic_tile.generic_list_tile(item, full_path, self.refresh_sidebar, self.load_file_to_editor)
                    else:
                        continue 

                item_actions = {
                "Rename": lambda e, w=wrapper, t=tile: self.context_menu_right_click.rename_widget(e, w, t),
                "Delete": lambda e, w=wrapper, t=tile: self.context_menu_right_click.delete_widget(e, w, t),
                "Properties": lambda e, w=wrapper, t=tile: self.context_menu_right_click.open_properties(e, w, t)
                }


                controls.append(
                    ft.GestureDetector(
                        mouse_cursor=ft.MouseCursor.CONTEXT_MENU,
                        on_secondary_tap_up=lambda e, w=wrapper, acts=item_actions, t=tile: self.context_menu_right_click.show_menu(e, w, t, acts),
                        content=wrapper
                    )
                )   
                        
        
        except Exception as e:
            logging.error(f"Exception occured {e} with {path}")

        return controls


    def refresh_sidebar(self):
        new_directory_controls = self.get_directory_tree(self.current_file_path)
        self.file_tree_column.controls = new_directory_controls
        self.file_tree_column.update()


    def load_file_to_editor(self, item_name : str, full_path: str):
        self.open_file_path = full_path
        self.handler.display_markdown_information(
            item=item_name,
            path=full_path,
            dir_widget=self.dir_name,
            message_widget=self.new_message,
            main_topbar=self.main_area_topbar,
            main_area=self.main_area,
            refresh_sidebar=self.refresh_sidebar,
            mic=self.mic_button
        )

        self.can_listen = True


    def create_and_open_new_markdown(self):
        final_path, new_name = self.handler.name_counter(self.current_file_path, created_type="File")     
        self.refresh_sidebar()
        self.load_file_to_editor(new_name + ".md", final_path + ".md")
        

    def create_new_dir(self):
        final_path, new_name = self.handler.name_counter(self.current_file_path, created_type="Dir")
        self.refresh_sidebar()


    def route_to_main_menu(self, page: ft.Page):
        asyncio.create_task(page.push_route("/main_menu"))


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
            border_radius=0,
            bgcolor= ft.Colors.TRANSPARENT,
            on_hover=lambda e: hover_color_change(e),
            border=ft.border.only(top=ft.border.BorderSide(width=1, color="#055b5f")),
            height=50
        )
    

    def handle_mic_click(self, mic_button, e=None):
        if getattr(self, "is_listening", False):
            return

        self.is_listening = True

        self.page.run_task(self.pulse_animation, mic_button)
        
        self.page.run_task(self._run_speech_recognition)


    async def pulse_animation(self, container_button: ft.Container):
        await asyncio.sleep(0.75)
        while self.is_listening:
            container_button.scale = 1.15
            container_button.shadow.color = ft.Colors.with_opacity(0.6, "#028268") 
            container_button.shadow.spread_radius = 5
            container_button.content.color = "#028268" 
            container_button.update()
            
            await asyncio.sleep(0.5)
            
            if not self.is_listening:
                break
                
            container_button.scale = 1.0
            container_button.shadow.color = ft.Colors.with_opacity(0.15, "blue")
            container_button.shadow.spread_radius = 1
            container_button.content.color = "white"
            container_button.update()
            
            await asyncio.sleep(0.5) 


        container_button.scale = 1.0
        container_button.shadow.color = ft.Colors.with_opacity(0.15, "blue")
        container_button.shadow.spread_radius = 1
        container_button.content.color = "white"
        container_button.update()


    async def _run_speech_recognition(self):
        try:
            recognized_speech = await asyncio.to_thread(self.speech.main_transcription)

            await self.update_interface(recognized_speech)

        except Exception as e:
            print(f"Erro no reconhecimento: {e}")
        finally:
            self.is_listening = False


    async def update_interface(self, recognized_speech: str):
        self.new_message.value += f" {recognized_speech}"
        
        await self.new_message.focus()

        self.new_message.update()




    def build_ui(self, path: str = "C:/Users/guilh/Documents/VoiceWriter/testes_folder"):
        self.page.padding = 0
        self.page.title = "Editor - Voice Writter"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.current_file_path = path
        self.open_file_path = path

        intial_tree_controls = self.get_directory_tree(path)

        self.mic_button = self.container.generic_container_with_mic_button(width=80, height=80, mic_size=36, on_click=self.handle_mic_click)

        sidebar_icons = TopToolbar(left_items=[
            ft.IconButton(icon=ft.Icons.FILE_OPEN, icon_color="#858585", highlight_color="#D4D4D4", on_click=self.create_and_open_new_markdown),
            ft.IconButton(icon=ft.Icons.FOLDER, icon_color="#858585", highlight_color="#D4D4D4", on_click=self.create_new_dir),
            ],
            vertical_padding=5
        )
                

        self.file_tree_column = ft.Column(
            controls=intial_tree_controls,
            spacing=2,
            scroll=ft.ScrollMode.AUTO,
            expand=True
        )

        routes_menu = self.routes_menu()

        sidebar = ft.Container(
            width=250,
            bgcolor="#181818",
            content=ft.Column(
                controls=[
                    ft.Container(
                        padding=ft.padding.symmetric(horizontal=5), 
                        expand=True, 
                        content=ft.Column(
                            controls=[
                                sidebar_icons,
                                self.file_tree_column,                                
                            ]
                        )
                    ),
                    ft.Container(
                        border=ft.border.only(top=ft.border.BorderSide(width=1, color="#055b5f")),
                        content=ft.Column(
                                    spacing=2, 
                                    horizontal_alignment=ft.CrossAxisAlignment.START, 
                                    controls=[
                                        ft.IconButton(icon=ft.Icons.ARROW_BACK, icon_color="#858585", on_click=lambda e: self.route_to_main_menu(self.page)), 
                                        ft.Text("Back", size=16, color="#858585")
                                    ]
                            )
                        ),
                    routes_menu 
                ]
            )
        )

        self.dragabble_sidebar = ft.DragTarget(group="folder", content=sidebar, on_accept=lambda e: self.handler.move_file_on_drop(e, path, self.refresh_sidebar))

        self.dir_name = ft.Column(
            spacing=20,
            controls=[ft.Text("Create new file (ctrl + p)", size=14, weight="bold", color="#055b5f", selectable=True, on_tap=self.create_and_open_new_markdown), 
                    ft.Text("Open recent file (ctrl + n)", size=14, weight="bold", color="#055b5f",selectable=True, on_tap=lambda e: print("Open Recent"))])
        

        self.main_area_topbar = TopToolbar(left_items=[ft.IconButton(icon=ft.Icons.ARROW_BACK, icon_color="#858585"),
                                                  ft.IconButton(icon=ft.Icons.ARROW_FORWARD, icon_color="#858585"),],
                                      central_items=[ft.Text(self.open_file_path, color="#42A5F5", size=14, weight=ft.FontWeight.W_500)], 
                                      bgcolor="#191919")


        self.main_area = ft.Container(
                expand=6,
                bgcolor="#191919",
                content=ft.Column(
                    alignment=ft.MainAxisAlignment.START,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=0,
                    controls=[
                        self.main_area_topbar,
                        ft.Container(
                        content=ft.Column(
                            controls=[
                                self.dir_name,
                                self.new_message,
                            ],
                            alignment=ft.MainAxisAlignment.CENTER, 
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        expand=True, 
                    )
                    ]
                )
        )

        side_layout = ft.Row(
            controls=[
                self.dragabble_sidebar,
                ft.VerticalDivider(width=1, color="#055b5f"),
                self.main_area,
                ft.VerticalDivider(width=0.5, color="#055b5f"),
            ],
            expand=True,
            spacing=0
        )

        top_bar = TopToolbar(
            left_items=[
            ft.Text("Voice Writter", color="#42A5F5", size=14, weight=ft.FontWeight.W_500)
            ],

            right_items=[
                ft.IconButton(icon=ft.Icons.LINK, icon_color="#858585", tooltip="Copiar Link"),
                ft.IconButton(icon=ft.Icons.FORMAT_QUOTE, icon_color="#858585", tooltip="Citar"),
                ft.IconButton(icon=ft.Icons.SAVE, icon_color="#858585", tooltip="Salvar"),
                ft.IconButton(icon=ft.Icons.SETTINGS, icon_color="#858585", tooltip="Configurações"),
                ft.IconButton(icon=ft.Icons.MORE_VERT, icon_color="#858585", tooltip="Mais Opções"),
            ],
            bgcolor="#1c1c1c"
        )

        self.home_layout = ft.Column(
            controls=[
                top_bar,
                ft.Divider(height=1, color="#055b5f"),
                side_layout
            ],
            expand=True,
            spacing=0
        )
        
        return self.home_layout
    

