import flet as ft

from frontend.utils.color import hover_color_change


class Containers():
    def __init__(self):
        pass

    def generic_text_container_with_right_context_menu(self, text_1="text_1", text_2="text_2", color_1="#D4D4D4", color_2="#858585", on_click=None):
        text = ft.Column(
            spacing=2,
            expand=True,
            controls=[
                    ft.Text(text_1, size=16, color=color_1, overflow=ft.TextOverflow.ELLIPSIS, no_wrap=True),
                    ft.Text(text_2, size=14, color=color_2, overflow=ft.TextOverflow.ELLIPSIS, no_wrap=True),
                    ]
        )

        control_menu = ft.PopupMenuButton(
            icon=ft.icons.Icons.MORE_VERT,
            icon_color="#D4D4D4",
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
            on_hover=lambda e: hover_color_change(e),
            on_click=on_click
        )

        return container
    

    def generic_text_container_with_right_button(self, text_1, text_2, text_button, button_color="#028268", container_color="#123F38", on_click_event=None, data=True):
        text = ft.Column(
            spacing=2,
            controls=[
                    ft.Text(text_1, size=16, color="#D4D4D4"),
                    ft.Text(text_2, size=12, color="#858585"),]
            )
    
        button = ft.Button(
            content=text_button,
            color=button_color,
            height=40,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8)
            ),
            data=data,
            on_click=on_click_event
        )

        container = ft.Container(
            bgcolor=container_color,
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
    

    def generic_text_container_with_right_text_field(self, text_right_up, text_right_down, text_field, container_color="#00302d"):
        text = ft.Column(
            spacing=2,
            controls=[
                    ft.Text(text_right_up, size=16, color="#D4D4D4"),
                    ft.Text(text_right_down, size=12, color="#858585"),]
            )
    
        text_field = ft.TextField(
            label= text_field,
            border=ft.InputBorder.NONE,
            cursor_color="#D4D4D4",
            color="#D4D4D4",
            filled=True,
            text_size=16,
            multiline=False,
            autofocus=True
        )

        container = ft.Container(
            bgcolor=container_color,
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
    

    def generic_container_with_mic_button(self, width=100, height=100, mic_size=45, on_click=None):
        container = ft.Container(
                        content=ft.Icon(ft.Icons.MIC, size=mic_size, color="white"),
                        width=width,
                        height=height,
                        border_radius=50,
                        bgcolor="#1A1D24",
                        border=ft.border.all(2, "#028268"),
                        alignment=ft.Alignment.CENTER,
                        shadow=ft.BoxShadow(
                            blur_radius=30,
                            color=ft.Colors.with_opacity(0.15, "blue"),
                            spread_radius=1,
                        ),
                        scale=1.0,
                        animate_scale=ft.Animation(500, ft.AnimationCurve.EASE_IN_OUT),
                        animate=ft.Animation(500, ft.AnimationCurve.EASE_IN_OUT),
                        on_hover=lambda e: hover_color_change(e, color="#055b5f"),
                        on_click=lambda e: on_click(e)
                        
        )

        return container
    
    
    
