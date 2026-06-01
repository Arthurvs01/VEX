import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sys
import os
import shutil
import textwrap
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
import ctypes
from PIL import Image, ImageDraw, ImageOps

try:
    import win32print
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

# Módulos Customizados
from styles import Theme, configurar_estilos_ttk
from database import DatabaseManager
from utils import resource_path, obter_ip_local, format_currency
from printer import PrinterManager, WIN32_PRINTER_AVAILABLE
from server import criar_app_vex
from ui_helpers import create_tooltip, styled_nav_button
from constants import (
    APP_NAME, APP_TITLE_LOADING, WINDOWS_APP_ID, WINDOW_SCALE_FACTOR,
    DEFAULT_COMPANY_NAME, DEFAULT_COMPANY_PHONE, DEFAULT_COMPANY_ADDRESS,
    DEFAULT_NUM_VIAS, DEFAULT_NUMBERING_TYPE, DEFAULT_HISTORY_TYPE,
    DEFAULT_PAPER_WIDTH, DEFAULT_HEADER_SIZE, DEFAULT_ORDER_SIZE,
    DEFAULT_ADDRESS_SIZE, DEFAULT_ITEMS_SIZE, DEFAULT_VALUES_SIZE,
    DEFAULT_PAYMENT_SIZE, DEFAULT_PRINT_VISIBILITY, DEFAULT_SHORTCUTS,
    APPDATA_FOLDER, DATABASE_FILENAME, SIDEBAR_EXPANDED,
    BLOCK_UNKNOWN_NEIGHBORHOOD, DEFAULT_DELIVERY_FEE, 
    DEFAULT_WEBAPP_MENU_ENABLED, DEFAULT_WEBAPP_ADMIN_ENABLED,
    DEFERRED_INIT_DELAY, WEB_SERVER_PORT, WEB_SERVER_HOST, WEB_SERVER_DEBUG,
    ORDER_TYPE_DELIVERY, ORDER_TYPE_PICKUP, NAVIGATION_BINDING_KEYS,
    MODIFIER_KEYS
)

# Biblioteca para Calendário
try:
    from tkcalendar import DateEntry
except ImportError:
    DateEntry = None
ctk.set_appearance_mode("light")

class GestorDelivery(ctk.CTk):
    """
    Aplicação principal para gestão de comandas de delivery.
    Gerencia interface gráfica, pedidos, impressão e servidor web.
    """
    
    def __init__(self):
        super().__init__()

        # Configuração para exibir o ícone corretamente na barra de tarefas do Windows
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(WINDOWS_APP_ID)
        except Exception:
            pass

        # Configuração visual imediata
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)
        
        self.sidebar_expandido = SIDEBAR_EXPANDED
        self.logo_path = None
        self.taxa_atual = DEFAULT_DELIVERY_FEE
        self.ip_local = obter_ip_local()
        self.url_publica = None
        self.tipo_numeracao = DEFAULT_NUMBERING_TYPE
        self.tipo_historico_atual = DEFAULT_HISTORY_TYPE
        self.app_data_base_path = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', APPDATA_FOLDER)
        self.db = None
        self.impressora_selecionada = None
        self.bloquear_bairro_desconhecido = BLOCK_UNKNOWN_NEIGHBORHOOD

        # Configurações de Impressão: Visibilidade de Seções
        self.vis_cabecalho = DEFAULT_PRINT_VISIBILITY['header']
        self.vis_pedido = DEFAULT_PRINT_VISIBILITY['order']
        self.vis_cliente = DEFAULT_PRINT_VISIBILITY['client']
        self.vis_itens = DEFAULT_PRINT_VISIBILITY['items']
        self.vis_totais = DEFAULT_PRINT_VISIBILITY['totals']
        self.vis_pagamento = DEFAULT_PRINT_VISIBILITY['payment']

        # WebApp Configs
        self.webapp_menu_enabled = DEFAULT_WEBAPP_MENU_ENABLED
        self.webapp_admin_enabled = DEFAULT_WEBAPP_ADMIN_ENABLED

        # Atalhos de Teclado
        self.atalhos_default = DEFAULT_SHORTCUTS.copy()
        self.atalhos_usuario = {}
        self.atalhos_binds = []
        
        # Configurações Padrão
        self.nome_empresa = DEFAULT_COMPANY_NAME
        self.fone_empresa = DEFAULT_COMPANY_PHONE
        self.end_empresa = DEFAULT_COMPANY_ADDRESS
        self.num_vias = DEFAULT_NUM_VIAS

        # Configurações de Impressão Avançadas
        self.largura_papel = DEFAULT_PAPER_WIDTH
        self.tam_cabecalho = DEFAULT_HEADER_SIZE
        self.tam_pedido = DEFAULT_ORDER_SIZE
        self.tam_endereco = DEFAULT_ADDRESS_SIZE
        self.tam_itens = DEFAULT_ITEMS_SIZE
        self.tam_valores = DEFAULT_VALUES_SIZE
        self.tam_pagamento = DEFAULT_PAYMENT_SIZE

        self.editando_id_pedido = None
        self.title(APP_TITLE_LOADING)

        # Configuração de Janela: Centralizar e Iniciar Maximizada
        largura_tela = self.winfo_screenwidth()
        altura_tela = self.winfo_screenheight()
        
        # Define o tamanho da janela como escala da tela para manter proporção
        largura_janela = int(largura_tela * WINDOW_SCALE_FACTOR)
        altura_janela = int(altura_tela * WINDOW_SCALE_FACTOR)

        pos_x = (largura_tela // 2) - (largura_janela // 2)
        pos_y = (altura_tela // 2) - (altura_janela // 2)
        
        self.geometry(f"{largura_janela}x{altura_janela}+{pos_x}+{pos_y}")
        self.after(0, lambda: self.state('zoomed'))
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Atalhos de Teclado Globais para Navegação
        for key_binding in NAVIGATION_BINDING_KEYS:
            self.bind(key_binding, self.navegar_teclado)

        # Layout Base Inicial (Sidebar aparece rápido)
        try:
            self.criar_sidebar()
        except Exception as e:
            print(f"Erro ao criar sidebar: {e}")
        self.container = ctk.CTkFrame(self, fg_color=Theme.BG_MAIN)
        self.container.pack(side="left", fill="both", expand=True)

        # Inicialização diferida para não travar a abertura da janela
        self.after(DEFERRED_INIT_DELAY, self.inicializar_sistema_deferred)

    def inicializar_sistema_deferred(self):
        # Define o padrão AppData, que pode ser sobrescrito pelo banco local (bootstrap)
        self.data_dir = self.app_data_base_path
        """Executa as tarefas pesadas após a UI inicial aparecer"""
        
        try:
            bootstrap_db = Path("delivery.db")
            if bootstrap_db.exists():
                try:
                    with sqlite3.connect(bootstrap_db) as bootstrap_conn:
                        b_cursor = bootstrap_conn.cursor()
                        b_cursor.execute("SELECT valor FROM config WHERE chave = 'data_dir'")
                        res = b_cursor.fetchone()
                        if res:
                            self.data_dir = res[0]
                except Exception:
                    pass

            self.data_dir = str(Path(self.data_dir).expanduser().resolve())
            Path(self.data_dir).mkdir(parents=True, exist_ok=True)
            self.db_manager = DatabaseManager(os.path.join(self.data_dir, "delivery.db"))
            self.db = self.db_manager.conn
            self.cursor = self.db_manager.cursor
            
            self.configurar_estilos_globais()

            configs = {chave: valor for chave, valor in self.db_fetchall("SELECT chave, valor FROM config")}
            
            self.impressora_selecionada = configs.get('impressora_selecionada')
            self.nome_empresa = configs.get('nome_empresa', DEFAULT_COMPANY_NAME)
            self.fone_empresa = configs.get('fone_empresa', DEFAULT_COMPANY_PHONE)
            self.end_empresa = configs.get('end_empresa', DEFAULT_COMPANY_ADDRESS)
            self.num_vias = int(configs.get('num_vias', DEFAULT_NUM_VIAS))
            self.largura_papel = int(configs.get('largura_papel', DEFAULT_PAPER_WIDTH))
            self.data_dir = configs.get('data_dir', self.data_dir)
            self.bloquear_bairro_desconhecido = configs.get('bloquear_bairro', 'True') == 'True'
            self.tipo_numeracao = configs.get('tipo_numeracao', DEFAULT_NUMBERING_TYPE)
            if configs.get('logo_path') and os.path.exists(configs['logo_path']):
                self.logo_path = configs['logo_path']
            if hasattr(self, 'lbl_link_web'):
                self.lbl_link_web.configure(text=f"📱 LOCAL:\nhttp://{self.ip_local}:{WEB_SERVER_PORT}")
            
            # Carrega configurações de layout e visibilidade da impressão
            self.tam_cabecalho = int(configs.get('tam_cabecalho', 2))
            self.tam_pedido = int(configs.get('tam_pedido', 0))
            self.tam_endereco = int(configs.get('tam_endereco', 2))
            self.tam_itens = int(configs.get('tam_itens', 2))
            self.tam_valores = int(configs.get('tam_valores', 2))
            self.tam_pagamento = int(configs.get('tam_pagamento', 0))
            self.vis_cabecalho = configs.get('vis_cabecalho', 'True') == 'True'
            self.vis_pedido = configs.get('vis_pedido', 'True') == 'True'
            self.vis_cliente = configs.get('vis_cliente', 'True') == 'True'
            self.vis_itens = configs.get('vis_itens', 'True') == 'True'
            self.vis_totais = configs.get('vis_totais', 'True') == 'True'
            self.vis_pagamento = configs.get('vis_pagamento', 'True') == 'True'
            self.webapp_menu_enabled = configs.get('webapp_menu_enabled', 'True') == 'True'
            self.webapp_admin_enabled = configs.get('webapp_admin_enabled', 'False') == 'True'
            
            for chave, valor in configs.items():
                if chave.startswith("atalho_"):
                    partes = chave.split("_")
                    if len(partes) == 3:
                        self.atalhos_usuario.setdefault(partes[1], {})[partes[2]] = valor
            
        except Exception as e:
            print(f"Erro ao conectar banco: {e}")

        # Inicia Servidor Web com os dados da empresa
        self.server_info = {
            'nome': self.nome_empresa, 
            'fone': self.fone_empresa, 
            'end': self.end_empresa, 
            'logo_path': self.logo_path
        }
        self.server_config = {
            'menu_enabled': self.webapp_menu_enabled,
            'admin_enabled': self.webapp_admin_enabled
        }
        app_web = criar_app_vex(self.data_dir, self.server_info, self.server_config)
        web_server_thread = threading.Thread(
            target=lambda: app_web.run(
                host=WEB_SERVER_HOST,
                port=WEB_SERVER_PORT,
                debug=WEB_SERVER_DEBUG,
                use_reloader=False
            ),
            daemon=True
        )
        web_server_thread.start()

        # Atualiza o título e entra na tela principal
        self.title(APP_NAME)
        self.mostrar_tela_delivery()
        if self.logo_path:
            self.atualizar_imagem_logo()

    def obter_atalho(self, tela: str, funcao: str) -> str:
        """
        Retorna o atalho configurado para uma função em uma tela específica.
        
        Args:
            tela: Nome da tela (ex: "Delivery", "Histórico")
            funcao: Nome da função (ex: "Finalizar", "Salvar")
            
        Returns:
            String com o atalho (ex: "F1") ou vazio se não configurado
        """
        return self.atalhos_usuario.get(tela, {}).get(funcao, self.atalhos_default.get(tela, {}).get(funcao, ""))

    def _format_bind_key(self, tecla: str) -> str:
        if not tecla:
            return ""
        tecla = tecla.strip()
        if tecla.startswith("<") and tecla.endswith(">"):
            return tecla
        return f"<{tecla}>"

    def db_execute(self, query: str, params=()):
        self.cursor.execute(query, params)
        self.db.commit()
        return self.cursor

    def db_fetchone(self, query: str, params=()):
        self.cursor.execute(query, params)
        return self.cursor.fetchone()

    def db_fetchall(self, query: str, params=()):
        self.cursor.execute(query, params)
        return self.cursor.fetchall()

    def registrar_atalhos(self, tela):
        """Limpa binds anteriores e registra os novos da tela atual"""
        for b in self.atalhos_binds:
            self.unbind_all(b)
        self.atalhos_binds.clear()

        atalhos_tela = self.atalhos_default.get(tela, {})
        for funcao in atalhos_tela.keys():
            tecla = self.obter_atalho(tela, funcao)
            if tecla:
                cmd = None
                if tela == "Delivery":
                    if funcao == "Finalizar": cmd = lambda e: self.finalizar_pedido()
                    elif funcao == "Consulta": cmd = lambda e: self.abrir_consulta_precos()
                    elif funcao == "Limpar": cmd = lambda e: self.limpar_tela_delivery()
                    elif funcao == "Editar Item": cmd = lambda e: self.editar_item_carrinho()
                    elif funcao == "Excluir Item": cmd = lambda e: self.excluir_item_carrinho()
                elif tela == "Histórico":
                    if funcao == "Visualizar": cmd = lambda e: self.visualizar_comanda_estatisticas(None)
                    elif funcao == "Editar": cmd = lambda e: self.editar_pedido_estatisticas()
                    elif funcao == "Reimprimir": cmd = lambda e: self.reimprimir_pedido_estatisticas()
                    elif funcao == "Excluir": cmd = lambda e: self.excluir_pedido_estatisticas()
                elif tela == "Cardápio":
                    if funcao == "Salvar": cmd = lambda e: self.salvar_produto_db()
                    elif funcao == "Limpar": cmd = lambda e: self.limpar_campos_cardapio()
                    elif funcao == "Excluir": cmd = lambda e: self.excluir_produto_db()

                if cmd:
                    bind_key = self._format_bind_key(tecla)
                    self.bind_all(bind_key, cmd)
                    self.atalhos_binds.append(bind_key)

    def capturar_tecla_atalho(self, event, ent):
        """
        Captura a tecla pressionada e insere o nome no campo de configuração.
        
        Args:
            event: Evento de teclado do Tkinter
            ent: Widget Entry para inserir a tecla capturada
        """
        tecla = event.keysym.upper()
        if tecla in MODIFIER_KEYS:
            return "break"

        ent.delete(0, 'end')
        if tecla != "BACKSPACE":
            ent.insert(0, tecla)
        return "break"

    def configurar_estilos_globais(self):
        configurar_estilos_ttk(ttk.Style())

    def on_close(self):
        try:
            if hasattr(self, 'db_manager') and self.db_manager:
                self.db_manager.fechar()
        except Exception:
            pass
        self.destroy()

    def criar_sidebar(self):
        """Cria a barra lateral de navegação persistente (chamado apenas uma vez no __init__)"""
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=Theme.PRIMARY)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False) # Impede que o conteúdo interno mude a largura

        # Header da Sidebar (Menu + Logo)
        self.frame_logo = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.frame_logo.pack(fill="x", pady=(8, 18))

        self.btn_menu = ctk.CTkButton(self.frame_logo, text="≡", width=44, height=44,
                                      fg_color="transparent", font=Theme.FONT_H1,
                                      hover_color=Theme.PRIMARY_HOVER, command=self.toggle_sidebar)
        self.btn_menu.pack(side="top", anchor="ne", padx=10)

        # Espaço para o Ícone/Logo
        self.btn_logo = ctk.CTkButton(self.frame_logo, text="Logo", width=110, height=110,
                                      corner_radius=55, fg_color=Theme.PRIMARY_HOVER,
                                      hover_color=Theme.PRIMARY_HOVER, text_color="white",
                                      font=Theme.FONT_LABEL,
                                      command=self.selecionar_logo)
        self.btn_logo.pack(pady=8)

        if self.logo_path:
            self.atualizar_imagem_logo()

        # Botões de Navegação
        self.nav_info = [
            ("Pedidos", "🚚", self.mostrar_tela_delivery),
            ("Hist. Delivery", "📦", lambda: self.mostrar_tela_estatisticas("ENTREGA")),
            ("Hist. Retirada", "🥡", lambda: self.mostrar_tela_estatisticas("RETIRADA")),
            ("Cardápio", "📋", self.mostrar_tela_cardapio),
            ("Taxa Entrega", "💰", self.mostrar_tela_taxas),
            ("Configurações", "⚙️", self.mostrar_tela_configuracoes)
        ]
        
        self.nav_buttons = []
        for texto, icone, comando in self.nav_info:
            btn = styled_nav_button(self.sidebar, texto, icone, comando, expanded=self.sidebar_expandido)
            btn.pack(pady=6, padx=12, fill="x")
            create_tooltip(btn, texto)
            self.nav_buttons.append((btn, texto, icone))

        # Rodapé da Sidebar com Versão
        self.lbl_versao = ctk.CTkLabel(self.sidebar, text="v1.0.11-beta", font=Theme.FONT_NORMAL, text_color="#ecf0f1")
        self.lbl_versao.pack(side="bottom", pady=10)

        # Link do Cardápio Digital
        txt_link = f"📱 LOCAL:\nhttp://{self.ip_local}:{WEB_SERVER_PORT}"
        self.lbl_link_web = ctk.CTkLabel(self.sidebar, text=txt_link, font=Theme.FONT_NORMAL, text_color="#f1c40f")
        self.lbl_link_web.pack(side="bottom", pady=2)

    def atualizar_sidebar(self, nome_ativo):
        """Atualiza a cor dos botões para indicar qual tela está ativa"""
        for btn, texto, _ in self.nav_buttons:
            if texto == nome_ativo:
                btn.configure(fg_color="#e74c3c", border_color="#e74c3c")
            else:
                btn.configure(fg_color="transparent", border_color="#ffffff")

    def navegar_teclado(self, event):
        """Permite usar as setas para navegar entre campos de entrada"""
        widget = self.focus_get()
        # Se estiver em uma tabela (Treeview), as setas devem funcionar normalmente para a tabela
        if isinstance(widget, ttk.Treeview):
            return
            
        if event.keysym == "Up" or event.keysym == "Left":
            proximo = widget.tk_focusPrev()
            if proximo: proximo.focus()
        elif event.keysym == "Down" or event.keysym == "Right":
            proximo = widget.tk_focusNext()
            if proximo: proximo.focus()

    def placeholder(self, modulo):
        messagebox.showinfo("Em breve", f"Módulo {modulo} em desenvolvimento.")
        self.atualizar_sidebar(modulo)

    def selecionar_logo(self):
        origem = filedialog.askopenfilename(filetypes=[("Imagens", "*.png *.jpg *.jpeg *.bmp")])
        if origem:
            # 1. Garantir que a pasta de assets existe
            pasta_assets = os.path.join(self.data_dir, "assets")
            if not os.path.exists(pasta_assets):
                os.makedirs(pasta_assets)

            # 2. Definir o novo caminho (usando o nome original ou um padrão)
            ext = os.path.splitext(origem)[1]
            destino = os.path.join(pasta_assets, f"logo_empresa{ext}")

            # 3. Remover a imagem antiga se for um arquivo diferente
            if self.logo_path and os.path.exists(self.logo_path) and self.logo_path != destino:
                try:
                    os.remove(self.logo_path)
                except Exception as e:
                    print(f"Não foi possível remover a logo antiga: {e}")

            # 4. Copiar o novo arquivo e atualizar referências
            shutil.copy2(origem, destino)
            self.logo_path = destino
            self.cursor.execute("INSERT OR REPLACE INTO config (chave, valor) VALUES ('logo_path', ?)", (destino,))
            self.db.commit()

            self.atualizar_imagem_logo()

    def atualizar_imagem_logo(self):
        size = 100 if self.sidebar_expandido else 40
        try:
            # Abre a imagem e converte para RGBA
            img = Image.open(self.logo_path).convert("RGBA")
            
            # Recorta a imagem para um quadrado centralizado (estilo Instagram)
            img = ImageOps.fit(img, (size * 2, size * 2), centering=(0.5, 0.5))
            
            # Cria uma máscara circular
            mask = Image.new('L', (size * 2, size * 2), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, size * 2, size * 2), fill=255)
            
            # Aplica a máscara circular na imagem
            img.putalpha(mask)
            
            # Converte para CTkImage
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
            
            self.btn_logo.configure(image=ctk_img, text="", width=size, height=size, corner_radius=size//2)
        except Exception as e:
            print(f"Erro ao carregar imagem: {e}")

    def toggle_sidebar(self):
        """Alterna a largura da barra lateral instantaneamente"""
        self.sidebar_expandido = not self.sidebar_expandido
        alvo = 200 if self.sidebar_expandido else 70

        # Atualiza largura da sidebar
        self.sidebar.configure(width=alvo)
        
        # Atualiza a Logo (tamanho e formato)
        if self.logo_path:
            self.atualizar_imagem_logo()
        else:
            size = 100 if self.sidebar_expandido else 40
            self.btn_logo.configure(text="Logo" if self.sidebar_expandido else "", width=size, height=size, corner_radius=size//2)

        # Atualiza os botões de navegação
        for btn, texto, icone in self.nav_buttons:
            btn.configure(text=texto if self.sidebar_expandido else icone, 
                          anchor="w" if self.sidebar_expandido else "center")

    def limpar_container(self):
        """Remove todos os widgets do container principal"""
        for widget in self.container.winfo_children():
            widget.destroy()

    def criar_card_container(self, titulo, parent=None, fg_color=None):
        """Helper para criar uma seção padronizada (Card)"""
        color = fg_color if fg_color else Theme.BG_CARD
        p = parent if parent else self.container
        frame = ctk.CTkFrame(p, fg_color=color, border_color=Theme.BORDER, border_width=1)
        frame.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkLabel(frame, text=titulo, font=Theme.FONT_H2, text_color=Theme.PRIMARY).grid(row=0, column=0, columnspan=10, pady=(10, 5), padx=15, sticky="w")
        return frame

    def mostrar_tela_delivery(self):
        self.limpar_container()
        self.atualizar_sidebar("Delivery")
        self.registrar_atalhos("Delivery")
        self.modo_retirada = tk.BooleanVar(value=False)

        # Adicionar colunas de pagamento se não existirem
        try: self.cursor.execute("ALTER TABLE pedidos ADD COLUMN forma_pagamento TEXT"); self.db.commit()
        except: pass
        
        # --- RODAPÉ (Pack primeiro para garantir visibilidade no fundo) ---
        self.frame_total = ctk.CTkFrame(self.container, height=100, fg_color="transparent")
        self.frame_total.pack(fill="x", side="bottom", padx=20, pady=10)

        self.lbl_total = ctk.CTkLabel(self.frame_total, text="TOTAL: R$ 0,00", font=("Arial", 28, "bold"), text_color=Theme.PRIMARY)
        self.lbl_total.pack(side="right", padx=20)

        from ui_helpers import styled_action_button
        self.btn_finalizar = styled_action_button(self.frame_total, f"FINALIZAR ({self.obter_atalho('Delivery', 'Finalizar')})", 
                                                 Theme.SUCCESS, self.finalizar_pedido, "🚀")
        self.btn_finalizar.pack(side="left", padx=5)

        self.btn_consultar = styled_action_button(self.frame_total, f"CONSULTA ({self.obter_atalho('Delivery', 'Consulta')})", 
                                                 Theme.SECONDARY, self.abrir_consulta_precos, "🔍")
        self.btn_consultar.pack(side="left", padx=5)
        
        self.btn_editar_item = styled_action_button(self.frame_total, f"EDITAR", Theme.ACCENT, self.editar_item_carrinho, "📝")
        self.btn_editar_item.pack(side="left", padx=5)

        self.btn_excluir_item = styled_action_button(self.frame_total, f"EXCLUIR", Theme.DANGER, self.excluir_item_carrinho, "❌")
        self.btn_excluir_item.pack(side="left", padx=5)

        # Botão Cancelar
        ctk.CTkButton(self.frame_total, text=f"LIMPAR ({self.obter_atalho('Delivery', 'Limpar')})", fg_color="gray", height=45, width=100,
                      font=("Arial", 12, "bold"), command=self.limpar_tela_delivery).pack(side="left", padx=5)

        # --- ÁREA DO CLIENTE ---
        self.frame_cliente = self.criar_card_container("📍 DADOS DO CLIENTE")

        # Switch para Retirada
        self.sw_retirada = ctk.CTkSwitch(self.frame_cliente, text="Pedido para Entrega / Retirada", 
                                         variable=self.modo_retirada, command=self.toggle_modo_retirada)
        self.sw_retirada.grid(row=0, column=2, columnspan=2, sticky="e", padx=15)

        # Configuração de pesos das colunas (4 colunas para flexibilidade)
        self.frame_cliente.grid_columnconfigure(0, weight=1) # Tel / Bairro
        self.frame_cliente.grid_columnconfigure(1, weight=2) # Nome / Rua
        self.frame_cliente.grid_columnconfigure(2, weight=1) # Num
        self.frame_cliente.grid_columnconfigure(3, weight=1) # Comp

        # Campos organizados em linhas lógicas
        self.ent_tel = self.criar_campo(self.frame_cliente, "Telefone", 1, 0)
        self.ent_nome = self.criar_campo(self.frame_cliente, "Nome Completo", 1, 1, colspan=3)
        
        self.ent_bairro = self.criar_campo(self.frame_cliente, "Bairro", 2, 0)
        self.ent_rua = self.criar_campo(self.frame_cliente, "Rua", 2, 1)
        self.ent_num = self.criar_campo(self.frame_cliente, "Número", 2, 2)
        self.ent_comp = self.criar_campo(self.frame_cliente, "Complemento", 2, 3)

        # Lista de widgets para monitoramento de foco na área do cliente
        self.widgets_cliente = [self.ent_tel, self.ent_nome, self.ent_bairro, self.ent_rua, self.ent_num, self.ent_comp]

        # BINDINGS DE NAVEGAÇÃO
        self.ent_tel.bind('<Return>', self.buscar_cliente)
        self.ent_nome.bind('<Return>', lambda e: self.ent_bairro.focus())
        self.ent_bairro.bind('<Return>', lambda e: self.ent_rua.focus())
        self.ent_bairro.bind('<FocusOut>', lambda e: self.buscar_taxa_bairro(), add="+")
        self.ent_rua.bind('<Return>', lambda e: self.ent_num.focus())
        self.ent_num.bind('<Return>', lambda e: self.ent_comp.focus())
        self.ent_comp.bind('<Return>', self.confirmar_cadastro_cliente)

        # Monitorar saída da área de cliente para qualquer outro lugar do sistema
        for ent in self.widgets_cliente:
            ent.bind('<FocusOut>', self.verificar_saida_cliente, add="+")

        # --- ÁREA DE LANÇAMENTO ---
        self.frame_lancamento = self.criar_card_container("🛒 LANÇAMENTO DE ITENS")
        self.frame_lancamento.grid_columnconfigure(5, weight=1) # Expande o campo de Obs

        ctk.CTkLabel(self.frame_lancamento, text="Cód/Nome:").grid(row=1, column=0, padx=5, pady=10)
        self.ent_id = ctk.CTkEntry(self.frame_lancamento, width=80, font=("Arial", 16, "bold"))
        self.ent_id.grid(row=1, column=1, padx=5)

        ctk.CTkLabel(self.frame_lancamento, text="Qtd:").grid(row=1, column=2, padx=5)
        self.ent_qtd = ctk.CTkEntry(self.frame_lancamento, width=60, font=("Arial", 16))
        self.ent_qtd.insert(0, "1")
        self.ent_qtd.bind("<FocusIn>", lambda e: self.ent_qtd.after(10, lambda: self.ent_qtd.select_range(0, 'end')))
        self.ent_qtd.grid(row=1, column=3, padx=5)

        ctk.CTkLabel(self.frame_lancamento, text="Obs:").grid(row=1, column=4, padx=5)
        self.ent_obs = ctk.CTkEntry(self.frame_lancamento)
        self.ent_obs.grid(row=1, column=5, padx=5, sticky="ew")

        self.lbl_nome_prod = ctk.CTkLabel(self.frame_lancamento, text="Produto: ---", text_color=Theme.SUCCESS, font=("Arial", 14, "italic"))
        self.lbl_nome_prod.grid(row=1, column=6, padx=20)

        self.ent_id.bind('<Return>', self.focar_qtd)
        self.ent_qtd.bind('<Return>', self.focar_obs)
        self.ent_obs.bind('<Return>', self.adicionar_item)

        # --- TABELA DE ITENS ---
        self.tree = ttk.Treeview(self.container, columns=("ID", "Produto", "Qtd", "Preço Unit", "Total", "Obs"), 
                                 show="headings", selectmode="browse", style="Treeview")
        
        # Configuração de Cabeçalhos e Larguras
        self.tree.heading("ID", text="ID")
        self.tree.heading("Produto", text="Produto")
        self.tree.heading("Qtd", text="Qtd")
        self.tree.heading("Preço Unit", text="Preço Unit")
        self.tree.heading("Total", text="Total")
        self.tree.heading("Obs", text="Observação")

        self.tree.column("ID", width=40, minwidth=40, anchor="center")          # Espaço para 2-3 dígitos
        self.tree.column("Produto", width=250, minwidth=200, anchor="w")        # Espaço para "Chocolate com Morango"
        self.tree.column("Qtd", width=50, minwidth=50, anchor="center")         # Espaço para 2 dígitos
        self.tree.column("Preço Unit", width=100, minwidth=90, anchor="center") # Espaço para 5 dígitos + R$
        self.tree.column("Total", width=100, minwidth=90, anchor="center")      # Espaço para 5 dígitos + R$
        self.tree.column("Obs", width=200, minwidth=150, anchor="w")            # Restante do espaço

        self.tree.tag_configure('oddrow', background="white")
        self.tree.tag_configure('evenrow', background="#f1f2f6")

        # Pack da tabela no que restou do espaço central
        self.tree.pack(pady=10, padx=20, fill="both", expand=True)
        
        # BINDINGS DA TABELA
        self.tree.bind("<Button-3>", self.mostrar_menu_contexto)

    def abrir_consulta_precos(self):
        pop = ctk.CTkToplevel(self)
        pop.title("Consulta de Preços")
        pop.geometry("600x550")
        pop.grab_set()
        pop.attributes("-topmost", True)

        # Centralizar popup
        pop.update_idletasks()
        w, h = 600, 550
        extra_x = (pop.winfo_screenwidth() // 2) - (w // 2)
        extra_y = (pop.winfo_screenheight() // 2) - (h // 2)
        pop.geometry(f"+{extra_x}+{extra_y}")

        main_f = ctk.CTkFrame(pop, fg_color="white")
        main_f.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(main_f, text="📋 CONSULTA DE PREÇOS", font=("Arial", 18, "bold"), text_color=Theme.PRIMARY).pack(pady=10)

        # Filtro de Busca Interno
        frame_busca = ctk.CTkFrame(main_f, fg_color="transparent")
        frame_busca.pack(fill="x", pady=5)
        ctk.CTkLabel(frame_busca, text="🔍 Buscar Produto:", font=Theme.FONT_LABEL).pack(side="left", padx=5)
        ent_busca = ctk.CTkEntry(frame_busca, placeholder_text="Digite o nome ou ID...")
        ent_busca.pack(side="left", fill="x", expand=True, padx=5)

        # Tabela de Consulta
        tree_frame = ctk.CTkFrame(main_f)
        tree_frame.pack(fill="both", expand=True, pady=10)

        cols = ("ID", "Produto", "Preço")
        tree_con = ttk.Treeview(tree_frame, columns=cols, show="headings", style="Treeview")
        tree_con.heading("ID", text="ID")
        tree_con.heading("Produto", text="Nome do Produto")
        tree_con.heading("Preço", text="Valor (R$)")
        tree_con.column("ID", width=70, anchor="center")
        tree_con.column("Produto", width=350, anchor="w")
        tree_con.column("Preço", width=100, anchor="center")
        tree_con.tag_configure('oddrow', background="white")
        tree_con.tag_configure('evenrow', background="#f1f2f6")
        tree_con.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree_con.yview)
        tree_con.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")

        def selecionar_produto(event):
            sel = tree_con.selection()
            if sel:
                # Pega o ID (primeira coluna) do item selecionado
                id_prod = tree_con.item(sel[0])['values'][0]
                self.ent_id.delete(0, 'end')
                self.ent_id.insert(0, id_prod)
                self.focar_qtd(None) # Atualiza o nome do produto e pula para a quantidade
                pop.destroy()

        tree_con.bind("<Double-1>", selecionar_produto)

        def carregar_dados(termo=""):
            for i in tree_con.get_children(): tree_con.delete(i)
            if self.db:
                if termo:
                    self.cursor.execute("SELECT id_produto, nome, preco FROM produtos WHERE nome LIKE ? OR id_produto LIKE ? ORDER BY id_produto", 
                                        (f"%{termo}%", f"%{termo}%"))
                else:
                    self.cursor.execute("SELECT id_produto, nome, preco FROM produtos ORDER BY id_produto")
                
                for i, r in enumerate(self.cursor.fetchall()):
                    tag = 'evenrow' if i % 2 == 0 else 'oddrow'
                    tree_con.insert("", "end", values=(r[0], r[1], f"R$ {r[2]:.2f}"), tags=(tag,))

        ent_busca.bind("<KeyRelease>", lambda e: carregar_dados(ent_busca.get()))
        carregar_dados()

        ctk.CTkButton(main_f, text="FECHAR (ESC)", fg_color="gray", command=pop.destroy).pack(pady=10)
        pop.bind("<Escape>", lambda e: pop.destroy())

        # Garante o foco no campo de busca após a renderização (mesmo método do fechamento)
        pop.after(200, lambda: ent_busca.focus())

    def toggle_modo_retirada(self):
        if self.modo_retirada.get():
            self.ent_bairro.configure(state="disabled", fg_color="#e0e0e0")
            self.ent_rua.configure(state="disabled", fg_color="#e0e0e0")
            self.ent_num.configure(state="disabled", fg_color="#e0e0e0")
            self.ent_comp.configure(state="disabled", fg_color="#e0e0e0")
            self.taxa_atual = 0.0
        else:
            self.ent_bairro.configure(state="normal", fg_color="white")
            self.ent_rua.configure(state="normal", fg_color="white")
            self.ent_num.configure(state="normal", fg_color="white")
            self.ent_comp.configure(state="normal", fg_color="white")

    def mostrar_menu_contexto(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            menu = tk.Menu(self, tearoff=0)
            menu.add_command(label="📝 Editar Item", command=self.editar_item_carrinho)
            menu.add_command(label="❌ Excluir Item", command=self.excluir_item_carrinho)
            self.tree.selection_set(item)
            menu.post(event.x_root, event.y_root)

    def organizar_zebra_carrinho(self):
        for i, item in enumerate(self.tree.get_children()):
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            self.tree.item(item, tags=(tag,))

    def excluir_item_carrinho(self, event=None):
        sel = self.tree.selection()
        if sel:
            for i in sel:
                self.tree.delete(i)
            self.atualizar_total()
            self.organizar_zebra_carrinho()

    def editar_item_carrinho(self, event=None):
        sel = self.tree.selection()
        if sel:
            item = sel[0]
            v = self.tree.item(item)['values']
            # v: (ID, Produto, Qtd, Preço Unit, Total, Obs)
            self.ent_id.delete(0, 'end'); self.ent_id.insert(0, v[0])
            self.ent_qtd.delete(0, 'end'); self.ent_qtd.insert(0, v[2])
            self.ent_obs.delete(0, 'end'); self.ent_obs.insert(0, v[5])
            self.tree.delete(item)
            self.atualizar_total()
            self.organizar_zebra_carrinho()
            self.focar_qtd(None) # Atualiza o label do produto e foca na Qtd

    def mostrar_tela_cardapio(self):
        self.limpar_container()
        self.atualizar_sidebar("Cardápio")
        self.registrar_atalhos("Cardápio")

        # Inicializa o estado de ordenação padrão se não existir
        if not hasattr(self, 'col_ordenacao_cardapio'):
            self.col_ordenacao_cardapio = "ID"
            self.ordem_reversa_cardapio = False

        # --- ÁREA DE CADASTRO DE PRODUTO ---
        self.frame_cad_prod = ctk.CTkFrame(self.container, fg_color="#f9f9f9", border_color="#e0e0e0", border_width=1)
        self.frame_cad_prod.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(self.frame_cad_prod, text="🍎 CADASTRO DE PRODUTO", font=("Arial", 14, "bold"), text_color="#c0392b").grid(row=0, column=0, columnspan=4, pady=(10, 5), padx=15, sticky="w")
        self.frame_cad_prod.grid_columnconfigure((0, 1, 2), weight=1)

        self.ent_id_prod = self.criar_campo(self.frame_cad_prod, "ID (Código)", 1, 0)
        self.ent_nome_prod = self.criar_campo(self.frame_cad_prod, "Nome do Produto", 1, 1)
        self.ent_cat_prod = self.criar_campo(self.frame_cad_prod, "Categoria", 1, 2)

        # Linha 2 de cadastro
        self.ent_preco_prod = self.criar_campo(self.frame_cad_prod, "Preço (R$)", 2, 0)
        self.ent_ingredientes_prod = self.criar_campo(self.frame_cad_prod, "Ingredientes (Opcional)", 2, 1)
        
        self.var_visivel_web = tk.BooleanVar(value=True)
        self.cb_visivel_web = ctk.CTkCheckBox(self.frame_cad_prod, text="Visível no Cardápio Digital", 
                                              variable=self.var_visivel_web, font=Theme.FONT_LABEL)
        self.cb_visivel_web.grid(row=2, column=2, padx=10, pady=(20, 5), sticky="w")

        # Listbox para sugestões (criada após os campos para referência)
        self.frame_sugestao = tk.Frame(self.container, bg="white", highlightbackground="#d1d1d1", highlightthickness=1)
        self.list_sugestao = tk.Listbox(self.frame_sugestao, font=("Arial", 11), borderwidth=0, highlightthickness=0)
        self.list_sugestao.pack(fill="both", expand=True)

        # BINDINGS DE NAVEGAÇÃO (Cardápio)
        self.ent_id_prod.bind('<Return>', self.buscar_produto_edicao)
        self.ent_nome_prod.bind('<Return>', lambda e: self.ent_cat_prod.focus())
        self.ent_cat_prod.bind('<Return>', self.processar_enter_categoria)
        self.ent_cat_prod.bind('<KeyRelease>', self.filtrar_categorias_sugestao)
        self.ent_preco_prod.bind('<Return>', lambda e: self.ent_ingredientes_prod.focus())
        self.ent_ingredientes_prod.bind('<Return>', lambda e: self.salvar_produto_db())

        # --- BOTÕES DE AÇÃO ---
        self.frame_acoes_prod = ctk.CTkFrame(self.container, fg_color="transparent")
        self.frame_acoes_prod.pack(pady=10, padx=20, fill="x")
        self.frame_acoes_prod.grid_columnconfigure(3, weight=1) # Empurra o filtro e o excluir para as pontas

        self.btn_salvar_prod = ctk.CTkButton(self.frame_acoes_prod, text=f"SALVAR ({self.obter_atalho('Cardápio', 'Salvar')})", fg_color="#27ae60", hover_color="#219150", 
                                             font=("Arial", 13, "bold"), command=self.salvar_produto_db)
        self.btn_salvar_prod.grid(row=0, column=0, padx=5)

        self.btn_massa_prod = ctk.CTkButton(self.frame_acoes_prod, text="📦 EDIÇÃO EM MASSA", fg_color="#34495e", 
                                             font=("Arial", 13, "bold"), command=self.abrir_edicao_em_massa)
        self.btn_massa_prod.grid(row=0, column=1, padx=5)

        self.btn_limpar_prod = ctk.CTkButton(self.frame_acoes_prod, text=f"LIMPAR ({self.obter_atalho('Cardápio', 'Limpar')})", fg_color="gray", 
                                             font=("Arial", 13, "bold"), command=self.limpar_campos_cardapio)
        self.btn_limpar_prod.grid(row=0, column=2, padx=5)

        self.btn_excluir_prod = ctk.CTkButton(self.frame_acoes_prod, text=f"EXCLUIR ({self.obter_atalho('Cardápio', 'Excluir')})", fg_color="#e74c3c", hover_color="#c0392b", 
                                              font=("Arial", 13, "bold"), command=self.excluir_produto_db)
        self.btn_excluir_prod.grid(row=0, column=6, padx=5)

        ctk.CTkLabel(self.frame_acoes_prod, text="🔍 Filtrar:", font=("Arial", 12, "bold")).grid(row=0, column=4, padx=5)
        self.cb_filtro_cat = ctk.CTkComboBox(self.frame_acoes_prod, values=["TODOS"], command=lambda _: self.atualizar_lista_produtos())
        self.cb_filtro_cat.grid(row=0, column=5, padx=5)
        self.cb_filtro_cat.set("TODOS")

        # --- TABELA DE PRODUTOS ---
        self.tree_prod = ttk.Treeview(self.container, columns=("ID", "Produto", "Categoria", "Preço"), 
                                      show="headings", selectmode="extended", style="Treeview")
        self.tree_prod.heading("ID", text="ID ↕", command=lambda: self.ordenar_coluna_cardapio("ID", False))
        self.tree_prod.heading("Produto", text="Nome do Produto ↕", command=lambda: self.ordenar_coluna_cardapio("Produto", False))
        self.tree_prod.heading("Categoria", text="Categoria ↕", command=lambda: self.ordenar_coluna_cardapio("Categoria", False))
        self.tree_prod.heading("Preço", text="Preço (R$) ↕", command=lambda: self.ordenar_coluna_cardapio("Preço", False))

        self.tree_prod.column("ID", width=100, anchor="center")
        self.tree_prod.column("Produto", width=300, anchor="w")
        self.tree_prod.column("Categoria", width=150, anchor="center")
        self.tree_prod.column("Preço", width=100, anchor="center")

        self.tree_prod.tag_configure('oddrow', background="white")
        self.tree_prod.tag_configure('evenrow', background="#f1f2f6")

        self.tree_prod.pack(pady=10, padx=20, fill="both", expand=True)
        self.tree_prod.bind("<<TreeviewSelect>>", self.preencher_campos_cardapio)

        self.atualizar_lista_produtos()

    def abrir_edicao_em_massa(self):
        selecionados = self.tree_prod.selection()
        if len(selecionados) < 2:
            messagebox.showwarning("Aviso", "Selecione pelo menos dois produtos para edição em massa.")
            return

        pop = ctk.CTkToplevel(self)
        pop.title("Edição em Massa")
        pop.geometry("400x350")
        pop.grab_set()
        pop.attributes("-topmost", True)

        main_f = ctk.CTkFrame(pop, fg_color="white")
        main_f.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(main_f, text=f"Editando {len(selecionados)} produtos", font=("Arial", 14, "bold")).pack(pady=10)

        ctk.CTkLabel(main_f, text="Nova Categoria (vazio para manter):", font=Theme.FONT_LABEL).pack(anchor="w", pady=(10, 0))
        ent_cat = ctk.CTkEntry(main_f)
        ent_cat.pack(fill="x", pady=5)

        ctk.CTkLabel(main_f, text="Novo Preço (vazio para manter):", font=Theme.FONT_LABEL).pack(anchor="w", pady=(10, 0))
        ent_preco = ctk.CTkEntry(main_f)
        ent_preco.pack(fill="x", pady=5)

        def aplicar_massa():
            nova_cat = ent_cat.get().strip()
            novo_preco = ent_preco.get().strip().replace(",", ".")
            
            updates = []
            params = []
            if nova_cat:
                # Garante que a categoria existe na tabela de categorias
                self.cursor.execute("SELECT id_categoria FROM categorias WHERE nome = ? COLLATE NOCASE", (nova_cat,))
                if not self.cursor.fetchone():
                    self.cursor.execute("INSERT INTO categorias (nome) VALUES (?)", (nova_cat,))
                updates.append("categoria = ?")
                params.append(nova_cat)
            
            if novo_preco:
                try:
                    float(novo_preco)
                    updates.append("preco = ?")
                    params.append(float(novo_preco))
                except ValueError:
                    messagebox.showerror("Erro", "Preço inválido!")
                    return

            if not updates:
                pop.destroy()
                return

            for item_id in selecionados:
                id_prod = self.tree_prod.item(item_id)['values'][0]
                self.cursor.execute(f"UPDATE produtos SET {', '.join(updates)} WHERE id_produto = ?", params + [id_prod])
            
            self.db.commit()
            self.atualizar_lista_produtos()
            pop.destroy()
            messagebox.showinfo("Sucesso", "Produtos atualizados em massa!")

        ctk.CTkButton(main_f, text="APLICAR MUDANÇAS", fg_color=Theme.SUCCESS, command=aplicar_massa).pack(pady=20, fill="x")

    def filtrar_categorias_sugestao(self, event):
        if event.keysym in ["Return", "Up", "Down", "Escape"]: return
        texto = self.ent_cat_prod.get().strip().lower()
        if not texto:
            self.frame_sugestao.place_forget()
            return

        self.cursor.execute("SELECT nome FROM categorias WHERE nome LIKE ? LIMIT 5", (f"%{texto}%",))
        sugestoes = [r[0] for r in self.cursor.fetchall()]

        if sugestoes:
            self.list_sugestao.delete(0, tk.END)
            for s in sugestoes: self.list_sugestao.insert(tk.END, s)
            
            # Força atualização para pegar coordenadas corretas
            self.update_idletasks()
            
            # Posicionamento absoluto relativo ao container principal
            x = self.ent_cat_prod.winfo_rootx() - self.container.winfo_rootx()
            y = (self.ent_cat_prod.winfo_rooty() - self.container.winfo_rooty()) + self.ent_cat_prod.winfo_height()
            
            self.frame_sugestao.place(x=x, y=y, width=self.ent_cat_prod.winfo_width(), height=120)
            self.frame_sugestao.lift()
        else:
            self.frame_sugestao.place_forget()

    def processar_enter_categoria(self, event):
        if self.frame_sugestao.winfo_ismapped():
            try:
                escolha = self.list_sugestao.get(0)
                if escolha:
                    self.ent_cat_prod.delete(0, tk.END)
                    self.ent_cat_prod.insert(0, escolha)
                self.frame_sugestao.place_forget()
            except: pass
        self.ent_preco_prod.focus()

    def ordenar_coluna_cardapio(self, col, reverse):
        # Salva o estado atual da ordenação
        self.col_ordenacao_cardapio = col
        self.ordem_reversa_cardapio = reverse

        l = [(self.tree_prod.set(k, col), k) for k in self.tree_prod.get_children('')]
        
        # Tenta converter para número se for ID ou Preço para ordenar corretamente
        if col in ["ID", "Preço"]:
            try:
                l.sort(key=lambda t: float(t[0].replace("R$ ", "").replace(",", ".")), reverse=reverse)
            except ValueError:
                l.sort(reverse=reverse)
        else:
            l.sort(reverse=reverse)

        for index, (val, k) in enumerate(l):
            self.tree_prod.move(k, '', index)
            self.tree_prod.item(k, tags=('evenrow' if index % 2 == 0 else 'oddrow',))

        # Alterna a direção da próxima ordenação
        self.tree_prod.heading(col, command=lambda: self.ordenar_coluna_cardapio(col, not reverse))

    def buscar_produto_edicao(self, event=None):
        id_p = self.ent_id_prod.get().strip()
        if id_p:
            self.cursor.execute("SELECT id_produto, nome, categoria, preco, ingredientes, visivel_web FROM produtos WHERE id_produto = ?", (id_p,))
            res = self.cursor.fetchone()
            if res:
                self.preencher_campos_com_dados(res)
                self.ent_nome_prod.focus()
            else:
                self.ent_nome_prod.focus()

    def salvar_produto_db(self):
        id_p = self.ent_id_prod.get()
        nome = self.ent_nome_prod.get()
        preco = self.ent_preco_prod.get().replace(",", ".")
        cat = self.ent_cat_prod.get().strip()
        ingredientes = self.ent_ingredientes_prod.get().strip()
        visivel = 1 if self.var_visivel_web.get() else 0

        if not id_p or not nome or not preco or not cat:
            messagebox.showwarning("Aviso", "Preencha todos os campos!")
            return

        try:
            float(preco)
            # Verifica se a categoria já existe, se não, cria.
            self.cursor.execute("SELECT id_categoria FROM categorias WHERE nome = ? COLLATE NOCASE", (cat,))
            if not self.cursor.fetchone():
                self.cursor.execute("INSERT INTO categorias (nome) VALUES (?)", (cat,))

            self.cursor.execute("INSERT OR REPLACE INTO produtos (id_produto, nome, preco, categoria, ingredientes, visivel_web) VALUES (?, ?, ?, ?, ?, ?)", 
                                (id_p, nome, preco, cat, ingredientes, visivel))
            self.db.commit()
            self.atualizar_lista_produtos()
            self.limpar_campos_cardapio()
            messagebox.showinfo("Sucesso", "Produto salvo com sucesso!")
        except ValueError:
            messagebox.showerror("Erro", "O preço deve ser um número válido!")

    def adicionar_categoria(self):
        nome_cat = self.ent_nova_cat.get().strip()
        if nome_cat:
            try:
                self.cursor.execute("INSERT INTO categorias (nome) VALUES (?)", (nome_cat,))
                self.db.commit()
                self.ent_nova_cat.delete(0, 'end')
                self.atualizar_lista_categorias()
                messagebox.showinfo("Sucesso", f"Categoria '{nome_cat}' adicionada!")
            except sqlite3.IntegrityError:
                messagebox.showwarning("Aviso", "Esta categoria já existe!")
        else:
            messagebox.showwarning("Aviso", "Digite um nome para a categoria!")

    def atualizar_lista_categorias(self):
        # Remove categorias que não estão vinculadas a nenhum produto
        self.cursor.execute("DELETE FROM categorias WHERE nome NOT IN (SELECT DISTINCT categoria FROM produtos WHERE categoria IS NOT NULL AND categoria != '')")
        self.db.commit()

        self.cursor.execute("SELECT nome FROM categorias ORDER BY nome")
        cats = [linha[0] for linha in self.cursor.fetchall()]

        # Atualiza o ComboBox de filtro alinhado aos botões
        if hasattr(self, 'cb_filtro_cat'):
            self.cb_filtro_cat.configure(values=["TODOS"] + cats)

    def excluir_produto_db(self):
        id_p = self.ent_id_prod.get()
        if not id_p:
            messagebox.showwarning("Aviso", "Selecione um produto para excluir!")
            return
        
        if messagebox.askyesno("Confirmar", f"Deseja realmente excluir o produto ID {id_p}?"):
            self.cursor.execute("DELETE FROM produtos WHERE id_produto = ?", (id_p,))
            self.db.commit()
            self.atualizar_lista_produtos()
            self.limpar_campos_cardapio()

    def atualizar_lista_produtos(self):
        for i in self.tree_prod.get_children(): self.tree_prod.delete(i)
        
        filtro = self.cb_filtro_cat.get()
        if filtro == "TODOS" or not filtro:
            self.cursor.execute("SELECT id_produto, nome, categoria, preco FROM produtos ORDER BY id_produto")
        else:
            self.cursor.execute("SELECT id_produto, nome, categoria, preco FROM produtos WHERE categoria = ? ORDER BY id_produto", (filtro,))
            
        for i, linha in enumerate(self.cursor.fetchall()):
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            self.tree_prod.insert("", "end", values=(linha[0], linha[1], linha[2] if linha[2] else "-", f"{linha[3]:.2f}"), tags=(tag,))
        
        self.atualizar_lista_categorias()

        # Reaplica a ordenação definida pelo operador (ou a padrão) após recarregar os dados
        self.ordenar_coluna_cardapio(self.col_ordenacao_cardapio, self.ordem_reversa_cardapio)

    def preencher_campos_cardapio(self, event):
        item_sel = self.tree_prod.selection()
        if item_sel:
            id_p = self.tree_prod.item(item_sel[0])['values'][0]
            self.cursor.execute("SELECT id_produto, nome, categoria, preco, ingredientes, visivel_web FROM produtos WHERE id_produto = ?", (id_p,))
            res = self.cursor.fetchone()
            if res:
                self.preencher_campos_com_dados(res)

    def preencher_campos_com_dados(self, dados):
        self.limpar_campos_cardapio()
        self.ent_id_prod.insert(0, dados[0])
        self.ent_nome_prod.insert(0, dados[1])
        self.ent_cat_prod.insert(0, dados[2] if dados[2] else "")
        self.ent_preco_prod.insert(0, f"{dados[3]:.2f}")
        self.ent_ingredientes_prod.insert(0, dados[4] if dados[4] else "")
        self.var_visivel_web.set(True if dados[5] == 1 else False)

    def limpar_campos_cardapio(self):
        self.ent_id_prod.delete(0, 'end')
        self.ent_nome_prod.delete(0, 'end')
        self.ent_preco_prod.delete(0, 'end')
        self.ent_cat_prod.delete(0, 'end')
        self.ent_ingredientes_prod.delete(0, 'end')
        self.var_visivel_web.set(True)
        if hasattr(self, 'frame_sugestao'): self.frame_sugestao.place_forget()
        self.ent_id_prod.focus()

    def mostrar_tela_taxas(self):
        self.limpar_container()
        self.atualizar_sidebar("Taxa Entrega")

        # --- ÁREA DE CADASTRO DE TAXA ---
        self.frame_cad_taxa = ctk.CTkFrame(self.container, fg_color="#f9f9f9", border_color="#e0e0e0", border_width=1)
        self.frame_cad_taxa.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(self.frame_cad_taxa, text="💰 GESTÃO DE TAXAS POR BAIRRO", font=("Arial", 14, "bold"), text_color="#c0392b").grid(row=0, column=0, columnspan=2, pady=(10, 5), padx=15, sticky="w")

        self.frame_cad_taxa.grid_columnconfigure((0, 1), weight=1)

        self.ent_nome_bairro = self.criar_campo(self.frame_cad_taxa, "Nome do Bairro", 1, 0)
        self.ent_valor_taxa = self.criar_campo(self.frame_cad_taxa, "Valor da Taxa (R$)", 1, 1)

        self.ent_nome_bairro.bind('<Return>', lambda e: self.ent_valor_taxa.focus())
        self.ent_valor_taxa.bind('<Return>', lambda e: self.salvar_taxa_db())

        # --- BOTÕES ---
        self.frame_btn_taxa = ctk.CTkFrame(self.container, fg_color="transparent")
        self.frame_btn_taxa.pack(pady=5, padx=20, fill="x")

        ctk.CTkButton(self.frame_btn_taxa, text="SALVAR TAXA", fg_color="#27ae60", command=self.salvar_taxa_db).pack(side="left", padx=5)
        ctk.CTkButton(self.frame_btn_taxa, text="EXCLUIR", fg_color="#e74c3c", command=self.excluir_taxa_db).pack(side="right", padx=5)

        # --- TABELA ---
        self.tree_taxas = ttk.Treeview(self.container, columns=("Bairro", "Taxa"), show="headings", style="Treeview")
        self.tree_taxas.heading("Bairro", text="Bairro")
        self.tree_taxas.heading("Taxa", text="Valor da Taxa")

        self.tree_taxas.tag_configure('oddrow', background="white")
        self.tree_taxas.tag_configure('evenrow', background="#f1f2f6")

        self.tree_taxas.pack(pady=10, padx=20, fill="both", expand=True)
        self.tree_taxas.bind("<<TreeviewSelect>>", self.preencher_campos_taxas)

        self.atualizar_lista_taxas()

    def salvar_taxa_db(self):
        nome = self.ent_nome_bairro.get().strip()
        valor = self.ent_valor_taxa.get().replace(",", ".")
        if nome and valor:
            try:
                self.cursor.execute("INSERT OR REPLACE INTO bairros (nome, taxa) VALUES (?, ?)", (nome, float(valor)))
                self.db.commit()
                self.ent_nome_bairro.delete(0, 'end'); self.ent_valor_taxa.delete(0, 'end')
                self.atualizar_lista_taxas()
                self.ent_nome_bairro.focus()
            except: messagebox.showerror("Erro", "Valor inválido")

    def excluir_taxa_db(self):
        nome = self.ent_nome_bairro.get()
        if nome:
            self.cursor.execute("DELETE FROM bairros WHERE nome = ?", (nome,))
            self.db.commit()
            self.atualizar_lista_taxas()
            self.ent_nome_bairro.delete(0, 'end'); self.ent_valor_taxa.delete(0, 'end')

    def atualizar_lista_taxas(self):
        for i in self.tree_taxas.get_children(): self.tree_taxas.delete(i)
        self.cursor.execute("SELECT nome, taxa FROM bairros ORDER BY nome")
        for i, r in enumerate(self.cursor.fetchall()):
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            self.tree_taxas.insert("", "end", values=(r[0], f"{r[1]:.2f}"), tags=(tag,))

    def preencher_campos_taxas(self, event):
        sel = self.tree_taxas.selection()
        if sel:
            v = self.tree_taxas.item(sel[0])['values']
            self.ent_nome_bairro.delete(0, 'end'); self.ent_nome_bairro.insert(0, v[0])
            self.ent_valor_taxa.delete(0, 'end'); self.ent_valor_taxa.insert(0, v[1])

    def buscar_taxa_bairro(self):
        bairro = self.ent_bairro.get().strip()
        self.taxa_atual = 0.0
        if not bairro:
            return

        self.cursor.execute("SELECT taxa, nome FROM bairros WHERE nome = ? COLLATE NOCASE", (bairro,))
        res = self.cursor.fetchone()
        if res:
            self.taxa_atual = res[0]
            # Atualiza o campo com a grafia correta do banco
            self.ent_bairro.delete(0, 'end'); self.ent_bairro.insert(0, res[1])
        elif self.bloquear_bairro_desconhecido:
            messagebox.showwarning("Aviso", f"O bairro '{bairro}' não está cadastrado nas Taxas de Entrega!")
            self.ent_bairro.delete(0, 'end')
            self.ent_bairro.focus()

    def mostrar_tela_estatisticas(self, tipo="ENTREGA"):
        self.limpar_container()
        self.tipo_historico_atual = tipo
        sidebar_label = "Hist. Delivery" if tipo == "ENTREGA" else "Hist. Retirada"
        self.atualizar_sidebar(sidebar_label)
        self.registrar_atalhos("Histórico")
        
        # Adicionar colunas faltantes se o banco já existir
        try:
            self.cursor.execute("ALTER TABLE pedidos ADD COLUMN subtotal REAL")
            self.cursor.execute("ALTER TABLE pedidos ADD COLUMN taxa REAL")
            self.cursor.execute("ALTER TABLE pedidos ADD COLUMN acrescimos REAL")
            self.cursor.execute("ALTER TABLE pedidos ADD COLUMN descontos REAL")
            self.cursor.execute("ALTER TABLE pedidos ADD COLUMN tipo TEXT DEFAULT 'ENTREGA'")
            self.db.commit()
        except: pass

        # --- CABEÇALHO MINIMALISTA ---
        header_frame = ctk.CTkFrame(self.container, fg_color="white")
        header_frame.pack(fill="x", padx=30, pady=(20, 10))

        title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_box.pack(side="left")

        titulo_aba = "Histórico de Delivery" if tipo == "ENTREGA" else "Histórico de Retirada"
        ctk.CTkLabel(title_box, text=titulo_aba, font=("Arial", 24, "bold"), text_color=Theme.TEXT_MAIN).pack(anchor="w")
        ctk.CTkLabel(title_box, text=f"Gerenciamento de {tipo.capitalize()}", font=("Arial", 12), text_color="gray").pack(anchor="w")

        # Card de Resumo (Destaque do Faturamento)
        summary_card = ctk.CTkFrame(header_frame, fg_color="#f8f9fa", border_width=1, border_color="#e9ecef", corner_radius=10)
        summary_card.pack(side="right", padx=10)
        
        ctk.CTkLabel(summary_card, text="TOTAL DO DIA", font=("Arial", 10, "bold"), text_color="gray").pack(padx=20, pady=(10, 0))
        self.lbl_faturamento = ctk.CTkLabel(summary_card, text="R$ 0,00", font=("Arial", 20, "bold"), text_color=Theme.SUCCESS)
        self.lbl_faturamento.pack(padx=20, pady=(0, 10))

        # --- BARRA DE FILTROS ---
        filter_bar = ctk.CTkFrame(self.container, fg_color="transparent")
        filter_bar.pack(fill="x", padx=30, pady=10)

        ctk.CTkLabel(filter_bar, text="Filtrar por data:", font=Theme.FONT_LABEL, text_color=Theme.TEXT_MAIN).pack(side="left", padx=(0, 5))

        if DateEntry:
            self.ent_filtro_data = DateEntry(filter_bar, width=12, background='white', foreground='black', borderwidth=1, date_pattern='dd/mm/yyyy')
            self.ent_filtro_data.pack(side="left", padx=5)
        else:
            self.ent_filtro_data = ctk.CTkEntry(filter_bar, width=120, placeholder_text="DD/MM/AAAA")
            self.ent_filtro_data.pack(side="left", padx=5)
            self.ent_filtro_data.insert(0, datetime.now().strftime("%d/%m/%Y"))
        
        ctk.CTkButton(filter_bar, text="Filtrar", width=100, fg_color=Theme.PRIMARY, hover_color=Theme.PRIMARY_HOVER, command=self.atualizar_lista_pedidos).pack(side="left", padx=10)
        ctk.CTkButton(filter_bar, text="Hoje", width=80, fg_color="#f1f2f6", text_color="#2f3542", hover_color="#dfe4ea", command=lambda: (self.ent_filtro_data.delete(0, 'end'), self.ent_filtro_data.insert(0, datetime.now().strftime("%d/%m/%Y")), self.atualizar_lista_pedidos())).pack(side="left")

        btn_limpar = ctk.CTkButton(filter_bar, text="Limpar Antigos", width=120, fg_color="transparent", text_color="gray", hover_color="#fee2e2", command=self.limpar_historico_antigo)
        btn_limpar.pack(side="right", padx=5)

        # --- TABELA DE PEDIDOS ---
        # Estilização da Treeview para um visual moderno
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", 
                        background="white", 
                        foreground=Theme.TEXT_MAIN, 
                        rowheight=35, 
                        fieldbackground="white", 
                        font=("Arial", 11),
                        borderwidth=0)
        style.map("Treeview", background=[('selected', Theme.PRIMARY)], foreground=[('selected', 'white')])
        
        style.configure("Treeview.Heading", 
                        font=("Arial", 11, "bold"), 
                        background="#f8f9fa", 
                        foreground="#555", 
                        relief="flat")

        self.tree_pedidos = ttk.Treeview(self.container, columns=("ID", "Cliente", "Contato", "Valor", "Horário", "RealID"), 
                                         show="headings", selectmode="browse", style="Treeview")
        # Oculta a coluna RealID que usamos internamente para identificar o pedido no banco
        self.tree_pedidos["displaycolumns"] = ("ID", "Cliente", "Contato", "Valor", "Horário")
        
        self.tree_pedidos.heading("ID", text="N° Pedido")
        self.tree_pedidos.heading("Cliente", text="Nome do Cliente")
        self.tree_pedidos.heading("Contato", text="Contato")
        self.tree_pedidos.heading("Valor", text="Valor do Pedido")
        self.tree_pedidos.heading("Horário", text="Hora do Pedido")

        self.tree_pedidos.column("ID", width=100, anchor="center")
        self.tree_pedidos.column("Cliente", width=300, anchor="w")
        self.tree_pedidos.column("Contato", width=150, anchor="center")
        self.tree_pedidos.column("Valor", width=150, anchor="center")
        self.tree_pedidos.column("Horário", width=200, anchor="center")

        # Configuração de cores alternadas (striping)
        self.tree_pedidos.tag_configure('oddrow', background="white")
        self.tree_pedidos.tag_configure('evenrow', background="#f1f2f6")

        self.tree_pedidos.pack(pady=10, padx=20, fill="both", expand=True)
        
        # --- BARRA DE AÇÕES DO HISTÓRICO ---
        action_bar = ctk.CTkFrame(self.container, fg_color="transparent")
        action_bar.pack(fill="x", padx=20, pady=10)
        action_bar.grid_columnconfigure(3, weight=1)

        btn_view = ctk.CTkButton(action_bar, text=f"👀 Visualizar ({self.obter_atalho('Histórico', 'Visualizar')})", fg_color="#34495e", command=lambda: self.visualizar_comanda_estatisticas(None))
        btn_view.grid(row=0, column=0, padx=5)

        btn_edit = ctk.CTkButton(action_bar, text=f"📝 Editar ({self.obter_atalho('Histórico', 'Editar')})", fg_color="#2980b9", command=self.editar_pedido_estatisticas)
        btn_edit.grid(row=0, column=1, padx=5)

        btn_print = ctk.CTkButton(action_bar, text=f"🖨️ Reimprimir ({self.obter_atalho('Histórico', 'Reimprimir')})", fg_color="#27ae60", command=self.reimprimir_pedido_estatisticas)
        btn_print.grid(row=0, column=2, padx=5)

        btn_del = ctk.CTkButton(action_bar, text=f"❌ Excluir ({self.obter_atalho('Histórico', 'Excluir')})", fg_color="#e74c3c", command=self.excluir_pedido_estatisticas)
        btn_del.grid(row=0, column=4, padx=5)
        
        # Inicia vazio conforme solicitado ou com o filtro aplicado
        self.atualizar_lista_pedidos()

    def atualizar_lista_pedidos(self):
        for i in self.tree_pedidos.get_children(): self.tree_pedidos.delete(i)
        data_input = self.ent_filtro_data.get()
        faturamento_total = 0.0
        try:
            data_iso = datetime.strptime(data_input, "%d/%m/%Y").strftime("%Y-%m-%d")
            if self.db:
                query = """SELECT 
                           p1.num_dia,
                           COALESCE(c.nome, 'Clien. não cadastrado'), p1.telefone_cliente, p1.total, p1.data_pedido, p1.id_pedido
                           FROM pedidos p1 LEFT JOIN clientes c ON p1.telefone_cliente = c.telefone 
                           WHERE DATE(p1.data_pedido, 'localtime') = ? AND p1.tipo = ? ORDER BY p1.id_pedido DESC"""
                self.cursor.execute(query, (data_iso, self.tipo_historico_atual))
                rows = self.cursor.fetchall()
                for i, linha in enumerate(rows):
                    tag = 'evenrow' if i % 2 == 0 else 'oddrow'
                    faturamento_total += linha[3]
                    # Tratamento robusto para formatos de data legados ou variações de timestamp
                    try:
                        # Tenta converter os primeiros 19 caracteres (formato padrão ISO)
                        dt_obj = datetime.strptime(linha[4][:19], "%Y-%m-%d %H:%M:%S")
                        dt = dt_obj.strftime("%d/%m/%Y %H:%M")
                    except:
                        dt = linha[4] # Fallback para o valor bruto caso o formato seja inesperado
                    self.tree_pedidos.insert("", "end", values=(linha[0], linha[1], linha[2], f"R$ {linha[3]:.2f}", dt, linha[5]), tags=(tag,))
                
                self.lbl_faturamento.configure(text=f"Faturamento: R$ {faturamento_total:.2f}")
        except ValueError:
            messagebox.showerror("Erro", "Formato de data inválido! Use DD/MM/AAAA")
        except Exception as e:
            # Captura outros erros, como o de coluna 'tipo' não existir ainda
            messagebox.showerror("Erro", f"Erro ao carregar pedidos: {e}\nVerifique se o banco de dados está atualizado.")
            print(f"Erro ao carregar pedidos: {e}")

    def mostrar_menu_contexto_estatisticas(self, event):
        item = self.tree_pedidos.identify_row(event.y)
        if item:
            self.tree_pedidos.selection_set(item)
            menu = tk.Menu(self, tearoff=0)
            menu.add_command(label="📝 Editar Pedido", command=self.editar_pedido_estatisticas)
            menu.add_command(label="🖨️ Reimprimir", command=self.reimprimir_pedido_estatisticas)
            menu.add_separator()
            menu.add_command(label="❌ Excluir Registro", command=self.excluir_pedido_estatisticas)
            menu.post(event.x_root, event.y_root)

    def visualizar_comanda_estatisticas(self, event):
        sel = self.tree_pedidos.selection()
        if not sel: return
        id_pedido = self.tree_pedidos.item(sel[0])['values'][5]
        
        # Buscar Detalhes
        self.cursor.execute("SELECT subtotal, taxa, acrescimos, descontos, total, data_pedido FROM pedidos WHERE id_pedido = ?", (id_pedido,))
        p = self.cursor.fetchone()
        if not p: return
        
        # Buscar Itens
        self.cursor.execute("""SELECT i.quantidade, pr.nome, i.preco_unitario, i.observacao 
                             FROM itens_pedido i JOIN produtos pr ON i.id_produto = pr.id_produto 
                             WHERE i.id_pedido = ?""", (id_pedido,))
        itens = self.cursor.fetchall()
        
        # Janela de Visualização
        win = ctk.CTkToplevel(self)
        win.title(f"Detalhes Pedido #{id_pedido}")
        win.geometry("350x600")
        win.attributes("-topmost", True)
        
        txt = tk.Text(win, font=("Courier", 10), padx=10, pady=10)
        txt.pack(fill="both", expand=True)
        
        resumo = f"PEDIDO N° {id_pedido}\n"
        resumo += f"Data: {p[5]}\n"
        resumo += "-"*30 + "\n"
        for it in itens:
            resumo += f"{it[0]}x {it[1]}\n"
            if it[3]: resumo += f"  Obs: {it[3]}\n"
        resumo += "-"*30 + "\n"
        resumo += f"Subtotal:   R$ {p[0]:.2f}\n"
        resumo += f"Taxa:       R$ {p[1]:.2f}\n"
        resumo += f"Desconto:   R$ {p[3]:.2f}\n"
        resumo += f"TOTAL:      R$ {p[4]:.2f}\n"
        
        txt.insert("1.0", resumo)
        txt.configure(state="disabled")

    def reimprimir_pedido_estatisticas(self):
        sel = self.tree_pedidos.selection()
        if not sel: return
        id_pedido = self.tree_pedidos.item(sel[0])['values'][5]
        
        # Recuperar dados para a comanda
        self.cursor.execute("SELECT subtotal, taxa, acrescimos, descontos, total, telefone_cliente, data_pedido, tipo, num_dia FROM pedidos WHERE id_pedido = ?", (id_pedido,))
        p = self.cursor.fetchone()
        vf = {'subtotal': p[0], 'taxa': p[1], 'acrescimos': p[2], 'descontos': p[3], 'total': p[4], 'tipo': p[7]}
        tel = p[5]
        data_pedido_db = p[6]
        num_dia = p[8]

        # 1. Buscar dados completos do cliente no banco (já que os campos da tela sumiram)
        self.cursor.execute("SELECT nome, telefone, rua, numero, bairro, complemento FROM clientes WHERE telefone = ?", (tel,))
        c_data = self.cursor.fetchone()
        cliente_info = {
            'nome': c_data[0], 'tel': c_data[1], 'rua': c_data[2], 'num': c_data[3], 'bairro': c_data[4], 'comp': c_data[5]
        }

        # 2. Buscar itens do pedido no banco
        self.cursor.execute("""SELECT i.id_produto, pr.nome, i.quantidade, i.preco_unitario, (i.quantidade * i.preco_unitario), i.observacao 
                             FROM itens_pedido i JOIN produtos pr ON i.id_produto = pr.id_produto 
                             WHERE i.id_pedido = ?""", (id_pedido,))
        itens_raw = self.cursor.fetchall()
        # Formata para o padrão que a função de impressão espera (mesmo formato da Treeview)
        itens_comanda = [(it[0], it[1], it[2], f"R$ {it[3]}", f"{it[4]:.2f}", it[5]) for it in itens_raw]

        # 4. Gerar e imprimir passando os dados manualmente
        self.gerar_e_imprimir_comanda(id_pedido, vf, num_dia, tipo=p[7], cliente_info=cliente_info, itens_comanda=itens_comanda)
        messagebox.showinfo("Impressão", "Pedido enviado para a impressora.")

    def editar_pedido_estatisticas(self):
        sel = self.tree_pedidos.selection()
        if not sel: return
        id_pedido = self.tree_pedidos.item(sel[0])['values'][5]
        
        if messagebox.askyesno("Editar", "Isso carregará os dados na tela de Delivery. Deseja continuar?"):
            # 1. Troca de tela
            self.mostrar_tela_delivery()
            
            # 2. Carrega Cliente
            self.cursor.execute("SELECT telefone_cliente FROM pedidos WHERE id_pedido = ?", (id_pedido,))
            tel = self.cursor.fetchone()[0]
            self.ent_tel.insert(0, tel)
            self.editando_id_pedido = id_pedido
            self.buscar_cliente(None)
            
            # 3. Carrega Itens
            self.cursor.execute("""SELECT i.id_produto, pr.nome, i.quantidade, i.preco_unitario, i.observacao 
                                 FROM itens_pedido i JOIN produtos pr ON i.id_produto = pr.id_produto 
                                 WHERE i.id_pedido = ?""", (id_pedido,))
            for it in self.cursor.fetchall():
                total = it[2] * it[3]
                self.tree.insert("", "end", values=(it[0], it[1], it[2], f"R$ {it[3]}", f"{total:.2f}", it[4]))
            
            self.atualizar_total()

    def excluir_pedido_estatisticas(self):
        sel = self.tree_pedidos.selection()
        if not sel: return
        id_pedido = self.tree_pedidos.item(sel[0])['values'][5]
        
        if messagebox.askyesno("Excluir", f"Deseja excluir permanentemente o pedido #{id_pedido}?"):
            self.cursor.execute("DELETE FROM itens_pedido WHERE id_pedido = ?", (id_pedido,))
            self.cursor.execute("DELETE FROM pedidos WHERE id_pedido = ?", (id_pedido,))
            self.db.commit()
            self.atualizar_lista_pedidos()

    def criar_campo(self, master, texto, row, col, colspan=1):
        frame = ctk.CTkFrame(master, fg_color="transparent")
        frame.grid(row=row, column=col, columnspan=colspan, padx=10, pady=5, sticky="ew")

        lbl = ctk.CTkLabel(frame, text=texto, font=Theme.FONT_LABEL, text_color="#555")
        lbl.pack(anchor="w", padx=2)
        
        ent = ctk.CTkEntry(frame, height=32, border_color="#d1d1d1")
        ent.pack(fill="x", expand=True)
        return ent

    def verificar_saida_cliente(self, event):
        """Gatilho chamado quando um campo de cliente perde o foco"""
        # Pequeno atraso para permitir que o sistema processe o novo foco antes da verificação
        self.after(100, self._validar_permanencia_area_cliente)

    def _validar_permanencia_area_cliente(self):
        """Verifica se o foco mudou para fora da seção de dados do cliente"""
        try:
            novo_foco = self.focus_get()
            if novo_foco is None: return

            # Identifica os widgets internos reais (tkinter) para comparação de foco
            entradas_reais = [w._entry for w in self.widgets_cliente]
            
            # Se o novo foco não for um dos campos de cliente, tentamos salvar
            if novo_foco not in entradas_reais:
                if hasattr(self, 'ent_tel') and self.ent_tel.winfo_exists():
                    self.confirmar_cadastro_cliente(from_focus_out=True)
        except Exception:
            pass

    def buscar_cliente(self, event):
        tel = self.ent_tel.get()
        if self.db and tel:
            widgets = [self.ent_nome, self.ent_bairro, self.ent_rua, self.ent_num, self.ent_comp]
            
            # Limpa campos antes da busca para não misturar dados
            for e in widgets:
                old_state = e.cget("state")
                e.configure(state="normal")
                e.delete(0, 'end')
                e.configure(state=old_state)
            
            self.cursor.execute("SELECT nome, bairro, rua, numero, complemento FROM clientes WHERE telefone = ?", (tel,))
            res = self.cursor.fetchone()
            if res:
                for ent, val in zip(widgets, res):
                    old_state = ent.cget("state")
                    ent.configure(state="normal")
                    ent.insert(0, val if val else "")
                    ent.configure(state=old_state)
                self.ent_id.focus()
            else:
                self.ent_nome.focus()

    def confirmar_cadastro_cliente(self, event=None, from_focus_out=False):
        tel = self.ent_tel.get().strip()
        nome = self.ent_nome.get().strip()
        
        if not tel or not nome:
            # Se o usuário apenas clicou fora e os campos essenciais estão vazios, não forçamos foco
            if not from_focus_out:
                self.ent_id.focus()
            return

        bairro = self.ent_bairro.get().strip()
        rua = self.ent_rua.get().strip()
        num = self.ent_num.get().strip()
        comp = self.ent_comp.get().strip()

        # Verifica se houve alteração ou se é um novo cliente
        self.cursor.execute("SELECT nome, bairro, rua, numero, complemento FROM clientes WHERE telefone = ?", (tel,))
        res = self.cursor.fetchone()

        houve_mudanca = False
        if not res:
            houve_mudanca = True
        else:
            dados_db = [str(x) if x is not None else "" for x in res]
            if [nome, bairro, rua, num, comp] != dados_db:
                houve_mudanca = True

        if houve_mudanca:
            if messagebox.askyesno("Salvar Cadastro", "Deseja salvar/atualizar os dados deste cliente no sistema?"):
                self.cursor.execute("""INSERT OR REPLACE INTO clientes (telefone, nome, bairro, rua, numero, complemento) 
                                     VALUES (?, ?, ?, ?, ?, ?)""", (tel, nome, bairro, rua, num, comp))
                self.db.commit()
        
        # Só transfere o foco para o lançamento de itens se o comando vier de um Enter (evento)
        # Isso evita que o cursor 'pule' para o código caso o usuário tenha clicado em outro botão propositalmente
        if not from_focus_out:
            self.ent_id.focus()

    def focar_qtd(self, event):
        id_digitado = self.ent_id.get().strip()
        if id_digitado and self.db:
            # Tenta buscar primeiro pelo ID exato para evitar que números contidos no nome do produto
            # causem uma seleção errada (ex: digitar 500 e puxar o item 153 pq o nome tem '500ml')
            self.cursor.execute("SELECT nome, preco, id_produto FROM produtos WHERE id_produto = ?", (id_digitado,))
            res = self.cursor.fetchone()

            # Se não encontrar por ID, tenta buscar por parte do nome
            if not res:
                self.cursor.execute("SELECT nome, preco, id_produto FROM produtos WHERE nome LIKE ?", (f"%{id_digitado}%",))
                res = self.cursor.fetchone()

            if res:
                self.ent_id.delete(0, 'end'); self.ent_id.insert(0, res[2]) # Garante o ID no campo
                self.lbl_nome_prod.configure(text=f"{res[0]} - R$ {res[1]:.2f}", text_color=Theme.SUCCESS)
                self.ent_qtd.focus()
            else:
                self.lbl_nome_prod.configure(text="Produto não encontrado!", text_color="red")
        else:
            self.ent_qtd.focus()

    def focar_obs(self, event): self.ent_obs.focus()

    def adicionar_item(self, event):
        id_item = self.ent_id.get()
        qtd = self.ent_qtd.get()
        obs = self.ent_obs.get()
        if not id_item or not qtd: return

        if self.db:
            self.cursor.execute("SELECT nome, preco FROM produtos WHERE id_produto = ?", (id_item,))
            res = self.cursor.fetchone()
            if res:
                nome, preco = res
                total_item = int(qtd) * float(preco)
                self.tree.insert("", "end", values=(id_item, nome, qtd, f"R$ {preco}", f"{total_item:.2f}", obs))
                self.ent_id.delete(0, 'end'); self.ent_qtd.delete(0, 'end'); self.ent_qtd.insert(0, "1"); self.ent_obs.delete(0, 'end')
                self.lbl_nome_prod.configure(text="Produto: ---")
                self.ent_id.focus()
                self.atualizar_total()
                self.organizar_zebra_carrinho()

    def atualizar_total(self):
        total_geral = 0.0
        for item in self.tree.get_children():
            valor_str = self.tree.item(item)['values'][4].replace("R$ ", "")
            total_geral += float(valor_str)
        self.lbl_total.configure(text=f"TOTAL: R$ {total_geral:.2f}")
        return total_geral

    def finalizar_pedido(self):
        if not self.tree.get_children():
            messagebox.showwarning("Aviso", "O carrinho está vazio!")
            return
        
        # Cálculo inicial
        subtotal = self.atualizar_total()
        self.buscar_taxa_bairro()

        # Popup de Fechamento
        self.pop = ctk.CTkToplevel(self)
        self.pop.title("Fechamento de Pedido")
        self.pop.geometry("400x650")
        self.pop.grab_set()
        self.pop.attributes("-topmost", True)

        main_f = ctk.CTkFrame(self.pop, fg_color="white")
        main_f.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(main_f, text="RESUMO DO PAGAMENTO", font=("Arial", 16, "bold"), text_color="#c0392b").pack(pady=10)

        def criar_campo_pop(label, valor_init):
            # Helper para selecionar tudo ao focar, igual ao campo de Qtd
            lbl = ctk.CTkLabel(main_f, text=label, font=("Arial", 12, "bold"))
            lbl.pack(anchor="w", pady=(10, 0))
            ent = ctk.CTkEntry(main_f, height=35, font=("Arial", 14))
            ent.insert(0, f"{valor_init:.2f}")
            ent.bind("<FocusIn>", lambda e, widget=ent: widget.after(10, lambda: widget.select_range(0, 'end')))
            ent.pack(fill="x")
            return ent

        self.ed_sub = criar_campo_pop("Sub-Total:", subtotal)
        self.ed_acr = criar_campo_pop("Acrecimos:", 0.0)
        self.ed_des = criar_campo_pop("Descontos:", 0.0)
        self.ed_tax = criar_campo_pop("Taxa de Entrega:", self.taxa_atual)

        # Forma de Pagamento e Troco
        ctk.CTkLabel(main_f, text="Forma de Pagamento:", font=("Arial", 12, "bold")).pack(anchor="w", pady=(10, 0))
        self.cb_pagamento = ctk.CTkComboBox(main_f, values=["Dinheiro", "Cartão Crédito", "Cartão Débito", "Pix", "Vale Refeição"], height=35)
        self.cb_pagamento.pack(fill="x")
        self.cb_pagamento.set("Dinheiro")

        self.ed_recebido = criar_campo_pop("Recebido (para troco):", subtotal + self.taxa_atual)

        self.lbl_final = ctk.CTkLabel(main_f, text=f"TOTAL: R$ {subtotal + self.taxa_atual:.2f}", font=("Arial", 20, "bold"), text_color="#27ae60")
        self.lbl_final.pack(pady=10)

        def atualizar_calculo_popup(e=None):
            try:
                def f(v): return float(v.replace(",", ".")) if v.strip() else 0.0
                total = f(self.ed_sub.get()) + f(self.ed_acr.get()) + f(self.ed_tax.get()) - f(self.ed_des.get())
                recebido = f(self.ed_recebido.get())
                self.lbl_final.configure(text=f"TOTAL: R$ {total:.2f} | Troco: R$ {max(0, recebido-total):.2f}")
            except: pass

        # Navegação Enter no Popup
        for ent in [self.ed_sub, self.ed_acr, self.ed_des, self.ed_tax, self.ed_recebido]:
            ent.bind('<KeyRelease>', atualizar_calculo_popup)
        
        self.ed_sub.bind('<Return>', lambda e: self.ed_acr.focus()); self.ed_acr.bind('<Return>', lambda e: self.ed_des.focus())
        self.ed_des.bind('<Return>', lambda e: self.ed_tax.focus()); self.ed_tax.bind('<Return>', lambda e: self.cb_pagamento.focus())
        self.cb_pagamento.bind('<Return>', lambda e: self.ed_recebido.focus())
        self.ed_recebido.bind('<Return>', lambda e: self.confirmar_e_imprimir())

        btn_confirmar = ctk.CTkButton(main_f, text="CONFIRMAR E IMPRIMIR", height=45, fg_color="#27ae60", command=self.confirmar_e_imprimir)
        btn_confirmar.pack(fill="x", pady=10)

        # Garante o foco no primeiro campo após a renderização
        self.after(200, lambda: self.ed_sub.focus())

    def confirmar_e_imprimir(self):
        try:
            self.valores_finais = {
                'subtotal': float(self.ed_sub.get().replace(",", ".")),
                'acrescimos': float(self.ed_acr.get().replace(",", ".")),
                'descontos': float(self.ed_des.get().replace(",", ".")),
                'taxa': float(self.ed_tax.get().replace(",", ".")),
                'pagamento': self.cb_pagamento.get(),
                'recebido': float(self.ed_recebido.get().replace(",", "."))
            }
            self.valores_finais['total'] = self.valores_finais['subtotal'] + self.valores_finais['acrescimos'] + self.valores_finais['taxa'] - self.valores_finais['descontos']
            
            self.pop.destroy()
            self.executar_salvamento_db()
            
        except ValueError:
            messagebox.showerror("Erro", "Verifique os valores informados!")

    def executar_salvamento_db(self):
        if not self.tree.get_children():
            messagebox.showwarning("Aviso", "O carrinho está vazio!")
            return

        id_pedido = None
        if self.db:
            tel = self.ent_tel.get()
            nome = self.ent_nome.get()
            bairro = self.ent_bairro.get()
            rua = self.ent_rua.get()
            num = self.ent_num.get()
            comp = self.ent_comp.get()

            if tel and nome:
                tipo_pedido = "RETIRADA" if self.modo_retirada.get() else "ENTREGA"
                try:
                    vf = self.valores_finais
                    if self.editando_id_pedido:
                        # 2. Atualiza o Pedido Existente em vez de criar um novo
                        self.cursor.execute("""UPDATE pedidos SET telefone_cliente=?, subtotal=?, taxa=?, acrescimos=?, descontos=?, total=?, tipo=? 
                                             WHERE id_pedido=?""", 
                                             (tel, vf['subtotal'], vf['taxa'], vf['acrescimos'], vf['descontos'], vf['total'], tipo_pedido, self.editando_id_pedido))
                        id_pedido = self.editando_id_pedido
                        # Busca o num_dia existente para a impressão
                        self.cursor.execute("SELECT num_dia FROM pedidos WHERE id_pedido = ?", (id_pedido,))
                        num_dia = self.cursor.fetchone()[0]
                        # Limpa os itens antigos para re-inserir a nova versão editada
                        self.cursor.execute("DELETE FROM itens_pedido WHERE id_pedido=?", (id_pedido,))
                    else:
                        # Lógica de Numeração
                        dia_hoje = datetime.now().strftime("%Y-%m-%d")
                        if self.tipo_numeracao == "SEQUENCIAL":
                            self.cursor.execute("""SELECT COALESCE(MAX(num_dia), 0) + 1 FROM pedidos 
                                                 WHERE DATE(data_pedido, 'localtime') = ? AND tipo = ?""", (dia_hoje, tipo_pedido))
                            num_dia = self.cursor.fetchone()[0]
                        else: # PREENCHER
                            self.cursor.execute("""SELECT num_dia FROM pedidos 
                                                 WHERE DATE(data_pedido, 'localtime') = ? AND tipo = ? 
                                                 ORDER BY num_dia ASC""", (dia_hoje, tipo_pedido))
                            existentes = {r[0] for r in self.cursor.fetchall()}
                            num_dia = 1
                            while num_dia in existentes:
                                num_dia += 1

                        # 2. Insere um Novo Pedido
                        self.cursor.execute("""INSERT INTO pedidos (telefone_cliente, subtotal, taxa, acrescimos, descontos, total, tipo, num_dia) 
                                             VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", 
                                             (tel, vf['subtotal'], vf['taxa'], vf['acrescimos'], vf['descontos'], vf['total'], tipo_pedido, num_dia))
                        id_pedido = self.cursor.lastrowid

                    # 3. Salva Itens do Pedido
                    for item_id in self.tree.get_children():
                        v = self.tree.item(item_id)['values']
                        # v: (ID, Produto, Qtd, Preço Unit, Total, Obs)
                        p_unit = str(v[3]).replace("R$ ", "").replace(",", ".")
                        self.cursor.execute("""INSERT INTO itens_pedido (id_pedido, id_produto, quantidade, preco_unitario, observacao) 
                                             VALUES (?, ?, ?, ?, ?)""", (id_pedido, v[0], v[2], float(p_unit), v[5]))
                    
                    self.db.commit()

                    # 4. Processo de Impressão / PDF
                    self.gerar_e_imprimir_comanda(id_pedido, self.valores_finais, num_dia, tipo=tipo_pedido)

                    messagebox.showinfo("Sucesso", f"Pedido finalizado com sucesso!")
                    
                    # Limpar para o próximo
                    self.limpar_tela_delivery()

                except Exception as e:
                    if self.db: self.db.rollback()
                    print(f"Erro ao salvar cliente: {e}")
                    messagebox.showerror("Erro", f"Erro ao processar pedido: {e}")
            else:
                messagebox.showwarning("Aviso", "Informe Nome e Telefone do cliente!")

    def limpar_tela_delivery(self):
        for ent in [self.ent_tel, self.ent_nome, self.ent_bairro, self.ent_rua, self.ent_num, self.ent_comp]:
            ent.delete(0, 'end')
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.lbl_total.configure(text="TOTAL: R$ 0,00")
        self.editando_id_pedido = None
        self.ent_tel.focus()

    def gerar_e_imprimir_comanda(self, id_pedido, vf, num_dia, tipo=None, cliente_info=None, itens_comanda=None):
        if not WIN32_PRINTER_AVAILABLE:
            messagebox.showerror("Erro", "Recursos de impressão não disponíveis neste sistema.")
            return

        config = {
            'largura_papel': self.largura_papel,
            'vis_cabecalho': self.vis_cabecalho, 'vis_pedido': self.vis_pedido,
            'vis_cliente': self.vis_cliente, 'vis_itens': self.vis_itens,
            'vis_totais': self.vis_totais, 'vis_pagamento': self.vis_pagamento,
            'tam_cabecalho': self.tam_cabecalho, 'tam_pedido': self.tam_pedido,
            'tam_endereco': self.tam_endereco, 'tam_itens': self.tam_itens,
            'tam_valores': self.tam_valores, 'tam_pagamento': self.tam_pagamento,
            'printer_name': self.impressora_selecionada if self.impressora_selecionada != "Nenhuma" else None,
            'num_vias': self.num_vias
        }
        pedido_info = {'num_dia': num_dia, 'tipo': tipo, 'valores': vf}
        empresa_info = {'nome': self.nome_empresa, 'fone': self.fone_empresa}
        
        if cliente_info is None:
            cliente_info = {
                'nome': self.ent_nome.get(), 'tel': self.ent_tel.get(), 'rua': self.ent_rua.get(), 
                'num': self.ent_num.get(), 'bairro': self.ent_bairro.get(), 'comp': self.ent_comp.get()
            }
        
        if itens_comanda is None:
            itens_comanda = [self.tree.item(item_id)['values'] for item_id in self.tree.get_children()]

        # Delega a execução para o PrinterManager (Módulo printer.py)
        if not PrinterManager.imprimir_comanda(config, pedido_info, cliente_info, itens_comanda, empresa_info):
            messagebox.showerror("Erro de Impressão", "Falha ao processar o envio para a impressora.")

    def mostrar_tela_configuracoes(self):
        self.limpar_container()
        self.atualizar_sidebar("Configurações")

        # Criar frame rolável para organizar as configurações
        self.scroll_config = ctk.CTkScrollableFrame(self.container, fg_color="transparent")
        self.scroll_config.pack(fill="both", expand=True)

        # --- SEÇÃO 1: DADOS DO ESTABELECIMENTO ---
        frame_empresa = self.criar_card_container("🏪 DADOS DO ESTABELECIMENTO", parent=self.scroll_config)
        frame_empresa.grid_columnconfigure((0, 1), weight=1)
        
        self.ent_conf_nome = self.criar_campo(frame_empresa, "Nome da Empresa (Cabeçalho)", 1, 0)
        self.ent_conf_nome.insert(0, self.nome_empresa)
        
        self.ent_conf_fone = self.criar_campo(frame_empresa, "Telefone de Contato", 1, 1)
        self.ent_conf_fone.insert(0, self.fone_empresa)
        
        self.ent_conf_end = self.criar_campo(frame_empresa, "Endereço Completo", 2, 0, colspan=2)
        self.ent_conf_end.insert(0, self.end_empresa)

        # --- SEÇÃO 1.1: CAMINHO DOS DADOS ---
        frame_data_path = self.criar_card_container("🗄️ CAMINHO DOS DADOS", parent=self.scroll_config)
        frame_data_path.grid_columnconfigure(0, weight=1)
        
        self.ent_data_dir = self.criar_campo(frame_data_path, "Pasta de Dados (Banco e Imagens):", 1, 0)
        self.ent_data_dir.insert(0, self.data_dir)
        self.ent_data_dir.configure(state="readonly") # Apenas leitura, para alterar use o botão
        
        ctk.CTkButton(frame_data_path, text="Procurar Pasta", command=self.browse_data_dir).grid(row=1, column=1, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(frame_data_path, text="Atenção: Mudar esta pasta requer reiniciar o programa e mover os arquivos manualmente.", font=("Arial", 10, "italic")).grid(row=2, column=0, columnspan=2, padx=15, pady=5, sticky="w")

        self.var_bloquear_bairro = tk.BooleanVar(value=self.bloquear_bairro_desconhecido)
        self.cb_bloquear_bairro = ctk.CTkSwitch(frame_empresa, text="Bloquear bairros não cadastrados", variable=self.var_bloquear_bairro, font=Theme.FONT_LABEL)
        self.cb_bloquear_bairro.grid(row=3, column=0, columnspan=2, padx=15, pady=10, sticky="w")

        # --- SEÇÃO 1.2: LÓGICA DE NUMERAÇÃO ---
        frame_num = self.criar_card_container("🔢 LÓGICA DE NUMERAÇÃO DIÁRIA", parent=self.scroll_config)
        self.var_tipo_num = tk.StringVar(value=self.tipo_numeracao)
        
        rb1 = ctk.CTkRadioButton(frame_num, text="Sequencial (Ex: 1, 2, 3, 4, 5... mesmo se apagar o 2)", 
                                 variable=self.var_tipo_num, value="SEQUENCIAL")
        rb1.grid(row=1, column=0, sticky="w", padx=15, pady=5)
        
        rb2 = ctk.CTkRadioButton(frame_num, text="Preecher Gaps (Ex: se apagar o 2, o próximo será 2)", 
                                 variable=self.var_tipo_num, value="PREENCHER")
        rb2.grid(row=2, column=0, sticky="w", padx=15, pady=10)

        # --- SEÇÃO 1.3: ACESSO WEB ---
        frame_web = self.criar_card_container("🌐 ACESSO WEB E MOBILE", parent=self.scroll_config)
        
        self.var_menu_web = tk.BooleanVar(value=self.webapp_menu_enabled)
        ctk.CTkSwitch(frame_web, text="Habilitar Cardápio Digital (Clientes)", 
                      variable=self.var_menu_web).grid(row=1, column=0, padx=15, pady=5, sticky="w")
        
        self.var_admin_web = tk.BooleanVar(value=self.webapp_admin_enabled)
        ctk.CTkSwitch(frame_web, text="Habilitar Painel Administrativo Web (Operador)", 
                      variable=self.var_admin_web).grid(row=2, column=0, padx=15, pady=5, sticky="w")
        
        links = f"Cardápio: http://{self.ip_local}:{WEB_SERVER_PORT}\n"
        links += f"Painel Admin: http://{self.ip_local}:{WEB_SERVER_PORT}/admin"
        ctk.CTkLabel(frame_web, text=links, font=("Consolas", 10), text_color=Theme.ACCENT, justify="left").grid(row=3, column=0, padx=15, pady=10, sticky="w")

        # --- SEÇÃO 2: CONFIGURAÇÕES DE IMPRESSÃO ---
        frame_print = self.criar_card_container("🖨️ CONFIGURAÇÕES DE IMPRESSÃO", parent=self.scroll_config)
        frame_print.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame_print, text="Impressora Selecionada:", font=Theme.FONT_LABEL).grid(row=1, column=0, padx=15, pady=10, sticky="w")
        
        impressoras_disponiveis = ["Nenhuma"]
        if WIN32_AVAILABLE:
            impressoras_disponiveis = PrinterManager.listar_impressoras()
        else:
            messagebox.showwarning("Aviso", "Módulo 'win32print' não disponível. A seleção de impressora não funcionará.")

        self.cb_impressora = ctk.CTkComboBox(frame_print, values=impressoras_disponiveis, width=300)
        self.cb_impressora.grid(row=1, column=1, padx=5, pady=10, sticky="ew")

        if self.impressora_selecionada and self.impressora_selecionada in impressoras_disponiveis:
            self.cb_impressora.set(self.impressora_selecionada)
        else:
            self.cb_impressora.set("Nenhuma")

        ctk.CTkLabel(frame_print, text="Número de Vias:", font=Theme.FONT_LABEL).grid(row=2, column=0, padx=15, pady=10, sticky="w")
        self.ent_conf_vias = ctk.CTkEntry(frame_print, width=80)
        self.ent_conf_vias.grid(row=2, column=1, padx=5, pady=10, sticky="w")
        self.ent_conf_vias.insert(0, str(self.num_vias))

        # Botão de ajustes movido para cá para melhor organização
        btn_cfg_print = ctk.CTkButton(frame_print, text="⚙️ AJUSTES DE TAMANHO E PAPEL", 
                                      fg_color="#34495e", command=self.abrir_config_impressora)
        btn_cfg_print.grid(row=3, column=0, columnspan=2, padx=15, pady=15, sticky="w")

        # --- SEÇÃO 3: ATALHOS DE TECLADO ---
        frame_keys = self.criar_card_container("⌨️ ATALHOS DE TECLADO", parent=self.scroll_config)
        frame_keys.grid_columnconfigure((1, 3, 5), weight=1)
        
        self.ents_atalhos = {}
        
        row_idx = 1
        for tela, funcoes in self.atalhos_default.items():
            ctk.CTkLabel(frame_keys, text=f"{tela}:", font=Theme.FONT_LABEL).grid(row=row_idx, column=0, padx=15, pady=10, sticky="w")
            col_idx = 1
            for func, tecla_padrao in funcoes.items():
                ctk.CTkLabel(frame_keys, text=f"{func}:", font=("Arial", 10)).grid(row=row_idx, column=col_idx, padx=5, sticky="e")
                
                tecla_atual = self.obter_atalho(tela, func)
                ent = ctk.CTkEntry(frame_keys, width=80)
                ent.insert(0, tecla_atual)
                ent.grid(row=row_idx, column=col_idx+1, padx=5, pady=5, sticky="w")
                # Vincula a captura automática de tecla
                ent.bind("<Key>", lambda e, widget=ent: self.capturar_tecla_atalho(e, widget))
                
                self.ents_atalhos[f"{tela}_{func}"] = ent
                col_idx += 2
                if col_idx > 5:
                    col_idx = 1
                    row_idx += 1
            row_idx += 1

        ctk.CTkLabel(frame_keys, text="Dica: Clique no campo e pressione a tecla desejada. Use Backspace para limpar.", font=("Arial", 10, "italic")).grid(row=row_idx, column=0, columnspan=6, padx=15, pady=5, sticky="w")

        # --- SEÇÃO 3: ORDEM DO CARDÁPIO DIGITAL ---
        frame_ordem_web = self.criar_card_container("🎨 ORDEM DAS CATEGORIAS (MOBILE)", parent=self.scroll_config)
        frame_ordem_web.grid_columnconfigure(0, weight=1)
        
        f_ordem = ctk.CTkFrame(frame_ordem_web, fg_color="transparent")
        f_ordem.grid(row=1, column=0, padx=15, pady=(5, 15), sticky="ew")
        
        self.tree_ordem_cat = ttk.Treeview(f_ordem, columns=("Nome"), show="headings", height=5, style="Treeview")
        self.tree_ordem_cat.heading("Nome", text="Arraste ou use as setas para organizar a exibição no celular")
        self.tree_ordem_cat.pack(side="left", fill="x", expand=True)
        
        self.tree_ordem_cat.tag_configure('oddrow', background="white")
        self.tree_ordem_cat.tag_configure('evenrow', background="#f1f2f6")

        f_btns_cat = ctk.CTkFrame(f_ordem, fg_color="transparent")
        f_btns_cat.pack(side="left", padx=5)
        
        ctk.CTkButton(f_btns_cat, text="MOVER PARA CIMA ▲", font=("Arial", 10, "bold"), width=140, height=35, fg_color="#34495e", command=lambda: self.mover_categoria_ordem(-1)).pack(pady=2)
        ctk.CTkButton(f_btns_cat, text="MOVER PARA BAIXO ▼", font=("Arial", 10, "bold"), width=140, height=35, fg_color="#34495e", command=lambda: self.mover_categoria_ordem(1)).pack(pady=2)

        self.atualizar_tree_ordem_categorias()

        # Botão Salvar Geral - Fixo ao final
        btn_salvar_tudo = ctk.CTkButton(self.scroll_config, text="💾 SALVAR TODAS AS CONFIGURAÇÕES", 
                                        fg_color=Theme.SUCCESS, hover_color="#219150", 
                                        height=55, font=("Arial", 16, "bold"),
                                        command=self.salvar_todas_configs)
        btn_salvar_tudo.pack(pady=25, padx=20, fill="x")

    def atualizar_tree_ordem_categorias(self):
        for i in self.tree_ordem_cat.get_children(): self.tree_ordem_cat.delete(i)
        self.cursor.execute("SELECT nome FROM categorias ORDER BY ordem, nome")
        for i, r in enumerate(self.cursor.fetchall()):
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            self.tree_ordem_cat.insert("", "end", values=(r[0],), tags=(tag,))

    def mover_categoria_ordem(self, direcao):
        sel = self.tree_ordem_cat.selection()
        if not sel: return
        idx = self.tree_ordem_cat.index(sel[0])
        novo_idx = idx + direcao
        if 0 <= novo_idx < len(self.tree_ordem_cat.get_children()):
            self.tree_ordem_cat.move(sel[0], "", novo_idx)
            for i, item in enumerate(self.tree_ordem_cat.get_children()):
                self.tree_ordem_cat.item(item, tags=('evenrow' if i % 2 == 0 else 'oddrow',))

    def salvar_ordem_categorias_db(self):
        for i, item_id in enumerate(self.tree_ordem_cat.get_children()):
            nome = self.tree_ordem_cat.item(item_id)['values'][0]
            self.cursor.execute("UPDATE categorias SET ordem = ? WHERE nome = ?", (i, nome))
        self.db.commit()

    def abrir_config_impressora(self):
        pop = ctk.CTkToplevel(self)
        pop.title("Ajustes de Impressão")
        pop.geometry("480x650")
        pop.grab_set()
        pop.attributes("-topmost", True)

        f_ajustes = ctk.CTkScrollableFrame(pop, fg_color="white", label_text="Configurações de Layout")
        f_ajustes.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(f_ajustes, text="Largura do Papel (mm):", font=Theme.FONT_LABEL).pack(anchor="w", padx=10, pady=(5, 0))
        ed_largura = ctk.CTkEntry(f_ajustes)
        ed_largura.insert(0, str(self.largura_papel))
        ed_largura.pack(fill="x", padx=10, pady=(0, 15))

        sections = [
            ("Cabeçalho", "cabecalho", self.vis_cabecalho, self.tam_cabecalho),
            ("Dados Pedido", "pedido", self.vis_pedido, self.tam_pedido),
            ("Dados Cliente", "cliente", self.vis_cliente, self.tam_endereco),
            ("Lista de Itens", "itens", self.vis_itens, self.tam_itens),
            ("Totais", "totais", self.vis_totais, self.tam_valores),
            ("Pagamento", "pagamento", self.vis_pagamento, self.tam_pagamento)
        ]

        switches, segs = {}, {}
        tam_opts = ["Padrão", "Alt. Dupla", "Larg. Dupla", "Grande", "Extra"]

        for label, key, vis, tam in sections:
            frame = ctk.CTkFrame(f_ajustes, fg_color="transparent")
            frame.pack(fill="x", pady=10)
            
            sw = ctk.CTkSwitch(frame, text=f"Imprimir {label}", font=Theme.FONT_LABEL)
            if vis: sw.select()
            sw.pack(anchor="w", padx=10)
            switches[key] = sw

            sg = ctk.CTkSegmentedButton(frame, values=tam_opts)
            sg.set(tam_opts[tam])
            sg.pack(fill="x", padx=10, pady=5)
            segs[key] = sg

        f_botoes = ctk.CTkFrame(pop, fg_color="transparent")
        f_botoes.pack(fill="x", pady=20)

        def aplicar_ajustes():
            mapa = {opt: i for i, opt in enumerate(tam_opts)}
            try: self.largura_papel = int(ed_largura.get())
            except: pass
            
            self.vis_cabecalho, self.vis_pedido = switches['cabecalho'].get(), switches['pedido'].get()
            self.vis_cliente, self.vis_itens = switches['cliente'].get(), switches['itens'].get()
            self.vis_totais, self.vis_pagamento = switches['totais'].get(), switches['pagamento'].get()
            
            self.tam_cabecalho, self.tam_pedido = mapa[segs['cabecalho'].get()], mapa[segs['pedido'].get()]
            self.tam_endereco, self.tam_itens = mapa[segs['cliente'].get()], mapa[segs['itens'].get()]
            self.tam_valores, self.tam_pagamento = mapa[segs['totais'].get()], mapa[segs['pagamento'].get()]
            
            self.salvar_todas_configs()
            pop.destroy()

        ctk.CTkButton(f_botoes, text="🖨️ IMPRIMIR TESTE", fg_color="#34495e", command=lambda: self.imprimir_pagina_teste(ed_largura, switches, segs)).pack(side="left", padx=10, expand=True)
        ctk.CTkButton(f_botoes, text="APLICAR E SALVAR", fg_color=Theme.SUCCESS, command=aplicar_ajustes).pack(side="left", padx=10, expand=True)

    def imprimir_pagina_teste(self, ed_largura, switches, segs):
        m = {"Padrão": 0, "Alt. Dupla": 1, "Larg. Dupla": 2, "Grande": 3, "Extra": 4}
        try: l = int(ed_largura.get())
        except: l = 80
        
        c = {
            'largura_papel': l,
            'vis_cabecalho': switches['cabecalho'].get(), 'vis_pedido': switches['pedido'].get(),
            'vis_cliente': switches['cliente'].get(), 'vis_itens': switches['itens'].get(),
            'vis_totais': switches['totais'].get(), 'vis_pagamento': switches['pagamento'].get(),
            'tam_cabecalho': m[segs['cabecalho'].get()], 'tam_pedido': m[segs['pedido'].get()],
            'tam_endereco': m[segs['cliente'].get()], 'tam_itens': m[segs['itens'].get()],
            'tam_valores': m[segs['totais'].get()], 'tam_pagamento': m[segs['pagamento'].get()],
            'printer_name': self.impressora_selecionada if self.impressora_selecionada != "Nenhuma" else None,
            'num_vias': 1
        }

        vf = {'subtotal': 15.0, 'taxa': 5.0, 'acrescimos': 0.0, 'descontos': 0.0, 'total': 20.0, 'recebido': 50.0, 'pagamento': 'DINHEIRO'}
        cliente = {'nome': 'CLIENTE TESTE IMPRESSÃO', 'tel': '(00) 00000-0000', 'rua': 'RUA DE TESTE EQUIPAMENTO', 'num': '123', 'bairro': 'BAIRRO EXEMPLO', 'comp': 'LOJA 01'}
        itens = [
            (1, "PRODUTO TESTE 01", 2, "R$ 5.00", "10.00", "Sem cebola"),
            (2, "PRODUTO TESTE 02", 1, "R$ 5.00", "5.00", "")
        ]
        p_info = {'num_dia': 1, 'tipo': 'ENTREGA', 'valores': vf}
        e_info = {'nome': self.nome_empresa, 'fone': self.fone_empresa}
        
        if not PrinterManager.imprimir_comanda(c, p_info, cliente, itens, e_info):
            messagebox.showerror("Erro", "Falha ao imprimir teste.")

    def salvar_todas_configs(self):
        old_data_dir = self.data_dir
        new_data_dir = self.ent_data_dir.get()

        data_dir_changed = (old_data_dir != new_data_dir)
        escolha = None
        if data_dir_changed:
            escolha = self.pedir_escolha_migracao(old_data_dir, new_data_dir)
            if escolha == "CANCELAR":
                return

        try:
            configs = {
                'nome_empresa': self.ent_conf_nome.get(),
                'fone_empresa': self.ent_conf_fone.get(),
                'end_empresa': self.ent_conf_end.get(),
                'num_vias': self.ent_conf_vias.get(),
                'impressora_selecionada': self.cb_impressora.get(),
                'largura_papel': str(self.largura_papel),
                'tam_cabecalho': str(self.tam_cabecalho),
                'tam_pedido': str(self.tam_pedido),
                'tam_endereco': str(self.tam_endereco),
                'tam_itens': str(self.tam_itens),
                'tam_valores': str(self.tam_valores),
                'tam_pagamento': str(self.tam_pagamento),
                'vis_cabecalho': str(self.vis_cabecalho),
                'vis_pedido': str(self.vis_pedido),
                'vis_cliente': str(self.vis_cliente),
                'vis_itens': str(self.vis_itens),
                'vis_totais': str(self.vis_totais),
                'vis_pagamento': str(self.vis_pagamento),
                'bloquear_bairro': str(self.var_bloquear_bairro.get()),
                'data_dir': new_data_dir,
                'tipo_numeracao': self.var_tipo_num.get(),
                'webapp_menu_enabled': str(self.var_menu_web.get()),
                'webapp_admin_enabled': str(self.var_admin_web.get()),
            }
            
            # Salvar Atalhos e Validar duplicatas na mesma tela
            for tela in self.atalhos_default.keys():
                teclas_tela = []
                for func in self.atalhos_default[tela].keys():
                    chave_ent = f"{tela}_{func}"
                    valor = self.ents_atalhos[chave_ent].get().strip()
                    if valor:
                        if valor in teclas_tela:
                            messagebox.showerror("Erro de Atalho", f"A tecla '{valor}' está duplicada na tela {tela}!")
                            return
                        teclas_tela.append(valor)
                    
                    chave_db = f"atalho_{tela}_{func}"
                    configs[chave_db] = valor

            if not data_dir_changed:
                # Se o caminho não mudou, apenas salva no banco atual
                for chave, valor in configs.items():
                    self.cursor.execute("INSERT OR REPLACE INTO config (chave, valor) VALUES (?, ?)", (chave, valor))
                self.db.commit()
            else:
                # Se mudou, precisamos trocar a conexão de forma segura
                if self.db:
                    self.db.close()
                    self.db = None
                
                if escolha == "MOVER":
                    try:
                        os.makedirs(new_data_dir, exist_ok=True)
                        # Migração do Banco de Dados
                        db_origem = os.path.join(old_data_dir, "delivery.db")
                        db_destino = os.path.join(new_data_dir, "delivery.db")
                        if os.path.exists(db_origem):
                            if os.path.exists(db_destino): os.remove(db_destino)
                            shutil.move(db_origem, db_destino)
                        
                        # Migração dos Assets (Logo)
                        assets_origem = os.path.join(old_data_dir, "assets")
                        assets_destino = os.path.join(new_data_dir, "assets")
                        if os.path.exists(assets_origem):
                            if os.path.exists(assets_destino):
                                for f in os.listdir(assets_origem):
                                    shutil.move(os.path.join(assets_origem, f), os.path.join(assets_destino, f))
                                os.rmdir(assets_origem)
                            else:
                                shutil.move(assets_origem, assets_destino)
                        
                        # Atualiza o caminho da logo em memória
                        if self.logo_path:
                            self.logo_path = self.logo_path.replace(old_data_dir, new_data_dir)
                            configs['logo_path'] = self.logo_path
                    except Exception as e:
                        messagebox.showerror("Erro na Migração", f"Erro ao mover arquivos: {e}")

                # Atualiza a variável de diretório e reconecta
                self.data_dir = new_data_dir
                os.makedirs(self.data_dir, exist_ok=True)
                
                if escolha == "NOVO":
                    db_destino = os.path.join(self.data_dir, "delivery.db")
                    if os.path.exists(db_destino):
                        try: os.remove(db_destino)
                        except: pass

                # Inicializa DatabaseManager (que já cria tabelas e aplica migrações)
                self.db_manager = DatabaseManager(os.path.join(self.data_dir, "delivery.db"))
                self.db = self.db_manager.conn
                self.cursor = self.db_manager.cursor
                
                # Persiste as configurações atuais no novo banco de dados
                for chave, valor in configs.items():
                    self.cursor.execute("INSERT OR REPLACE INTO config (chave, valor) VALUES (?, ?)", (chave, valor))
                self.db.commit()

            self.salvar_ordem_categorias_db()
            # Atualiza variáveis locais
            self.nome_empresa = configs['nome_empresa']
            self.fone_empresa = configs['fone_empresa']
            self.end_empresa = configs['end_empresa']
            self.num_vias = int(configs['num_vias']) if configs['num_vias'].isdigit() else 1
            self.impressora_selecionada = None if configs['impressora_selecionada'] == "Nenhuma" else configs['impressora_selecionada']
            self.bloquear_bairro_desconhecido = (configs['bloquear_bairro'] == 'True')
            self.tipo_numeracao = configs['tipo_numeracao']
            self.webapp_menu_enabled = self.var_menu_web.get()
            self.webapp_admin_enabled = self.var_admin_web.get()

            # Atualiza os dicionários do servidor web em tempo real
            if hasattr(self, 'server_config'):
                self.server_config['menu_enabled'] = self.webapp_menu_enabled
                self.server_config['admin_enabled'] = self.webapp_admin_enabled
            
            if hasattr(self, 'server_info'):
                self.server_info.update({
                    'nome': self.nome_empresa,
                    'fone': self.fone_empresa,
                    'end': self.end_empresa,
                    'logo_path': self.logo_path
                })

            # Atualiza o dicionário de atalhos em memória
            for k, v in configs.items():
                if k.startswith("atalho_"):
                    p = k.split("_")
                    self.atalhos_usuario.setdefault(p[1], {})[p[2]] = v
            
            messagebox.showinfo("Sucesso", "Configurações aplicadas! Reinicie para surtir efeito total no servidor.")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao salvar: {e}")

    def limpar_historico_antigo(self):
        if messagebox.askyesno("Atenção", "Deseja excluir TODOS os pedidos de dias anteriores?"):
            if not self.db:
                messagebox.showerror("Erro", "Banco de dados não conectado.")
                return
            if not self.cursor:
                messagebox.showerror("Erro", "Cursor do banco de dados não disponível.")
            try:
                # Deleta itens primeiro por causa da FK
                self.cursor.execute("DELETE FROM itens_pedido WHERE id_pedido IN (SELECT id_pedido FROM pedidos WHERE DATE(data_pedido, 'localtime') < DATE('now', 'localtime'))")
                self.cursor.execute("DELETE FROM pedidos WHERE DATE(data_pedido, 'localtime') < DATE('now', 'localtime')")
                self.db.commit()
                self.atualizar_lista_pedidos()
                messagebox.showinfo("Sucesso", "Histórico antigo removido!")
            except Exception as e:
                print(e)

    def browse_data_dir(self):
        new_dir = filedialog.askdirectory(initialdir=self.data_dir)
        if new_dir:
            self.ent_data_dir.configure(state="normal"); self.ent_data_dir.delete(0, 'end'); self.ent_data_dir.insert(0, new_dir); self.ent_data_dir.configure(state="readonly")

    def pedir_escolha_migracao(self, old_dir, new_dir):
        """Exibe diálogo customizado para escolha de migração de dados."""
        res = {"val": "CANCELAR"}
        
        pop = ctk.CTkToplevel(self)
        pop.title("Configuração de Dados")
        pop.geometry("480x420")
        pop.grab_set()
        pop.attributes("-topmost", True)
        
        # Centralizar popup
        pop.update_idletasks()
        x = (pop.winfo_screenwidth() // 2) - (480 // 2)
        y = (pop.winfo_screenheight() // 2) - (420 // 2)
        pop.geometry(f"+{x}+{y}")

        main_f = ctk.CTkFrame(pop, fg_color="white")
        main_f.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(main_f, text="MUDANÇA DE PASTA DE DADOS", font=("Arial", 16, "bold"), text_color=Theme.PRIMARY).pack(pady=10)
        
        info = f"Origem: {old_dir}\nDestino: {new_dir}\n\nO que deseja fazer com as informações do sistema?"
        ctk.CTkLabel(main_f, text=info, font=("Arial", 11), justify="left", wraplength=400).pack(pady=10)

        def definir_escolha(v):
            res["val"] = v
            pop.destroy()

        ctk.CTkButton(main_f, text="Mover Banco de Dados Atual", height=45, fg_color=Theme.PRIMARY, 
                      command=lambda: definir_escolha("MOVER")).pack(fill="x", pady=5)
        
        ctk.CTkButton(main_f, text="Manter Banco de Dados Existente", height=45, fg_color="#34495e", 
                      command=lambda: definir_escolha("MANTER")).pack(fill="x", pady=5)
        
        ctk.CTkButton(main_f, text="Criar Novo Banco de Dados", height=45, fg_color="#e74c3c", 
                      command=lambda: definir_escolha("NOVO")).pack(fill="x", pady=5)

        ctk.CTkButton(main_f, text="Cancelar", height=35, fg_color="gray", 
                      command=lambda: definir_escolha("CANCELAR")).pack(fill="x", pady=(15, 0))

        self.wait_window(pop)
        return res["val"]

if __name__ == "__main__":
    app = GestorDelivery()
    app.mainloop()