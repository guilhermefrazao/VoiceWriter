# Roberto -

### Prioridade

1 - Melhorar o "reconhecimento de comandos", principalmente para aplicativos com nomes em inglês (Como "Google Chrome", "Visual Studio Code", etc.) e também para comandos de navegação (como "abrir nova aba", "fechar janela", etc.)

### Secundária

5 - Diminuir o tempo para começar o reconhecimento da fala (latência), após clicar no botão de gravação. (tanto com animação visual quanto com o reconhecimento de voz em si, principalmente na primeira execução)


# Saraiva - 

### Prioridade

6 - Criar e Avaliar variáveis para diferentes modelos de ASR. (success_rate, WER, Latency, etc.) (na transcrição de comandos e de texto em geral)

### Secundária

2 - Formatação de Markdown utilizando voz. (ex: "hastag", "aspas", "asteriscos", etc.)


# Guilherme - 

### Prioridade

10 - Testar diferentes modelos de ASR dentro da arquitetura, atualmente feita com o Whisper, testar também desempenho dos modelos Whisper (Modelo como Parakeet para Pt-BR).
    10.1 - Testar modelo OpenAI Whisper e Distil-Whisper 
    10.2 - Testar modelo Voxtral-Mini-3B 
    10.3 - Testar modelo NVIDIA Canary-V2 
    10.4 - Testar modelo NVIDIA Parakeet-TDT 

### Secundária
    
3 (Análisar) - Implementar uma feature com Wakeword, fazer funcionar quando a aplicação esteja rodando em background ou com comandos no teclado (F9), para que o usuário possa ativar o reconhecimento de voz sem precisar clicar no botão de gravação. (ex: "Hey Voice Control, abrir Google Chrome")

8 - Implementar uma feature de transcrição de fala, que irá realizar o Speech-to-text onde quer que o cursor esteja posicionado, para facilitar a edição de texto.


## Carlos - 

### Prioridade

11 - Comparar outras aplicações de controle de voz para computador e realizar uma análise de pontos fortes e fracos, para entender melhor o mercado e possíveis melhorias para a aplicação.

### Secundária

4 - Expandir o reconhecimento de comandos para mais aplicativos e ações, como por exemplo além de abrir o e fechar aplicativos, conseguir interagir com eles. (Abrir e pesquisar no Google Chrome, abrir e criar arquivos no Visual Studio Code, etc.)


# Tasks prioridade menor não divididas entre os integrantes -

9 - Adaptar o repositório para conseguir rodar ele tanto no windows quanto no linux, utilizando bibliotecas compatíveis com ambos os sistemas operacionais. (atualmente o repositório é focado para Windows, utilizando a biblioteca pywin32 para controle de janelas e aplicativos)

7 - Fazer com que a detecção de audio seja interrompida após um tempo de silêncio durante a trasncrição em tempo real no editor de texto.



### Explicação dos modelos de ASR -

Distil-Whisper

Arquitetura: Destilação de conhecimento (knowledge distillation) do Whisper large-v2/v3. Encoder-decoder transformer com ~6x menos parâmetros que o modelo original.

Características:
- Mantém ~98% do WER do Whisper large-v2 para inglês
- Inferência ~6x mais rápida que o equivalente full-size
- A versão multilingual (distil-large-v3) suporta PT-BR, mas a distilação foi primariamente otimizada para EN — a degradação em PT-BR é maior que em inglês
- API idêntica ao Whisper — integração trivial via Faster-Whisper

Opinião para a aplicação: Substituto direto de baixo risco para o modo de comandos. Para transcrição PT-BR longa, a perda de qualidade em relação ao large-v2 que você já usa pode não
valer a pena. Melhor uso: trocar o small atual pelo distil-large-v3 no modo de comandos e medir o impacto.

---
Voxtral-Mini-3B

Arquitetura: Versão compacta do Voxtral, ~3B parâmetros. Ainda um LLM multimodal, mas em escala utilizável.

Características:
- Cabe em ~6-8GB VRAM em float16 — viável em GPUs consumer
- Latência maior que modelos ASR dedicados (geração autoregressiva)
- Melhor compreensão semântica que modelos ASR puros — entende intenção, não só transcreve
- PT-BR suportado (herda o multilinguismo do Mistral)

Opinião para a aplicação: O caso de uso mais interessante seria substituir o pipeline regex + Whisper no modo de comandos por um único modelo que transcreve e extrai a intenção
simultaneamente — eliminando o interact_app.py por completo. O custo é latência mais alta (~500ms–1s) comparado ao Whisper small + regex. Vale testar no todo #2 (comandos com nomes em
inglês), onde a compreensão semântica do Voxtral-Mini superaria o regex diretamente.

---

NVIDIA Canary-V2

Arquitetura: FastConformer encoder + Transformer decoder, 1B parâmetros. Modelo ASR multilingual dedicado, família NeMo da NVIDIA.

Características:
- Suporta EN, DE, ES, FR nativamente — PT-BR não está entre os idiomas oficialmente suportados na versão 1.0
- FastConformer é extremamente eficiente em GPU — latência competitiva com Whisper small
- Capacidade de transcrição com pontuação e capitalização automáticas (diferencial sobre o Whisper)
- Integração via NeMo toolkit (dependência pesada)

Opinião para a aplicação: Não recomendado como opção principal dado que PT-BR não é suportado oficialmente — o risco de WER alto é real. Se o suporte PT-BR for adicionado em versões
futuras ou você encontrar um checkpoint fine-tuned para PT-BR na HuggingFace, reconsidere. A pontuação automática nativa seria um diferencial valioso para o modo de transcrição.

---
NVIDIA Parakeet-TDT

Arquitetura: Token-and-Duration Transducer (TDT), ~0.6B parâmetros. ASR dedicado, extremamente otimizado para velocidade de inferência.

Características:
- Exclusivamente inglês — treinado no dataset MLS English e afins
- Benchmark de velocidade: um dos mais rápidos disponíveis para EN (fator de tempo real > 100x)
- TDT gera timestamps de duração por token — útil para legendagem, mas irrelevante para seu caso
- Sem suporte a PT-BR

Opinião para a aplicação: Não aplicável para PT-BR. Útil apenas se você quiser incluir uma baseline em inglês na avaliação do todo #8, ou se futuramente a aplicação suportar EN.


