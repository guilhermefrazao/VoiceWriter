import flet as ft

from interface import writer
from widgets.containers_generic import Containers

def main(page: ft.Page):
    page.padding = 0
    page.title = "Voice Writter"
    page.theme_mode = ft.ThemeMode.DARK

    directory_container = ft.Container(
        bgcolor="#202020",
        padding=10,
        content=ft.Column(
            spacing=5,
            controls=[
                    Containers().generic_text_container_with_right_context_menu("Folder_name_1", "Folder_path_1"),
                    Containers().generic_text_container_with_right_context_menu("Folder_name_2", "Folder_path_2"),
                    Containers().generic_text_container_with_right_context_menu("Folder_name_3", "Folder_path_3"),
                    Containers().generic_text_container_with_right_context_menu("Folder_name_4", "Folder_path_4"),
                    ]
        ),
        expand=True
    )

    main_container = ft.Container(
        bgcolor="#11111",
        padding=20,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            controls=[ft.Image(src="images/Aura.webp", width=100, height=100),
                    ft.Text(value="VoiceWritter", size=30, weight="bold"),
                    Containers().generic_text_container_with_right_button("Create new vault", "Create a new Obsidian vault under a folder.", lambda e : writer(page))
                    ]
        ),
        expand=True
    )

    home_menu = ft.Row(
        controls=[
            directory_container,
            main_container
        ],
        expand=True,
        spacing=0,
        vertical_alignment=ft.CrossAxisAlignment.STRETCH

    )

    page.add(
        home_menu
    )


if __name__ == "__main__":
    ft.run(main)

