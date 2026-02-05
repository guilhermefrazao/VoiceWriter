import flet as ft

def hover_color_change(e):
        if e.data == True:
            e.control.bgcolor = "#333333"
        else:
            e.control.bgcolor = ft.Colors.TRANSPARENT

        e.control.update()