import flet as ft
import os



def get_directory_tree(path):
    controls = []

    try:
        items = sorted(os.listdir(path), key=lambda x: (not os.path.isdir(os.path.join(path, x), x)))

        for item in items:
            full_path = os.path.join(path, item)

            if os.path.isdir(full_path):
                controls.append(
                    ft.ExpansionTile(
                        title = ft.Text(item, size=14),
                        leading=ft.Icon(ft.icons.FOLDER, size=16),
                        text_color="white",
                        controls_padding=15,
                        controls=get_directory_tree(full_path)

                    ))
            else:
                if item.endswith(".md"):
                    controls.append(
                        ft.ListTile(
                            title=ft.Text(item, size=14),
                            leading=ft.Icon(ft.icons.INSERT_DRIVE_FILE, size=14),
                            height=30,
                            on_click=lambda e, p=full_path: print(f"Abrir arquivo: {p}")
                        )
                    )
    
    except Exception as e:
        print(f"Exception occured {e} with {path}")

    return controls


def refresh_sidebar(sidebar, path):
    sidebar.controls = get_directory_tree(path)
    sidebar.update()


def writer(page: ft.Page, path: str):
    page.padding = 0
    page.title = "Editor - Voice Writter"
    page.theme_mode = ft.ThemeMode.DARK

    new_message = ft.TextField(
        border=ft.InputBorder.NONE,
        always_call_on_tap=False,
        animate_cursor_opacity=True,
        multiline=True,
        text_size=16,
        autocorrect=True,
        expand=True,
        autofocus=True
    )

    topbar = ft.Container(
        width=float("inf"),
        bgcolor="#202020",
        padding=10,
        content=ft.Row(
            controls=[
                ft.Text("Texting Upbar", size=12, weight="bold", color="grey")
            ],
        ),
    )

    sidebar_buttons = ft.Row(
        controls=[
            ft.IconButton(icon=ft.Icons.PASTE, icon_color="grey", highlight_color="white"),
            ft.IconButton(icon=ft.Icons.FOLDER, icon_color="grey", highlight_color="white"),
        ]
    )

    sidebar = ft.Container(
        width=250,
        bgcolor="#202020",
        padding=10,
        content=ft.Column(
            controls=[
                sidebar_buttons,
                ft.Text("Explorer", size=12, weight="bold", color="grey")
            ]
        )
    )

    main_area = ft.Container(
            expand=True,
            bgcolor="#11111",
            padding=20,
            content=ft.Column(
                controls=[
                    ft.Text("Idea app.md", size=30, weight="bold"),
                    new_message
                ]
            )
    )

    side_layout = ft.Row(
        controls=[
            sidebar,
            ft.VerticalDivider(width=1, color="grey"),
            main_area
        ],
        expand=True,
        spacing=0
    )

    home_layout = ft.Column(
        controls=[
            topbar,
            ft.Divider(height=1, color="grey"),
            side_layout
        ],
        expand=True,
        spacing=0
    )
    
    page.add(
        home_layout
    )
