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

## Configuração do `.env`

Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis. **Nunca commite este arquivo.**

```env
SUPABASE_URL=<url do projeto>
SUPABASE_KEY=<chave anon>
MEMBER_NAME=<seu nome>
```

> Peça as credenciais ao Saraiva.

---

## Opção 1 — Windows sem Docker (execução nativa)

Use este caminho quando quiser rodar diretamente no Windows, sem container. O microfone e a janela funcionam nativamente — nenhuma configuração extra de áudio ou display é necessária.

### Pré-requisitos

- Python 3.10+
- Driver NVIDIA com suporte a CUDA 12.x (para o faster-whisper)
- [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) — necessário para compilar o PyAudio

### Passos

1. Clone o repositório:
   ```powershell
   git clone <url-do-repositório>
   cd VoiceWriter
   ```

2. Crie e ative o ambiente virtual:
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. Instale o PyTorch com suporte a CUDA **antes** dos demais pacotes:
   ```powershell
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
   ```

4. Instale as dependências do projeto:
   ```powershell
   pip install -r requirements.txt
   ```

5. Configure o `.env` conforme a seção acima.

6. Inicie a aplicação:
   ```powershell
   python main.py
   ```

### Argumentos opcionais

| Argumento     | Descrição                                             |
|---------------|-------------------------------------------------------|
| `--editor`    | Abre o editor diretamente no último projeto utilizado |
| `--main_menu` | Abre o menu principal de seleção de projeto           |

```powershell
python main.py --editor
python main.py --main_menu
```

### Empacotar em executável

```powershell
flet pack main.py --name "VoiceWriter"
```

---

## Opção 2 — Docker no Windows

Use este caminho quando quiser rodar dentro de um container Linux no Windows. Requer dois serviços auxiliares no host para encaminhar vídeo e áudio ao container.

### Pré-requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) com WSL2
- [VcXsrv](https://sourceforge.net/projects/vcxsrv/) — servidor X11 para exibir a janela do Flet
- [PulseAudio para Windows](https://github.com/pgaskin/pulseaudio-win32) — para encaminhar o microfone ao container

### Configuração única (primeira vez)

**VcXsrv:**
1. Abra o **XLaunch** no menu Iniciar
2. Selecione "Multiple windows", display number `0`, clique em Next
3. Selecione "Start no client", clique em Next
4. Marque **"Disable access control"** e clique em Finish
5. Permita o acesso no Firewall do Windows quando solicitado

**PulseAudio:**

Edite `C:\Program Files (x86)\PulseAudio\etc\pulse\default.pa` como administrador e comente a linha do módulo Unix (não funciona no Windows):
```
#load-module module-native-protocol-unix
```

Adicione ao final do mesmo arquivo:
```
load-module module-native-protocol-tcp auth-ip-acl=127.0.0.1;172.16.0.0/12 auth-anonymous=1
```

Edite `daemon.conf` no mesmo diretório e descomente:
```
exit-idle-time = -1
```

### Iniciando

A cada sessão, execute na ordem:

```powershell
# 1. Inicie o XLaunch (ícone na bandeja ou pelo menu Iniciar)

# 2. Inicie o PulseAudio em segundo plano
Start-Process -WindowStyle Hidden "C:\Program Files (x86)\PulseAudio\bin\pulseaudio.exe"

# 3. Suba o container
docker compose up
```

---

## Opção 3 — Docker no Linux

Use este caminho para rodar dentro de um container em uma máquina Linux com GPU NVIDIA.

### Pré-requisitos

- Docker + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
- PulseAudio rodando no host
- Servidor X11 (já presente em desktops Linux com GUI)

### Iniciando

A cada sessão, execute na ordem:

```bash
# 1. Permita que containers conectem ao servidor X11 do host
xhost +local:docker

# 2. Crie o socket de áudio PulseAudio para o container
pactl load-module module-native-protocol-unix socket=/tmp/pulse-docker.sock auth-anonymous=1

# 3. Suba o container com os overrides do Linux
docker compose -f docker-compose.yml -f docker-compose.linux.yml up
```

---

## Estrutura do projeto

```
VoiceWriter/
├── main.py                    # Ponto de entrada da aplicação
├── requirements.txt
├── docker-compose.yml         # Configuração Docker (padrão Windows)
├── docker-compose.linux.yml   # Overrides Docker para Linux
├── frontend/
│   ├── speech_menu.py         # Tela de comandos de voz
│   ├── main_menu.py           # Menu de seleção/criação de vault
│   ├── editor_menu.py         # Editor de arquivos Markdown
│   ├── widgets/
│   │   ├── mic.py             # Widget do microfone
│   │   ├── toolbar.py         # Barra de ferramentas
│   │   ├── tiles_generic.py   # Tiles de arquivo/pasta
│   │   ├── containers_generic.py
│   │   └── context_menu.py    # Menu de contexto (renomear, deletar)
│   └── utils/
│       ├── file_handler.py    # Operações de arquivo e pasta
│       ├── recent_manager.py  # Gerenciamento de projetos recentes
│       ├── animation.py       # Animações de UI
│       └── color.py           # Utilitários de cor
└── voice/
    ├── speech.py              # Captura de áudio e transcrição (Whisper)
    ├── interact_app.py        # Interpretação e execução de comandos de voz
    ├── type_at_cursor.py      # Modo de ditado para qualquer aplicativo
    └── utils/
        ├── json_utils.py      # Salvamento de logs de transcrição
        ├── asr_metrics.py     # Métricas de qualidade da transcrição
        └── metrics_storage.py # Persistência de métricas (local e nuvem)
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
| `pyautogui`         | Injeção de teclado (type at cursor)      |
| `send2trash`        | Exclusão segura de arquivos              |
