# VoiceWriter

VoiceWriter é uma aplicação desktop que combina reconhecimento de voz com um editor de texto Markdown. Com ela, você pode ditar texto por voz diretamente no editor, além de executar comandos de voz para controlar o computador — como abrir e fechar programas ou desligar o sistema.

A interface foi construída com [Flet](https://flet.dev/) e o reconhecimento de voz utiliza o modelo [Whisper](https://github.com/openai/whisper) via [faster-whisper](https://github.com/SYSTRAN/faster-whisper), com suporte a GPU via CUDA.

---

## Funcionalidades

- **Ditado por voz**: Clique no microfone dentro do editor e fale — o texto reconhecido é inserido automaticamente no arquivo aberto.
- **Comandos de voz**: Na tela inicial, use a voz para:
  - Abrir aplicativos (`"abra o Chrome"`, `"execute o Spotify"`)
  - Fechar aplicativos (`"feche o Notepad"`)
  - Desligar o computador (`"desligue o PC"`)
- **Editor Markdown**: Navegue por pastas, abra, crie e renomeie arquivos `.md`.
- **Vaults**: Crie "vaults" (pastas de projetos) e acesse rapidamente os mais recentes.
- **Atalhos de teclado**:
  - `F8` — Ativa o microfone na tela atual
  - `F9` — Abre/fecha o painel flutuante do microfone
  - `Ctrl + P` — Cria um novo arquivo Markdown
  - `Ctrl + N` — Cria uma nova pasta

---

## Pré-requisitos

- Python 3.10+
- GPU com suporte a CUDA (recomendado para melhor desempenho do Whisper)
- Microfone configurado no sistema

---

## Instalação

1. Clone o repositório:
   ```bash
   git clone <url-do-repositório>
   cd VoiceWriter
   ```

2. Crie e ative o ambiente virtual:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   ```

3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

---

## Como usar

### Iniciando a aplicação

```bash
python main.py
```

Por padrão, a aplicação abre na **tela de comandos de voz**.

### Argumentos opcionais

| Argumento       | Descrição                                              |
|-----------------|--------------------------------------------------------|
| `--editor`      | Abre o editor diretamente no último projeto utilizado  |
| `--main_menu`   | Abre o menu principal de seleção de projeto            |

Exemplo:
```bash
python main.py --editor
python main.py --main_menu
```

---

## Estrutura do projeto

```
VoiceWriter/
├── main.py                  # Ponto de entrada da aplicação
├── requirements.txt
├── frontend/
│   ├── speech_menu.py       # Tela de comandos de voz
│   ├── main_menu.py         # Menu de seleção/criação de vault
│   ├── editor_menu.py       # Editor de arquivos Markdown
│   ├── widgets/
│   │   ├── mic.py           # Widget do microfone
│   │   ├── toolbar.py       # Barra de ferramentas
│   │   ├── tiles_generic.py # Tiles de arquivo/pasta
│   │   ├── containers_generic.py
│   │   └── context_menu.py  # Menu de contexto (renomear, deletar)
│   └── utils/
│       ├── file_handler.py  # Operações de arquivo e pasta
│       ├── recent_manager.py# Gerenciamento de projetos recentes
│       ├── animation.py     # Animações de UI
│       └── color.py         # Utilitários de cor
└── voice/
    ├── speech.py            # Captura de áudio e transcrição (Whisper)
    ├── interact_app.py      # Interpretação e execução de comandos de voz
    └── utils/
        └── json_utils.py    # Salvamento de logs de transcrição
```

---

## Dependências principais

| Pacote              | Uso                                      |
|---------------------|------------------------------------------|
| `flet`              | Interface gráfica desktop                |
| `faster-whisper`    | Transcrição de voz (modelo Whisper)      |
| `speechrecognition` | Captura de áudio do microfone            |
| `pyaudio`           | Backend de áudio                         |
| `appopener`         | Abertura/fechamento de aplicativos       |
| `keyboard`          | Atalhos globais de teclado               |
| `send2trash`        | Exclusão segura de arquivos              |
