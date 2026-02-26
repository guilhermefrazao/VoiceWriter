Essenciais antes da transcrição:
#TODO: Adaptar o TextInput para aceitar o formato markdown (negrito, itálico, listas, etc).
#TODO: Corrigir a seleção dos arquivos e tiles da sidebar.
#TODO: Não permitir que seja aberto um diretório imenso.

Estilo:
#TODO: Ligar markdowns abertos à barra superior para facilitar a navegação e deleção.


Erros:

2 - 026-02-09 19:13:52,947 | INFO | Manager: C:\Users\guilh\Documents\Obsidian Vault\Ideias_Pessoais\Games
2026-02-09 19:14:18,389 | ERROR | Unhandled error in 'on_click' handler
Traceback (most recent call last):
  File "C:\Users\guilh\Documents\VoiceWriter\.venv\Lib\site-packages\flet\messaging\session.py", line 194, in dispatch_event
    await control._trigger_event(event_name, event_data)
  File "C:\Users\guilh\Documents\VoiceWriter\.venv\Lib\site-packages\flet\controls\base_control.py", line 344, in _trigger_event
    event_handler(e)
    ~~~~~~~~~~~~~^^^
  File "C:\Users\guilh\Documents\VoiceWriter\frontend\widgets\tiles_generic.py", line 75, in <lambda>
    on_click=lambda e: self._on_file_selected(e)
                       ~~~~~~~~~~~~~~~~~~~^^^
  File "C:\Users\guilh\Documents\VoiceWriter\frontend\widgets\tiles_generic.py", line 32, in _on_file_selected
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