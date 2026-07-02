import flet as ft
import argparse
import logging
import os
from pathlib import Path
import sys
import threading

from dotenv import load_dotenv
load_dotenv()

from frontend.utils.recent_manager import RecentManager
from frontend.widgets.mic import MicMenu
from constant import ASR_MODEL_KEY




def _prewarm_speech():
    try:
        from voice.speech import SpeechToText
        stt = SpeechToText()
        stt.load_model(ASR_MODEL_KEY)
        logging.info("Loading Model - (Pre-warm).")
    except Exception as e:
        logging.warning(f"Pre-warm failed: {e}")


logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", 
        level=logging.INFO, 
        encoding="utf-8", 
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
        logging.FileHandler("frontend.log", encoding='utf-8'), 
        logging.StreamHandler(sys.stdout)                    
        ])

class MainPage():
    def __init__(self, page: ft.Page):
        self.page = page
        self.mic_menu = MicMenu(page)
        self.menu_instance = None


    def execute_benchmark_pipeline(self):
        from voice.speech import SpeechToText
        pasta_audios = Path(r"voice/benchmark_wav")

        dataset_benchmark = {
            "1.wav": "Abra o Google",
            "2.wav": "Abra o Discord",
            "3.wav": "Feche o Fire Fox",
            "4.wav": "Execute o Any Desk",
            "5.wav": "Inicia o System Manager",
            "6.wav": "Abra Devil may Cry",
            "7.wav": "Abre o Intagram",
            "8.wav": "Abrir Obsidian",
            "9.wav": "Pode abrir o File Explorer",
            "10.wav": "Pare o Blender",
        }
        speech_app = SpeechToText()

        logging.info(f"=== Iniciando Benchmark para {len(dataset_benchmark)} arquivos ===")
        for nome_arquivo, texto_referencia in dataset_benchmark.items():
            
            caminho_audio_completo = pasta_audios / nome_arquivo
            
            if caminho_audio_completo.exists():
                logging.info(f"\n🎧 Processando: {nome_arquivo}")
                logging.info(f"📝 Referência  : '{texto_referencia}'")
                
                speech_app.run_benchmark(
                    audio=str(caminho_audio_completo), 
                    reference=texto_referencia
                )
            else:
                logging.info(f"\n ERRO: O arquivo '{nome_arquivo}' não foi encontrado na pasta.")


    def execute_benchmark_transcription_pipeline(self):
        from voice.speech import SpeechToText
        pasta_audios = Path(r"voice/benchmark_wav")

        dataset_benchmark = {
            "1_transcription.wav": "APIs e Arquitetura REST Resumo sobre APIs e arquitetura REST para a prova de back-end. Uma API, ou Interface de Programação de Aplicações, atua como uma ponte de comunicação padronizada entre diferentes sistemas de software. No padrão REST, utilizamos os métodos nativos do protocolo HTTP, como os verbos GET, POST, PUT e DELETE, para consultar e manipular recursos no servidor.É importante notar que, na arquitetura moderna, as respostas do servidor quase sempre retornam no formato JSON. Isso substituiu o antigo padrão XML porque o JSON é mais leve e facilita imensamente o parsing dos dados no lado do front-end da aplicação.",
            "2_transcription.wav": "Modelos de Computação em Nuvem Anotações da aula de hoje sobre computação em nuvem. Basicamente, precisamos memorizar as diferenças entre os três modelos principais de serviço: IaaS, PaaS e SaaS. Quando fazemos o deploy de uma aplicação usando PaaS, ou Plataforma como Serviço, a nuvem abstrai toda a infraestrutura subjacente, o que permite que a equipe de desenvolvimento foque exclusivamente na escrita do código. Um ponto crucial para sistemas corporativos é o contrato de nível de serviço, conhecido como SLA. Os grandes provedores garantem uma disponibilidade de 99,9% de uptime anual. Isso reduz drasticamente o tempo de inatividade quando comparamos com a manutenção dos antigos servidores on-premise locais.",
            "3_transcription.wav": "Evolução do Armazenamento: HDD vs SSD Comparativo rápido de hardware de armazenamento para o guia de montagem. A principal diferença estrutural entre um HDD e um SSD é a total ausência de partes mecânicas móveis no disco de estado sólido. Enquanto um disco rígido magnético tradicional opera girando a 7200 RPM e atinge taxas de transferência na faixa de 150 megabytes por segundo, a tecnologia flash mudou tudo. Hoje, um SSD com protocolo NVMe moderno, conectado diretamente no barramento PCIe da placa-mãe, ultrapassa com extrema facilidade a marca de 3500 megabytes por segundo. Essa transição, que ganhou muita força a partir de 2012, revolucionou o tempo de boot dos sistemas operacionais de desktop.Feche o Fire Fox",
            "4_transcription.wav": "Segurança da Informação e LGPD Revisão para o exame de segurança cibernética. O foco do capítulo 4 foi entender os vetores de ataque modernos, principalmente os ataques de negação de serviço distribuída, a sigla DDoS, e as táticas de engenharia social focadas em phishing. Para tentar mitigar o risco de invasão de contas corporativas, a implementação do 2FA, a autenticação de dois fatores, deixou de ser um diferencial e se tornou uma exigência básica. Além da parte técnica, existe a questão legal. As empresas no Brasil precisam se adequar rigorosamente às diretrizes da LGPD, a Lei Geral de Proteção de Dados, que foi sancionada em agosto de 2018. O não cumprimento dessas regras de privacidade pode resultar em multas que chegam a 2% do faturamento da empresa.",
            "5_transcription.wav": "Fundamentos de Inteligência Artificial Conceitos iniciais do módulo de inteligência artificial. O primeiro passo é saber diferenciar os termos Machine Learning e Deep Learning. O Deep Learning é uma subcategoria que utiliza redes neurais artificiais complexas, estruturadas com múltiplas camadas ocultas, para conseguir extrair padrões de datasets gigantescos, como milhões de imagens ou horas de áudio. Ontem à noite, durante o treinamento prático do nosso modelo de visão computacional, enfrentei um clássico problema de overfitting. A precisão do modelo no conjunto de dados de treino chegou a impressionantes 98%, mas, quando fui rodar a inferência nos dados de validação, a taxa de acerto despencou para apenas 65%. Preciso ajustar os hiperparâmetros amanhã.",
        }
        speech_app = SpeechToText()

        logging.info(f"=== Iniciando Benchmark para {len(dataset_benchmark)} arquivos ===")
        for nome_arquivo, texto_referencia in dataset_benchmark.items():
            
            caminho_audio_completo = pasta_audios / nome_arquivo
            
            if caminho_audio_completo.exists():
                logging.info(f"\n🎧 Processando: {nome_arquivo}")
                logging.info(f"📝 Referência  : '{texto_referencia}'")
                
                speech_app.run_benchmark_transcription(
                    audio=str(caminho_audio_completo), 
                    reference=texto_referencia
                )
            else:
                logging.info(f"\n ERRO: O arquivo '{nome_arquivo}' não foi encontrado na pasta.")


    async def main(self):
        self.page.title = "Voice Writter"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.padding = 0
        self.page.window.icon = "frontend/images/icon.png"


        parser = argparse.ArgumentParser(description='Voice Writter App')
        parser.add_argument('--editor', type=str, nargs="?", const="last_path", help='Abrir o editor no último caminho utilizado')
        parser.add_argument('--main_menu', type=str, nargs="?", const="Exists", help="Abrir o menu_inicial")
        args, unknown = parser.parse_known_args()

        mic_menu_container = self.mic_menu.build_ui()

        mic_window = ft.AlertDialog(
            content=mic_menu_container,
            content_padding=0,
            bgcolor=ft.Colors.TRANSPARENT,
            open=False
        )

        async def route_change():
            self.page.views.clear()

            if self.page.route == "/":
                from frontend.speech_menu import SpeechMenu
                self.menu_instance = SpeechMenu(self.page)

                speech_view = ft.View(
                    route="/",
                    padding=0,
                    spacing=0,
                    controls=[]
                )

                self.page.views.append(speech_view)

                speech_view.controls.append(self.menu_instance.build_ui())

            if self.page.route == "/main_menu":
                from frontend.main_menu import MainEditorMenu
                self.menu_instance = MainEditorMenu(self.page)
                
                home_view = ft.View(
                    route="/main_menu",
                    padding=0, 
                    spacing=0,
                    controls=[]
                )
                
                self.page.views.append(home_view)
                
                home_view.controls.append(self.menu_instance.build_ui())

            if self.page.route == "/editor":
                current_path = self.page.current_project_path

                if current_path and os.path.exists(current_path):
                    from frontend.editor_menu import EditorMenu
                    self.menu_instance = EditorMenu(self.page, self.mic_menu)

                    editor_layout = ft.View(
                        route="/editor",
                        padding=0,
                        spacing=0,
                        controls=[]
                    )

                    self.page.views.append(editor_layout)

                    editor_layout.controls.append(self.menu_instance.build_ui(current_path))
                    
                else:
                    logging.info("Path inválido ou não fornecido, voltando para Home.")
                    await self.page.push_route("/")

            self.page.update()

        async def view_pop(view):
            self.page.views.pop()
            top_view = self.page.views[-1]
            await self.page.push_route(top_view.route)


        def manage_shortcuts(e: ft.KeyboardEvent):
            if e.key == "F9":
                if not mic_window.open:
                    self.page.show_dialog(mic_window)
                    self.mic_menu.handle_mic_click(mic_button=mic_window.content.content.controls[0])
                else:
                    self.page.pop_dialog()

                self.page.update()

            if e.key == "F8":
                from frontend.speech_menu import SpeechMenu
                from frontend.editor_menu import EditorMenu
                if mic_window.open:
                    self.mic_menu.handle_mic_click(mic_button=mic_window.content.content.controls[0])

                elif type(self.menu_instance) == SpeechMenu:
                    self.mic_menu.handle_mic_click(self.menu_instance.mic_card.content.controls[0])

                elif type(self.menu_instance) == EditorMenu and self.menu_instance.can_listen == True:
                    self.menu_instance.handle_mic_click(self.menu_instance.mic_button)

            if e.key == "F7":
                if hasattr(self.menu_instance, "speech"):
                    self.menu_instance.speech.stop_listen()

            if e.key == "F12":
                self.execute_benchmark_pipeline()

            if e.ctrl and e.key == "B":
                self.execute_benchmark_transcription_pipeline()

            if e.ctrl and e.key == "P":
                if hasattr(self.menu_instance, "create_and_open_new_markdown"):
                    self.menu_instance.create_and_open_new_markdown()

            if e.ctrl and e.key == "N":
                if hasattr(self.menu_instance, "create_new_dir"):
                    self.menu_instance.create_new_dir()

            if e.ctrl and e.key == "S":
                if hasattr(self.menu_instance, "_save_now"):
                    self.menu_instance._save_now()


        self.page.on_route_change = route_change
        self.page.on_view_pop = view_pop

        self.page.on_keyboard_event = manage_shortcuts

        if args.editor:
            manager = RecentManager().get_recents()[0]
            logging.info(f"Manager: {manager}")
            self.page.current_project_path = manager
            await self.page.push_route("/editor")

        elif args.main_menu:
            await self.page.push_route("/main_menu")

        else:
            await route_change()

        threading.Thread(target=_prewarm_speech, daemon=True).start()

async def flet_target(page:ft.Page):
    app = MainPage(page)

    await app.main()


if __name__ == "__main__":
    if "--type-at-cursor" in sys.argv:
        from voice.type_at_cursor import TypeAtCursorMode
        TypeAtCursorMode().run()
        sys.exit(0)
    ft.run(flet_target, view=ft.AppView.FLET_APP)