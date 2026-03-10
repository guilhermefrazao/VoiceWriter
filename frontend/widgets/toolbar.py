import flet as ft 

class TopToolbar(ft.Container):
    def __init__(self, left_items=None, central_items=None, right_items=None, bgcolor="#181818", vertical_padding=0):
        super().__init__()
        self.bgcolor = bgcolor
        self.height = 40
        self.padding = ft.padding.symmetric(horizontal=5, vertical=vertical_padding)
        self.border_radius = ft.border_radius.only(top_left=10, top_right=10)
        
        left_items = left_items or []
        right_items = right_items or []

        self.content = ft.Row(
            controls=[
                ft.Row(controls=left_items, spacing=5, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row(controls=central_items, spacing=5, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row(controls=right_items, spacing=5, vertical_alignment=ft.CrossAxisAlignment.CENTER)
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )
