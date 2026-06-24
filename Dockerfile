# Base: CUDA 12.6 + cuDNN runtime sobre Ubuntu 24.04
# Usa CUDA 12.x porque os pacotes Python (ctranslate2, NeMo, torch wheels)
# são compilados contra CUDA 12.x e procuram libcublas.so.12 em runtime.
# Driver NVIDIA ≥ 525 suporta containers CUDA 12.x sem problema.
FROM nvidia/cuda:13.3.0-cudnn-runtime-ubuntu24.04

# ── Timezone (Brasília) ────────────────────────────────────────────────────────
ENV TZ=America/Sao_Paulo
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# ── Dependências de sistema ────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Compilação (Essencial para compilar extensões em C como o PyAudio)
    build-essential \
    # Timezone
    tzdata \
    # Python
    python3 \
    python3-pip \
    python3-dev \
    python3-venv \
    # Áudio (PyAudio / PortAudio / ALSA / PulseAudio)
    portaudio19-dev \
    libportaudio2 \
    libasound2-dev \
    alsa-utils \
    pulseaudio \
    libpulse-dev \
    # FFmpeg + libsndfile (faster-whisper, soundfile)
    ffmpeg \
    libsndfile1 \
    # GStreamer (flet[all] media support)
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-libav \
    # GTK3 / X11 para janela do Flutter/Flet
    libgtk-3-0 \
    libgtk-3-dev \
    libglib2.0-0 \
    libdbus-1-3 \
    x11-utils \
    xauth \
    libx11-6 \
    libxext6 \
    libxrender1 \
    libxrandr2 \
    libxi6 \
    libxfixes3 \
    libxcursor1 \
    libxss1 \
    libxtst6 \
    # MPV (reprodução de mídia no flet)
    libmpv-dev \
    mpv \
    # Sox: processamento de áudio interno ao NeMo
    sox \
    libsox-dev \
    libsox-fmt-all \
    # Utilitários
    git \
    curl \
    wget \
    ca-certificates \
    xdg-utils \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && dpkg-reconfigure -f noninteractive tzdata \
    && rm -rf /var/lib/apt/lists/*

# ── ALSA: redireciona todo áudio para PulseAudio ──────────────────────────────
# Sem isso, o ALSA tenta dmix/dsnoop/oss/jack/usb antes de desistir — gerando
# dezenas de linhas de erro no log toda vez que o microfone é aberto.
RUN printf 'pcm.!default { type pulse }\nctl.!default { type pulse }\n' > /etc/asound.conf

# ── cuBLAS 12.x (compatibilidade) ─────────────────────────────────────────────
# ctranslate2 (faster-whisper) e NeMo são compilados contra CUDA 12.x e buscam
# libcublas.so.12 em runtime. A imagem CUDA 13.x fornece apenas .so.13.
# Os repos NVIDIA na imagem base contêm pacotes 12.x para instalação paralela.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcublas-12-6 \
    && rm -rf /var/lib/apt/lists/*

# ── Ambiente Python isolado ────────────────────────────────────────────────────
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Instala dependências Python em camadas separadas para aproveitar o cache Docker
COPY requirements.txt .

# 1. PyTorch com CUDA 12.x — deve vir ANTES de qualquer outro pacote ML.
#    Garante que openai-whisper, NeMo e transformers usem a versão GPU,
#    não a versão CPU que o PyPI instala por padrão.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        torch torchvision torchaudio \
        --index-url https://download.pytorch.org/whl/cu121

# 2. NeMo ASR — Canary e Parakeet (camada separada: ~2 GB, muda raramente)
RUN pip install --no-cache-dir "nemo_toolkit[asr]"

# 3. Mistral Voxtral: mistral-common[audio] + transformers atualizado
RUN pip install --no-cache-dir \
    "mistral-common[audio]" \
    "transformers>=4.40.0"

# 4. Demais dependências do projeto
RUN pip install --no-cache-dir python-dotenv && \
    pip install --no-cache-dir -r requirements.txt

# Copia o restante do projeto
COPY . .

# ── Variáveis de ambiente para GUI / GPU ──────────────────────────────────────
ENV DISPLAY=:0
# Evita problemas de shared memory em alguns ambientes X11
ENV QT_X11_NO_MITSHM=1
# Permite controle de memória GPU pela aplicação via env (ver compose)
ENV CUDA_VISIBLE_DEVICES=0

CMD ["python3", "main.py"]
