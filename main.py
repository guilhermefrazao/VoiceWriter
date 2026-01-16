import flet as ft
import os
import subprocess
import platform

from interface import writer
from widgets.containers_generic import Containers

def fade(switcher, c1, c2):
    switcher.content = c2 if switcher.content == c1 else c1
    switcher.transition = ft.AnimatedSwitcherTransition.FADE
    switcher.update()     


def create_and_open_new_vault(page: ft.Page, path: str):
    print(path)

    if not os.path.dirname(path):
        os.makedirs(path)

    page.clean()

    writer(page, path)

def open_explorer(path):
    print("path", os.path.abspath(path))
    print(platform.system())

    """Opens the file explorer in the specified path based on the operating system."""
    if platform.system() == "Windows":
        subprocess.run(f'explorer "{os.path.abspath(path)}"', shell=True)
    elif platform.system() == "Darwin":
        subprocess.run(['open', os.path.abspath(path)])
    elif platform.system() == "Linux":
        try:
            subprocess.run(['xdg-open', os.path.abspath(path)])
        except FileNotFoundError:
            subprocess.run(['nautilus', os.path.abspath(path)])
    else:
        print(f"Unsupported operating system: {platform.system()}")
    

def main(page: ft.Page):
    page.padding = 0
    page.title = "Voice Writter"
    page.theme_mode = ft.ThemeMode.DARK

    directory_container = ft.Container(
        bgcolor="#202020",
        padding=10,
        border=ft.Border.only(right=ft.border.BorderSide(1, "#0C5F49"), top=ft.border.BorderSide(1, "#0C5F49")),
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

    options_container_1 = ft.Column(
        spacing=10,
        controls=[
            Containers().generic_text_container_with_right_button("Create new vault", "Create a new vault under a folder.", "Create", lambda e : fade(animation_switcher, options_container_1, options_container_2)),
            Containers().generic_text_container_with_right_button("Open a Folder", "Open Folder with files.", "Open", lambda e : open_explorer(os.getcwd()))
            ]
        )     
    
    text_container, text_field_path = Containers().generic_text_container_with_right_text_field("Vault name", "Pick a name to gain Aura.", "Aura name")

    options_container_2 = ft.Column(
        spacing=10,
        controls=[
            ft.Column(spacing=2, horizontal_alignment=ft.CrossAxisAlignment.START, controls=[ft.IconButton(icon=ft.Icons.ARROW_BACK, icon_color="white", on_click=lambda e: fade(animation_switcher, options_container_1, options_container_2)), ft.Text("Back", size=16, color="grey")]),
            text_container,
            Containers().generic_text_container_with_right_button("Location", "Pick a place to create the Aura + Ego", "Browse", lambda e : open_explorer(os.getcwd())),
            ft.Button(content="Create", color="#028268", height=40,style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)), on_click=lambda e: create_and_open_new_vault(page, text_field_path))
            ]
        )

    animation_switcher = ft.AnimatedSwitcher(
        content=options_container_1,
        transition=ft.AnimatedSwitcherTransition.FADE,
        duration=500,
        reverse_duration=100,
        switch_in_curve=ft.AnimationCurve.BOUNCE_OUT,
        switch_out_curve=ft.AnimationCurve.BOUNCE_IN,
    )  

    main_container = ft.Container(
        bgcolor="#11111",
        padding=20,
        border=ft.Border.only(top=ft.border.BorderSide(1, "#0C5F49")),
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=15,
            controls=[ft.Image(src="images/Aura.webp", width=100, height=100),
                    ft.Text(value="VoiceWritter", size=30, weight="bold"),
                    animation_switcher,
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

