import flet as ft

from frontend.utils.dir import DirectoryUtils

class Tiles():
    def __init__(self):
        self.selected_tile = None
        self.dir = DirectoryUtils()
        pass

    def _handle_tile_change(self, e: ft.Event[ft.ExpansionTile]):
        self._on_file_click(e)
        e.control.leading.icon = (
            ft.Icons.KEYBOARD_ARROW_RIGHT   
            if e.control.leading.icon == ft.Icons.KEYBOARD_ARROW_DOWN  
            else ft.Icons.KEYBOARD_ARROW_DOWN
        )
        e.page.update()


    def _on_file_click(self, e: ft.Event[ft.ExpansionTile]):
        if isinstance(e.control, ft.ExpansionTile):
            return 

        
        if self.selected_tile == e.control:
            e.control.shape = ft.RoundedRectangleBorder(side=ft.BorderSide(width=1,  color="white"), radius=5)
            e.control.update()
            return 

        
        if self.selected_tile:
            self.selected_tile.bgcolor = ft.Colors.TRANSPARENT
            self.selected_tile.shape = None
            self.selected_tile.update()
            self.dir.display_markdown_information()
            
        e.control.bgcolor = "#37373d"
        e.control.shape = None
        e.control.update()

        self.selected_tile = e.control


    def generic_expand_tile(self, item: str, full_path: str, recursive_func) -> ft.ExpansionTile:
        return ft.ExpansionTile(
                            title = ft.Text(item, size=14, color="#A4A5A5", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, tooltip=item),
                            leading=ft.Icon(ft.Icons.KEYBOARD_ARROW_RIGHT, size=12, color="grey"),
                            animation_style=ft.AnimationStyle(duration=20, reverse_duration=20),
                            affinity=ft.TileAffinity.LEADING,
                            collapsed_shape=ft.RoundedRectangleBorder(),
                            shape=ft.RoundedRectangleBorder(),
                            tile_padding=ft.Padding.symmetric(horizontal=10, vertical=0),
                            data=full_path,
                            controls_padding=ft.Padding.only(left=20),
                            controls=[
                                ft.Container(
                                    border=ft.Border.only(left=ft.BorderSide(1, "#0C5F49")),
                                    padding=ft.Padding.only(left=10),
                                    content=ft.Column(controls=recursive_func(full_path),spacing=0)
                                    )
                                ],
                            on_change=self._handle_tile_change,
                        )
    
    def generic_list_tile(self, item: str, full_path: str) -> ft.ListTile:
        return ft.ListTile(
                            title=ft.Text(item, size=14, color="grey", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, tooltip=item),
                            height=50,
                            content_padding=ft.Padding.symmetric(horizontal=10, vertical=0),
                            hover_color="black",
                            data=full_path,
                            is_three_line=False,
                            on_click=lambda e: self._on_file_click(e)
                        )