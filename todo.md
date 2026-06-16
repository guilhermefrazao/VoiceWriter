1 - Diminuir o tempo para começar o reconhecimento da fala, após clicar no botão de gravação. (tanto com animação visual quanto com o reconhecimento de voz em si, principalmente na primeira execução)

2 - Melhorar o reconhecimento de comandos principalmente para aplicativos com nomes em inglês (Como "Google Chrome", "Visual Studio Code", etc.) e também para comandos de navegação (como "abrir nova aba", "fechar janela", etc.)

3 - Implementar uma feature com Wakeword caso a aplicação esteja rodando em background ou com comandos no teclado (F9), para que o usuário possa ativar o reconhecimento de voz sem precisar clicar no botão de gravação. (ex: "Hey Voice Control, abrir Google Chrome")

4 - Expandir o reconhecimento de comandos para mais aplicativos e ações, como por exemplo além de abrir o e fechar aplicativos, conseguir interagir com eles.

5 - Melhorar a feature de transcrição de fala em tempo real, ou seja, enquanto a pessoa fala, o texto já vai aparecendo na tela no modo de editor. (atualmente é feito em batches de fala.)

6 - Formatação de Markdown utilizando voz. (ex: "hastag", "aspas", "asteriscos", etc.)

7 - Testar diferentes modelos de ASR dentro da arquitetura, atualmente feita com o Whisper, testar também desempenho dos modelos Whisper (Modelo como Parakeet para Pt-BR).

8 - Criar e Avaliar variáveis para diferentes modelos de ASR. (success_rate, WER, Latency, etc.) (na transcrição de comandos e de texto em geral)

9 - Implementar uma feature de transcrição de fala para onde o cursor do mouse estiver posicionado, para facilitar a edição de texto.




