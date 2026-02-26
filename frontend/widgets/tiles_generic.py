import flet as ft
from frontend.utils.file_handler import DirectoryUtils

class Tiles():
    def __init__(self):
        self.handler = DirectoryUtils()
        self.expanded_folders = set()


    def generic_expand_tile(self, item: str, full_path: str, recursive_func, refresh_sidebar) -> tuple[ft.DragTarget, ft.ExpansionTile]:
        tile = ft.ExpansionTile(
                                title = ft.Text(item, size=14, color="#858585", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, tooltip=item),
                                leading=ft.Icon(ft.Icons.KEYBOARD_ARROW_RIGHT, size=12, color="#858585"),
                                animation_style=ft.AnimationStyle(duration=20, reverse_duration=20),
                                affinity=ft.TileAffinity.LEADING,
                                collapsed_shape=ft.RoundedRectangleBorder(),
                                shape=ft.RoundedRectangleBorder(),
                                tile_padding=ft.Padding.symmetric(horizontal=10, vertical=0),
                                data=full_path,
                                controls_padding=ft.Padding.only(left=20),
                                expanded=(full_path in self.expanded_folders),
                                controls=[
                                    ft.Container(
                                        border=ft.Border.only(left=ft.BorderSide(1, "#0C5F49")),
                                        padding=ft.Padding.only(left=10),
                                        content=ft.Column(controls=recursive_func(full_path), spacing=0)
                                        )
                                    ],
                                on_change=lambda e: self.handler.handle_tile_change(e, self.expanded_folders),
                            )
        
        wrapper = ft.DragTarget(
            group="folder",
            content=self.handler.make_draggable(tile, full_path, "folder"),
            on_accept=lambda e: self.handler.move_file_on_drop(e, full_path, refresh_sidebar)
        )
    
        return wrapper, tile
    

    def generic_list_tile(self, item: str, full_path: str, refresh_sidebar, on_file_open) -> tuple[ft.DragTarget, ft.ListTile]:
        tile = ft.ListTile(
                            title=ft.Text(item, size=14, color="#858585", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, tooltip=item),
                            height=50,
                            content_padding=ft.Padding.symmetric(horizontal=10, vertical=0),
                            hover_color="black",
                            data=full_path,
                            is_three_line=False,
                            on_click=lambda e: self.handler.on_file_selected(e, on_file_open)
                        )         
        
        wrapper = ft.DragTarget(
            group="files",
            content=self.handler.make_draggable(tile, full_path, "files"),
            on_accept=lambda e: self.handler.move_file_on_drop(e, full_path, refresh_sidebar)
        )
        
        return wrapper, tile