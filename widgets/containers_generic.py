import flet as ft

class Containers():
    def __init__(self):
        self.self = self

    def hover_color_change(self, e):
        print(e.data)
        if e.data == True:
            e.control.bgcolor = "#333333"
        else:
            e.control.bgcolor = ft.Colors.TRANSPARENT

        e.control.update()

    def generic_text_container_with_right_context_menu(self, text_1, text_2):
        text = ft.Column(
            spacing=2,
            controls=[
                    ft.Text(text_1, size=16, weight="bold", color="white"),
                    ft.Text(text_2, size=14, color="grey"),
                    ]
        )

        control_menu = ft.Button(
            content="Create",
            color="#028268",
            height=40,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8)
            ),
            on_click=lambda e: print("Botão funcionando")
        )

        container = ft.Container(
            bgcolor= ft.Colors.TRANSPARENT,
            padding=10,
            animate = ft.Animation(100, ft.AnimationCurve.EASE_OUT),
            alignment=ft.Alignment.TOP_LEFT,
            content=ft.Row(
                controls=[text, control_menu],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            ),
            on_hover=lambda e: self.hover_color_change(e)
        )

        return container
    

    def generic_text_container_with_right_button(self, text_1, text_2, on_click_event):
        text = ft.Column(
            spacing=2,
            controls=[
                    ft.Text(text_1, size=16, weight="bold", color="white"),
                    ft.Text(text_2, size=12, color="grey"),]
            )
    
        button = ft.Button(
            content="Create",
            color="#028268",
            height=40,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8)
            ),
            on_click=on_click_event
        )

        container = ft.Container(
            bgcolor="#0C5F49",
            padding=20,
            border_radius=10,
            width=400,
            alignment=ft.Alignment.CENTER,
            content=ft.Row(
                controls=[text, button],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            )
        )

        return container