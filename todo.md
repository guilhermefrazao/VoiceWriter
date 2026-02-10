Essenciais antes da transcrição:
#TODO: Fazer o botão de criar no segundo menu do main menu ser clicável somente após escolher o caminho.
#TODO: Corrigir o bug em que o Menu de contexto não abre caso o botão tenha sido clicado.
#TODO: Adaptar o TextInput para aceitar o formato markdown (negrito, itálico, listas, etc).
#TODO: Implementar o rename dentro do título do markdown.

Estilo:
#TODO: Descobrir como deixar os menus de popup mais bonitos.
#TODO: Ligar markdowns abertos à barra superior para facilitar a navegação e deleção.


Erros:

1 - 2026-02-09 19:12:14,658 | ERROR | Task exception was never retrieved
future: <Task finished name='Task-25' coro=<ContextMenu.show_context_menu() done, defined at C:\Users\guilh\Documents\VoiceWriter\frontend\widgets\context_menu.py:13> exception=RuntimeError('Null check operator used on a null value')>
Traceback (most recent call last):
  File "C:\Users\guilh\Documents\VoiceWriter\frontend\widgets\context_menu.py", line 17, in show_context_menu
    await self.directory_column.open(
    ...<2 lines>...
    )
  File "C:\Users\guilh\Documents\VoiceWriter\.venv\Lib\site-packages\flet\controls\material\context_menu.py", line 194, in open
    await self._invoke_method(
    ...<5 lines>...
    )
  File "C:\Users\guilh\Documents\VoiceWriter\.venv\Lib\site-packages\flet\controls\base_control.py", line 270, in _invoke_method
    return await self.page.session.invoke_method(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        self._i, method_name, arguments, timeout
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "C:\Users\guilh\Documents\VoiceWriter\.venv\Lib\site-packages\flet\messaging\session.py", line 233, in invoke_method
    raise RuntimeError(err)
RuntimeError: Null check operator used on a null value

2 - 026-02-09 19:13:52,947 | INFO | Manager: C:\Users\guilh\Documents\Obsidian Vault\Ideias_Pessoais\Games
2026-02-09 19:14:18,389 | ERROR | Unhandled error in 'on_click' handler
Traceback (most recent call last):
  File "C:\Users\guilh\Documents\VoiceWriter\.venv\Lib\site-packages\flet\messaging\session.py", line 194, in dispatch_event
    await control._trigger_event(event_name, event_data)
  File "C:\Users\guilh\Documents\VoiceWriter\.venv\Lib\site-packages\flet\controls\base_control.py", line 344, in _trigger_event
    event_handler(e)
    ~~~~~~~~~~~~~^^^
  File "C:\Users\guilh\Documents\VoiceWriter\frontend\widgets\tiles_generic.py", line 75, in <lambda>
    on_click=lambda e: self._on_file_click(e)
                       ~~~~~~~~~~~~~~~~~~~^^^
  File "C:\Users\guilh\Documents\VoiceWriter\frontend\widgets\tiles_generic.py", line 32, in _on_file_click
    self.selected_tile.update()
    ~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "C:\Users\guilh\Documents\VoiceWriter\.venv\Lib\site-packages\flet\controls\base_control.py", line 253, in update
    if not self.page:
           ^^^^^^^^^
  File "C:\Users\guilh\Documents\VoiceWriter\.venv\Lib\site-packages\flet\controls\base_control.py", line 200, in page
    raise RuntimeError(
    ...<2 lines>...
    )
RuntimeError: ListTile(80) Control must be added to the page first