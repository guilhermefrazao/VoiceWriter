# Wakeword "transcrição" — Design

## Contexto

Hoje o fluxo de comando de voz (`voice/interact_app.py` + `voice/speech.py:listen_for_command`) só é
disparado pela hotkey **F9**, tratada em `main.py:manage_shortcuts` — que só funciona com a janela do
Flet em foco (não existe hotkey global de SO hoje; `keyboard==0.13.5` está nas dependências mas não é
usado). O objetivo deste projeto é permitir que o usuário dispare esse mesmo fluxo falando a wakeword
"transcrição", mesmo com a janela minimizada/oculta.

## Suposições assumidas sem confirmação do usuário

Duas perguntas de esclarecimento não foram respondidas a tempo (usuário ausente). Segui com as opções
recomendadas, registradas aqui para revisão quando o usuário retornar:

1. **Bandeja do sistema**: usar `pystray` para manter o processo vivo com um ícone na bandeja
   (menu Abrir/Sair), e o botão X da janela passa a minimizar para a bandeja em vez de encerrar o
   processo. Alternativa descartada: só minimizar a janela sem ícone de bandeja.
2. **Escopo Docker**: o design foca a execução nativa no Windows (onde bandeja/minimizar fazem
   sentido). A captura contínua de áudio dentro do container via PulseAudio fica fora do escopo
   inicial — o app continua funcionando normalmente em primeiro plano no Docker, sem o listener de
   wakeword ali.

Também foi confirmado explicitamente pelo usuário:
- O app deve continuar rodando (minimizado/bandeja), não um processo externo separado.
- Dados de treino gerados sinteticamente via TTS (pipeline oficial do openWakeWord com Piper), sem
  gravação manual de centenas de amostras.

## Arquitetura geral

Quatro componentes, todos seguindo os padrões já existentes no projeto (threads daemon, sem introduzir
um novo sistema de configuração):

1. **Script de treino** (offline, execução manual e esporádica pelo usuário)
2. **Listener de wakeword** (thread sempre ativa em paralelo ao app)
3. **Integração com o fluxo de ASR** (reaproveita o caminho já existente do F9)
4. **Bandeja do sistema** (mantém o processo vivo com a janela fechada)

```
[Microfone] --stream contínuo--> [WakewordListener/openWakeWord] --score > limiar--> [callback]
                                                                                          |
                                                                                          v
                                                          MainPage.trigger_mic_listen()
                                                          (mesmo caminho do F9 hoje)
                                                                                          |
                                                                                          v
                                          mic_menu.handle_mic_click -> speech.listen_for_command()
                                          -> translation_tasks() -> abre/fecha app, etc.
```

## Componente 1 — Script de treino (`scripts/train_wakeword.py`)

- Segue a convenção existente de scripts avulsos (`scripts/repro_parakeet_crash.py`, etc.), CLI
  standalone, não é importado pelo app em runtime.
- Usa o pipeline oficial de treino sintético do openWakeWord:
  - **Amostras positivas**: gera falas sintéticas de "transcrição" via TTS Piper (voz(es) pt-BR),
    variando velocidade/tom para diversidade.
  - **Amostras negativas**: usa os datasets/features pré-computados que o openWakeWord baixa
    automaticamente (fala genérica + ruído), evitando gravação manual.
  - **Treino**: treina apenas a "cabeça" classificadora leve sobre os embeddings (é assim que o
    openWakeWord é desenhado — rápido mesmo em CPU, não é um treino de modelo de áudio completo).
  - **Exporta** o modelo final para `voice/wakeword/models/transcricao.onnx`.
- Aviso de escopo: a primeira execução baixa alguns GB de dados de features negativas (cache local,
  reutilizável em treinos futuros). Isso é esperado e documentado num README curto em
  `voice/wakeword/`.
- Não faz parte do fluxo automático do app — é rodado manualmente (`python scripts/train_wakeword.py`)
  sempre que o usuário quiser re-treinar/ajustar sensibilidade.

## Componente 2 — Listener de wakeword (`voice/wakeword/detector.py`)

- Classe `WakewordListener`, iniciada como thread daemon a partir de `main.py` (mesmo padrão de
  `_prewarm_speech`, `main.py:188`).
- Abre seu **próprio stream PyAudio** (16kHz mono, frames curtos ~80ms), independente do stream que
  `speech_recognition` abre sob demanda em `listen_for_command`/`transcribe_continuously`.
- Alimenta os frames no modelo `openwakeword.Model(wakeword_models=["voice/wakeword/models/transcricao.onnx"])`
  e verifica o score contra um limiar (com debounce simples para não disparar múltiplas vezes na mesma
  fala).
- Expõe `pause()`/`resume()`: enquanto `listen_for_command` estiver com o microfone aberto para captar
  o comando, o listener libera o dispositivo (evita conflito de acesso exclusivo ao microfone no
  Windows). É retomado assim que o comando termina.
- Se o arquivo do modelo (`transcricao.onnx`) não existir (usuário ainda não treinou), a thread loga um
  aviso e não inicia — o app continua funcionando normalmente só com F9, sem quebrar nada.
- Exceções na thread são capturadas e logadas (mesmo padrão de `_prewarm_speech`), nunca derrubam o
  app.

## Componente 3 — Integração com o fluxo de ASR existente

- A lógica que hoje está inline no branch `F9` de `manage_shortcuts` (`main.py:133-140`: abrir o dialog
  `mic_window` + chamar `mic_menu.handle_mic_click`) é extraída para um método reaproveitável, ex.
  `MainPage.trigger_mic_listen()`.
- O keyboard handler do F9 passa a chamar esse método; o callback de detecção da wakeword chama o
  **mesmo método**, agendado de forma thread-safe no loop do Flet (a wakeword roda em thread própria,
  fora do event loop assíncrono do Flet — a forma exata de despachar essa chamada com segurança será
  resolvida na fase de implementação).
- Deve haver algum elemento visual mostrando para o usuário que o app está "ouvindo" a wakeword (ex: ícone de microfone na bandeja, ou um
  toast temporário). A implementação exata será decidida na fase de implementação.
- Resultado: nenhuma lógica de comando é duplicada. `listen_for_command()` →
  `translation_tasks()` → abrir/fechar app/desligar PC, diálogo de feedback Sim/Não e métricas
  continuam exatamente como hoje — a wakeword é só um gatilho alternativo para o mesmo caminho.

## Componente 4 — Bandeja do sistema (`frontend/utils/tray.py`)

- Nova dependência: `pystray`.
- Ícone na bandeja com menu **Abrir** (mostra a janela) / **Sair** (para o listener de wakeword e
  encerra o processo de fato).
- O evento de fechar a janela (X) passa a escondê-la em vez de encerrar o processo, para o listener de
  wakeword e o ícone de bandeja continuarem ativos.
- Esse comportamento (listener + bandeja) só é ativado na execução nativa via
  `ft.run(..., view=ft.AppView.FLET_APP)`; o modo headless `--type-at-cursor` não é afetado.

## Tratamento de erros

- Modelo de wakeword ausente → listener não inicia, log de aviso, app funciona normalmente (F9 continua
  ativo).
- Conflito de dispositivo de microfone → resolvido via `pause()`/`resume()`, nunca dois streams abertos
  simultaneamente no mesmo device.
- Falha na thread do listener (ex. dispositivo de áudio desconectado) → capturada e logada, não derruba
  o app; idealmente tenta reabrir o stream com backoff simples.

## Testes

- **Script de treino**: verificação manual (falar a wakeword e observar o score de detecção num
  harness simples de teste local).
- **Detector**: teste automatizado alimentando `WakewordListener` com um WAV pré-gravado da wakeword
  (deve disparar o callback) e um WAV de fala genérica/negativa (não deve disparar) — sem depender de
  microfone real, roda em CI.
- **Integração ponta a ponta**: teste manual — minimizar o app para a bandeja, falar "transcrição",
  confirmar que o dialog do microfone abre e o fluxo de comando roda. Documentado como passo de QA
  manual (depende de áudio ao vivo + bandeja do Windows, não é automatizável facilmente).

## Fora de escopo (por ora)

- Suporte a wakeword dentro do container Docker.
- Múltiplas wakewords / múltiplos idiomas.
- UI para ajustar sensibilidade do wakeword (fica hardcoded/config simples por enquanto).
