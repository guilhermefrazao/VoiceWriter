import flet as ft

from frontend.utils.color import hover_color_change


class Containers():
    def __init__(self):
        pass

    def generic_text_container_with_right_context_menu(self, text_1, text_2):
        text = ft.Column(
            spacing=2,
            controls=[
                    ft.Text(text_1, size=16, color="white"),
                    ft.Text(text_2, size=14, color="grey"),
                    ]
        )

        control_menu = ft.PopupMenuButton(
            icon=ft.icons.Icons.MORE_VERT,
            icon_color="white",
            tooltip="Options",
            items=[
                ft.PopupMenuItem(
                    content="Editar", 
                    on_click=lambda e: print(f"Editar {text_1}") 
                ),
                ft.PopupMenuItem(
                    content="Deletar", 
                    on_click=lambda e: print(f"Deletar {text_1}")
                ),
                ft.PopupMenuItem(content="Cancelar")
            ]
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
            on_hover=lambda e: hover_color_change(e)
        )

        return container
    

    def generic_text_container_with_right_button(self, text_1, text_2, text_button, on_click_event, data=True):
        text = ft.Column(
            spacing=2,
            controls=[
                    ft.Text(text_1, size=16, color="white"),
                    ft.Text(text_2, size=12, color="grey"),]
            )
    
        button = ft.Button(
            content=text_button,
            color="#028268",
            height=40,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8)
            ),
            data=data,
            on_click=on_click_event
        )

        container = ft.Container(
            bgcolor="#032C21",
            padding=20,
            border_radius=10,
            width=600,
            alignment=ft.Alignment.CENTER,
            content=ft.Row(
                controls=[text, button],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            )
        )

        return container
    

    def generic_text_container_with_right_text_field(self, text_right_up, text_right_down, text_field):
        text = ft.Column(
            spacing=2,
            controls=[
                    ft.Text(text_right_up, size=16, color="white"),
                    ft.Text(text_right_down, size=12, color="grey"),]
            )
    
        text_field = ft.TextField(
            label= text_field,
            border=ft.InputBorder.NONE,
            cursor_color="white",
            color="white",
            filled=True,
            text_size=16,
            multiline=False,
            autofocus=True
        )

        container = ft.Container(
            bgcolor="#032C21",
            padding=20,
            border_radius=10,
            width=600,
            alignment=ft.Alignment.CENTER,
            content=ft.Row(
                controls=[text, text_field],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            )
        )

        return container    