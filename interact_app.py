import webbrowser
import subprocess


def open_browser():
    webbrowser.open("https://www.google.com")


def open_app(app_name: str):
    subprocess.Popen(app_name)







