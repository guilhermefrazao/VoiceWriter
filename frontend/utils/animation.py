import flet as ft

class AnimationUtils():
    def __init__(self):
        pass

    def fade(self, switcher: ft.AnimatedSwitcher, c1: ft.Column, c2: ft.Column):
        switcher.content = c2 if switcher.content == c1 else c1
        switcher.transition = ft.AnimatedSwitcherTransition.FADE
        switcher.update()  