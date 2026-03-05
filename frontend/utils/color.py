import flet as ft
import asyncio

def hover_color_change(e, color="#333333"):
        if e.data == True:
            e.control.bgcolor = color
        else:
            e.control.bgcolor = ft.Colors.TRANSPARENT

        e.control.update()



