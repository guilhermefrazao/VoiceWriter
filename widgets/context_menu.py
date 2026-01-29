import flet as ft

class ContextMenu():
    def __init__(self):
        self.context_menu = ft.Container(
            visible=False,
            width=150,
            bgcolor="#252526",
            border=ft.border.all(1, "#454545"),
            border_radius=5,
            padding=5,
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.BLACK),
            content=ft.Column(
                spacing=0,
                controls=[
                    self.create_menu_item("Renomear", ft.Icons.EDIT, self.action_rename),
                    self.create_menu_item("Deletar", ft.Icons.DELETE, self.action_delete),
                    ft.Divider(height=1, color="grey"),
                    self.create_menu_item("Propriedades", ft.Icons.INFO, self.action_info),
                ]
            ),
        )

       

    def create_menu_item(self, text, icon, func):
        return ft.Container(
            padding=10,
            on_click=func,
            on_hover=lambda e: self.highlight_menu_item(e),
            content=ft.Row([
                ft.Icon(icon, size=16, color="white"),
                ft.Text(text, size=14, color="white")
            ])
        )


    def highlight_menu_item(self, e):
        e.control.bgcolor = "#094771" if e.data == "true" else ft.Colors.TRANSPARENT
        e.control.update()


    async def show_context_menu(self, e: ft.TapEvent[ft.GestureDetector], menu: ft.ContextMenu, is_folder: bool):
        await menu.open(
            local_position=e.local_position,
            global_position=e.global_position
        )


    def close_context_menu(self, e=None):
        if self.context_menu.visible:
            self.context_menu.visible = False
            self.context_menu.update()

    
    def action_rename(self):
        pass
    
    
    def action_delete(self):
        pass
    
    
    def action_info(self):
        pass