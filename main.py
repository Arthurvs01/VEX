import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import textwrap
import sqlite3
import os
import shutil
import time
from datetime import datetime
from PIL import Image, ImageDraw, ImageOps

# Biblioteca para Calendário
try:
    from tkcalendar import DateEntry
except ImportError:
    DateEntry = None

try:
    import win32print
    import win32api
    WIN32_PRINTER_AVAILABLE = True
except ImportError:
    win32print = None
    win32api = None
    WIN32_PRINTER_AVAILABLE = False

# --- CONFIGURAÇÃO DE ESTILO PADRONIZADO ---
ctk.set_appearance_mode("light")

class Theme:
    PRIMARY = "#c0392b"      # Vermelho principal
    PRIMARY_HOVER = "#a93226"
    SUCCESS = "#27ae60"      # Verde sucesso
    BG_CARD = "#f9f9f9"      # Fundo dos cards
    BORDER = "#e0e0e0"       # Cor das bordas
    TEXT_MAIN = "#2c3e50"    # Texto principal
    FONT_H1 = ("Arial", 16, "bold")
    FONT_H2 = ("Arial", 14, "bold")
    FONT_LABEL = ("Arial", 11, "bold")

class GestorDelivery(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.sidebar_expandido = True
        self.logo_path = None
        self.taxa_atual = 0.0
        self.tipo_historico_atual = "ENTREGA"
        self.impressora_selecionada = None # Armazena a impressora configurada
        
        # Configurações Padrão
        self.nome_empresa = "MINHA EMPRESA"
        self.fone_empresa = "(00) 0000-0000"
        self.end_empresa = ""
        self.num_vias = 1

        # Configurações de Impressão Avançadas
        self.largura_papel = 80
        self.tam_cabecalho = 2 # Índice 2 = Médio (14pt)
        self.tam_endereco = 2  # Índice 2 = Médio (10pt)
        self.tam_itens = 2     # Índice 2 = Médio (9pt)
        self.tam_valores = 2   # Índice 2 = Médio (9pt)

        self.editando_id_pedido = None
        self.title("VEX - Gestor de Comandas")

        # Configuração de Janela: Centralizar e Iniciar Maximizada
        largura_tela = self.winfo_screenwidth()
        altura_tela = self.winfo_screenheight()
        
        # Define o tamanho da janela como 80% da tela para manter a proporção (formato)
        largura_janela = int(largura_tela * 0.8)
        altura_janela = int(altura_tela * 0.8)

        pos_x = (largura_tela // 2) - (largura_janela // 2)
        pos_y = (altura_tela // 2) - (altura_janela // 2)
        
        self.geometry(f"{largura_janela}x{altura_janela}+{pos_x}+{pos_y}")
        self.after(0, lambda: self.state('zoomed'))

        # Atalhos de Teclado Globais para Navegação
        self.bind("<Up>", self.navegar_teclado)
        self.bind("<Down>", self.navegar_teclado)
        self.bind("<Left>", self.navegar_teclado)
        self.bind("<Right>", self.navegar_teclado)

        # Conexão com o Banco de Dados
        try:
            self.db = sqlite3.connect("delivery.db")
            self.cursor = self.db.cursor()
            self.criar_tabelas()
            
            # Carrega configurações do banco
            self.cursor.execute("SELECT chave, valor FROM config")
            for chave, valor in self.cursor.fetchall():
                if chave == 'impressora_selecionada': self.impressora_selecionada = valor
                elif chave == 'nome_empresa': self.nome_empresa = valor
                elif chave == 'fone_empresa': self.fone_empresa = valor
                elif chave == 'end_empresa': self.end_empresa = valor
                elif chave == 'num_vias': self.num_vias = int(valor) if valor.isdigit() else 1
                elif chave == 'largura_papel': self.largura_papel = int(valor) if valor.isdigit() else 80
                elif chave == 'tam_cabecalho': self.tam_cabecalho = int(valor) if valor.isdigit() else 2
                elif chave == 'tam_endereco': self.tam_endereco = int(valor) if valor.isdigit() else 2
                elif chave == 'tam_itens': self.tam_itens = int(valor) if valor.isdigit() else 2
                elif chave == 'tam_valores': self.tam_valores = int(valor) if valor.isdigit() else 2
                elif chave == 'logo_path':
                    if os.path.exists(valor): self.logo_path = valor
            
        except Exception as e:
            print(f"Erro ao conectar banco: {e}")
            self.db = None
            
        # Layout Base
        self.criar_sidebar()
        self.container = ctk.CTkFrame(self, fg_color="white")
        self.container.pack(side="left", fill="both", expand=True)

        self.mostrar_tela_delivery()

    def criar_tabelas(self):
        queries = [
            """CREATE TABLE IF NOT EXISTS config (
                chave TEXT PRIMARY KEY,
                valor TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS clientes (
                telefone TEXT PRIMARY KEY,
                nome TEXT,
                bairro TEXT,
                rua TEXT,
                numero TEXT,
                complemento TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS produtos (
                id_produto INTEGER PRIMARY KEY,
                nome TEXT,
                preco REAL
            )""",
            """CREATE TABLE IF NOT EXISTS categorias (
                id_categoria INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE
            )""",
            """CREATE TABLE IF NOT EXISTS bairros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE,
                taxa REAL
            )""",
            """CREATE TABLE IF NOT EXISTS pedidos (
                id_pedido INTEGER PRIMARY KEY AUTOINCREMENT,
                telefone_cliente TEXT,
                subtotal REAL,
                taxa REAL,
                acrescimos REAL,
                descontos REAL,
                total REAL,
                forma_pagamento TEXT,
                tipo TEXT DEFAULT 'ENTREGA',
                troco REAL,
                data_pedido TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS itens_pedido (
                id_item_pedido INTEGER PRIMARY KEY AUTOINCREMENT,
                id_pedido INTEGER,
                id_produto INTEGER,
                quantidade INTEGER,
                preco_unitario REAL,
                observacao TEXT,
                FOREIGN KEY(id_pedido) REFERENCES pedidos(id_pedido)
            )"""
        ]
        for q in queries:
            self.cursor.execute(q)
        self.db.commit()
        
    def criar_sidebar(self):
        """Cria a barra lateral de navegação persistente"""
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color=Theme.PRIMARY)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False) # Impede que o conteúdo interno mude a largura

        # Header da Sidebar (Menu + Logo)
        self.frame_logo = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.frame_logo.pack(fill="x", pady=(5, 20))

        self.btn_menu = ctk.CTkButton(self.frame_logo, text="≡", width=40, height=40,
                                      fg_color="transparent", font=("Arial", 24, "bold"),
                                      hover_color="#a93226", command=self.toggle_sidebar)
        self.btn_menu.pack(side="top", anchor="ne", padx=10)

        # Espaço para o Ícone/Logo
        self.btn_logo = ctk.CTkButton(self.frame_logo, text="Logo", width=110, height=110,
                                      corner_radius=55, fg_color=Theme.PRIMARY_HOVER,
                                      hover_color="#8e2b21", text_color="white",
                                      font=Theme.FONT_LABEL,
                                      command=self.selecionar_logo)
        self.btn_logo.pack(pady=10)

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
            btn = ctk.CTkButton(self.sidebar, text=texto, fg_color="transparent", height=45,
                                text_color="white", hover_color="#a93226",
                                font=("Arial", 14, "bold"), anchor="w" if self.sidebar_expandido else "center",
                                border_width=0,
                                command=comando)
            btn.pack(pady=10, padx=20, fill="x")
            self.nav_buttons.append((btn, texto, icone))

        # Rodapé da Sidebar com Versão
        self.lbl_versao = ctk.CTkLabel(self.sidebar, text="v1.0.1-beta", font=("Arial", 10), text_color="#ecf0f1")
        self.lbl_versao.pack(side="bottom", pady=10)

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
            pasta_assets = "assets"
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

    def criar_card_container(self, titulo, fg_color=None):
        """Helper para criar uma seção padronizada (Card)"""
        color = fg_color if fg_color else Theme.BG_CARD
        frame = ctk.CTkFrame(self.container, fg_color=color, border_color=Theme.BORDER, border_width=1)
        frame.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkLabel(frame, text=titulo, font=Theme.FONT_H2, text_color=Theme.PRIMARY).grid(row=0, column=0, columnspan=10, pady=(10, 5), padx=15, sticky="w")
        return frame

    def mostrar_tela_delivery(self):
        self.limpar_container()
        self.atualizar_sidebar("Delivery")
        self.modo_retirada = tk.BooleanVar(value=False)

        # Adicionar colunas de pagamento se não existirem
        try: self.cursor.execute("ALTER TABLE pedidos ADD COLUMN forma_pagamento TEXT"); self.db.commit()
        except: pass
        
        # --- RODAPÉ (Pack primeiro para garantir visibilidade no fundo) ---
        self.frame_total = ctk.CTkFrame(self.container, height=100, fg_color="transparent")
        self.frame_total.pack(fill="x", side="bottom", padx=20, pady=10)

        self.lbl_total = ctk.CTkLabel(self.frame_total, text="TOTAL: R$ 0,00", font=("Arial", 35, "bold"), text_color=Theme.PRIMARY)
        self.lbl_total.pack(side="right", padx=30)

        self.btn_finalizar = ctk.CTkButton(self.frame_total, text="🚀 FINALIZAR (F1)", 
                                           fg_color=Theme.SUCCESS, hover_color="#219150", height=55, 
                                           font=("Arial", 18, "bold"), command=self.finalizar_pedido)
        self.btn_finalizar.pack(side="left", padx=10)

        self.btn_consultar = ctk.CTkButton(self.frame_total, text="🔍 CONSULTA (F5)", 
                                           fg_color="#34495e", height=55, 
                                           font=("Arial", 18, "bold"), command=self.abrir_consulta_precos)
        self.btn_consultar.pack(side="left", padx=10)
        
        # Botão Cancelar
        ctk.CTkButton(self.frame_total, text="LIMPAR (F6)", fg_color="gray", height=55, width=120,
                      font=("Arial", 14, "bold"), command=self.limpar_tela_delivery).pack(side="left", padx=10)

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

        # BINDINGS DE NAVEGAÇÃO
        self.ent_tel.bind('<Return>', self.buscar_cliente)
        self.ent_nome.bind('<Return>', lambda e: self.ent_bairro.focus())
        self.ent_bairro.bind('<Return>', lambda e: self.ent_rua.focus())
        self.ent_bairro.bind('<FocusOut>', lambda e: self.buscar_taxa_bairro())
        self.ent_rua.bind('<Return>', lambda e: self.ent_num.focus())
        self.ent_num.bind('<Return>', lambda e: self.ent_comp.focus())
        self.ent_comp.bind('<Return>', lambda e: self.ent_id.focus())

        # --- ÁREA DE LANÇAMENTO ---
        self.frame_lancamento = self.criar_card_container("🛒 LANÇAMENTO DE ITENS")
        self.frame_lancamento.grid_columnconfigure(5, weight=1) # Expande o campo de Obs

        ctk.CTkLabel(self.frame_lancamento, text="Cód/Nome:").grid(row=1, column=0, padx=5, pady=10)
        self.ent_id = ctk.CTkEntry(self.frame_lancamento, width=80, font=("Arial", 16, "bold"))
        self.ent_id.grid(row=1, column=1, padx=5)

        ctk.CTkLabel(self.frame_lancamento, text="Qtd:").grid(row=1, column=2, padx=5)
        self.ent_qtd = ctk.CTkEntry(self.frame_lancamento, width=60, font=("Arial", 16))
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
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", rowheight=30, font=("Arial", 11))
        style.configure("Treeview.Heading", font=("Arial", 12, "bold"), background="#c0392b", foreground="white")
        
        self.tree = ttk.Treeview(self.container, columns=("ID", "Produto", "Qtd", "Preço Unit", "Total", "Obs"), show="headings", selectmode="browse")
        
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

        # Pack da tabela no que restou do espaço central
        self.tree.pack(pady=10, padx=20, fill="both", expand=True)
        
        # BINDINGS DA TABELA
        self.tree.bind("<Button-3>", self.mostrar_menu_contexto)
        self.tree.bind("<Delete>", lambda e: self.excluir_item_carrinho())
        
        self.bind('<F1>', lambda e: self.finalizar_pedido())
        self.bind('<F5>', lambda e: self.abrir_consulta_precos())
        self.bind('<F6>', lambda e: self.limpar_tela_delivery())

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
        tree_con = ttk.Treeview(tree_frame, columns=cols, show="headings")
        tree_con.heading("ID", text="ID")
        tree_con.heading("Produto", text="Nome do Produto")
        tree_con.heading("Preço", text="Valor (R$)")
        tree_con.column("ID", width=70, anchor="center")
        tree_con.column("Produto", width=350, anchor="w")
        tree_con.column("Preço", width=100, anchor="center")
        tree_con.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree_con.yview)
        tree_con.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")

        def carregar_dados(termo=""):
            for i in tree_con.get_children(): tree_con.delete(i)
            if self.db:
                if termo:
                    self.cursor.execute("SELECT id_produto, nome, preco FROM produtos WHERE nome LIKE ? OR id_produto LIKE ? ORDER BY id_produto", 
                                        (f"%{termo}%", f"%{termo}%"))
                else:
                    self.cursor.execute("SELECT id_produto, nome, preco FROM produtos ORDER BY id_produto")
                for r in self.cursor.fetchall():
                    tree_con.insert("", "end", values=(r[0], r[1], f"R$ {r[2]:.2f}"))

        ent_busca.bind("<KeyRelease>", lambda e: carregar_dados(ent_busca.get()))
        carregar_dados()

        ctk.CTkButton(main_f, text="FECHAR (ESC)", fg_color="gray", command=pop.destroy).pack(pady=10)
        pop.bind("<Escape>", lambda e: pop.destroy())
        ent_busca.focus()

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
            self.tree.selection_set(item)
            menu = tk.Menu(self, tearoff=0)
            menu.add_command(label="📝 Editar Item", command=self.editar_item_carrinho)
            menu.add_command(label="❌ Excluir Item", command=self.excluir_item_carrinho)
            menu.post(event.x_root, event.y_root)

    def excluir_item_carrinho(self):
        sel = self.tree.selection()
        if sel:
            for i in sel:
                self.tree.delete(i)
            self.atualizar_total()

    def editar_item_carrinho(self):
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
            self.focar_qtd(None) # Atualiza o label do produto e foca na Qtd

    def mostrar_tela_cardapio(self):
        self.limpar_container()
        self.atualizar_sidebar("Cardápio")

        # --- ÁREA DE CADASTRO DE PRODUTO ---
        self.frame_cad_prod = ctk.CTkFrame(self.container, fg_color="#f9f9f9", border_color="#e0e0e0", border_width=1)
        self.frame_cad_prod.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(self.frame_cad_prod, text="🍎 CADASTRO DE PRODUTO", font=("Arial", 14, "bold"), text_color="#c0392b").grid(row=0, column=0, columnspan=4, pady=(10, 5), padx=15, sticky="w")
        self.frame_cad_prod.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.ent_id_prod = self.criar_campo(self.frame_cad_prod, "ID (Código)", 1, 0)
        self.ent_nome_prod = self.criar_campo(self.frame_cad_prod, "Nome do Produto", 1, 1)
        self.ent_cat_prod = self.criar_campo(self.frame_cad_prod, "Categoria", 1, 2)
        self.ent_preco_prod = self.criar_campo(self.frame_cad_prod, "Preço (R$)", 1, 3)

        # Listbox para sugestões (criada após os campos para referência)
        self.frame_sugestao = tk.Frame(self.container, bg="white", highlightbackground="#d1d1d1", highlightthickness=1)
        self.list_sugestao = tk.Listbox(self.frame_sugestao, font=("Arial", 11), borderwidth=0, highlightthickness=0)
        self.list_sugestao.pack(fill="both", expand=True)

        # --- BOTÕES DE AÇÃO E FILTRO ---
        self.frame_acoes_prod = ctk.CTkFrame(self.container, fg_color="transparent")
        self.frame_acoes_prod.pack(pady=10, padx=20, fill="x")

        self.btn_salvar_prod = ctk.CTkButton(self.frame_acoes_prod, text="SALVAR (F2)", fg_color="#27ae60", height=35, command=self.salvar_produto_db)
        self.btn_salvar_prod.pack(side="left", padx=5)

        self.btn_limpar_prod = ctk.CTkButton(self.frame_acoes_prod, text="LIMPAR (F3)", fg_color="gray", height=35, command=self.limpar_campos_cardapio)
        self.btn_limpar_prod.pack(side="left", padx=5)

        self.btn_excluir_prod = ctk.CTkButton(self.frame_acoes_prod, text="EXCLUIR (DEL)", fg_color="#e74c3c", height=35, command=self.excluir_produto_db)
        self.btn_excluir_prod.pack(side="right", padx=5)

        ctk.CTkLabel(self.frame_acoes_prod, text="🔍 Filtrar:", font=Theme.FONT_LABEL).pack(side="right", padx=5)
        self.cb_filtro_cat = ctk.CTkComboBox(self.frame_acoes_prod, values=["TODOS"], command=lambda _: self.atualizar_lista_produtos())
        self.cb_filtro_cat.pack(side="right", padx=5)
        self.cb_filtro_cat.set("TODOS")

        # --- TABELA DE PRODUTOS ---
        self.tree_prod = ttk.Treeview(self.container, columns=("ID", "Produto", "Categoria", "Preço"), show="headings")
        self.tree_prod.heading("ID", text="ID")
        self.tree_prod.heading("Produto", text="Nome do Produto")
        self.tree_prod.heading("Categoria", text="Categoria")
        self.tree_prod.heading("Preço", text="Preço (R$)")
        self.tree_prod.column("ID", width=80, anchor="center")
        self.tree_prod.column("Produto", width=300, anchor="w")
        self.tree_prod.column("Categoria", width=150, anchor="center")
        self.tree_prod.column("Preço", width=100, anchor="center")
        self.tree_prod.pack(pady=10, padx=20, fill="both", expand=True)
        self.tree_prod.bind("<<TreeviewSelect>>", self.preencher_campos_cardapio)

        # Adicionar campo Categoria na tabela de produtos
        self.cursor.execute("PRAGMA table_info(produtos)")
        if 'categoria' not in [col[1] for col in self.cursor.fetchall()]:
            self.cursor.execute("ALTER TABLE produtos ADD COLUMN categoria TEXT")
            self.db.commit()

        self.atualizar_lista_produtos()

        # BINDINGS DE NAVEGAÇÃO (Cardápio)
        self.ent_id_prod.bind('<Return>', lambda e: self.ent_nome_prod.focus())
        self.ent_nome_prod.bind('<Return>', lambda e: self.ent_cat_prod.focus())
        self.ent_cat_prod.bind('<Return>', self.processar_enter_categoria)
        self.ent_cat_prod.bind('<KeyRelease>', self.filtrar_categorias_sugestao)
        self.ent_preco_prod.bind('<Return>', lambda e: self.salvar_produto_db())

        # Atalhos Globais da Tela
        self.bind('<F2>', lambda e: self.salvar_produto_db())
        self.bind('<F3>', lambda e: self.limpar_campos_cardapio())
        self.bind('<F4>', lambda e: self.excluir_produto_db())
        self.bind('<Delete>', lambda e: self.excluir_produto_db())

        # --- BOTÕES DE AÇÃO ---
        self.frame_acoes_prod = ctk.CTkFrame(self.container, fg_color="transparent")
        self.frame_acoes_prod.pack(pady=10, padx=20, fill="x")

        self.btn_salvar_prod = ctk.CTkButton(self.frame_acoes_prod, text="SALVAR (F2)", fg_color="#27ae60", hover_color="#219150", 
                                             font=("Arial", 13, "bold"), command=self.salvar_produto_db)
        self.btn_salvar_prod.pack(side="left", padx=5)

        self.btn_limpar_prod = ctk.CTkButton(self.frame_acoes_prod, text="LIMPAR (F3)", fg_color="gray", 
                                             font=("Arial", 13, "bold"), command=self.limpar_campos_cardapio)
        self.btn_limpar_prod.pack(side="left", padx=5)

        self.btn_excluir_prod = ctk.CTkButton(self.frame_acoes_prod, text="EXCLUIR (DEL)", fg_color="#e74c3c", hover_color="#c0392b", 
                                              font=("Arial", 13, "bold"), command=self.excluir_produto_db)
        self.btn_excluir_prod.pack(side="right", padx=5)

        ctk.CTkLabel(self.frame_acoes_prod, text="🔍 Filtrar:", font=("Arial", 12, "bold")).pack(side="right", padx=5)
        self.cb_filtro_cat = ctk.CTkComboBox(self.frame_acoes_prod, values=["TODOS"], command=lambda _: self.atualizar_lista_produtos())
        self.cb_filtro_cat.pack(side="right", padx=5)
        self.cb_filtro_cat.set("TODOS")

        # --- TABELA DE PRODUTOS ---
        self.tree_prod = ttk.Treeview(self.container, columns=("ID", "Produto", "Categoria", "Preço"), show="headings", selectmode="browse")
        self.tree_prod.heading("ID", text="ID ↕", command=lambda: self.ordenar_coluna_cardapio("ID", False))
        self.tree_prod.heading("Produto", text="Nome do Produto ↕", command=lambda: self.ordenar_coluna_cardapio("Produto", False))
        self.tree_prod.heading("Categoria", text="Categoria ↕", command=lambda: self.ordenar_coluna_cardapio("Categoria", False))
        self.tree_prod.heading("Preço", text="Preço (R$) ↕", command=lambda: self.ordenar_coluna_cardapio("Preço", False))

        self.tree_prod.column("ID", width=100, anchor="center")
        self.tree_prod.column("Produto", width=300, anchor="w")
        self.tree_prod.column("Categoria", width=150, anchor="center")
        self.tree_prod.column("Preço", width=100, anchor="center")

        self.tree_prod.pack(pady=10, padx=20, fill="both", expand=True)
        self.tree_prod.bind("<<TreeviewSelect>>", self.preencher_campos_cardapio)

        self.atualizar_lista_produtos()

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

        # Alterna a direção da próxima ordenação
        self.tree_prod.heading(col, command=lambda: self.ordenar_coluna_cardapio(col, not reverse))

    def salvar_produto_db(self):
        id_p = self.ent_id_prod.get()
        nome = self.ent_nome_prod.get()
        preco = self.ent_preco_prod.get().replace(",", ".")
        cat = self.ent_cat_prod.get().strip()

        if not id_p or not nome or not preco or not cat:
            messagebox.showwarning("Aviso", "Preencha todos os campos!")
            return

        try:
            float(preco)
            # Verifica se a categoria já existe, se não, cria.
            self.cursor.execute("SELECT id_categoria FROM categorias WHERE nome = ? COLLATE NOCASE", (cat,))
            if not self.cursor.fetchone():
                self.cursor.execute("INSERT INTO categorias (nome) VALUES (?)", (cat,))

            self.cursor.execute("INSERT OR REPLACE INTO produtos (id_produto, nome, preco, categoria) VALUES (?, ?, ?, ?)", 
                                (id_p, nome, preco, cat))
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
            self.cursor.execute("SELECT id_produto, nome, categoria, preco FROM produtos ORDER BY nome")
        else:
            self.cursor.execute("SELECT id_produto, nome, categoria, preco FROM produtos WHERE categoria = ? ORDER BY nome", (filtro,))
            
        for linha in self.cursor.fetchall():
            self.tree_prod.insert("", "end", values=(linha[0], linha[1], linha[2] if linha[2] else "-", f"{linha[3]:.2f}"))
        
        self.atualizar_lista_categorias()

    def preencher_campos_cardapio(self, event):
        item_sel = self.tree_prod.selection()
        if item_sel:
            valores = self.tree_prod.item(item_sel)['values']
            self.limpar_campos_cardapio()
            self.ent_id_prod.insert(0, valores[0])
            self.ent_nome_prod.insert(0, valores[1])
            self.ent_cat_prod.insert(0, valores[2] if valores[2] != "-" else "")
            self.ent_preco_prod.insert(0, valores[3])

    def limpar_campos_cardapio(self):
        self.ent_id_prod.delete(0, 'end')
        self.ent_nome_prod.delete(0, 'end')
        self.ent_preco_prod.delete(0, 'end')
        self.ent_cat_prod.delete(0, 'end')
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
        self.tree_taxas = ttk.Treeview(self.container, columns=("Bairro", "Taxa"), show="headings")
        self.tree_taxas.heading("Bairro", text="Bairro")
        self.tree_taxas.heading("Taxa", text="Valor da Taxa")
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
        for r in self.cursor.fetchall(): self.tree_taxas.insert("", "end", values=(r[0], f"{r[1]:.2f}"))

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
        else:
            messagebox.showwarning("Aviso", f"O bairro '{bairro}' não está cadastrado nas Taxas de Entrega!")
            self.ent_bairro.delete(0, 'end')
            self.ent_bairro.focus()

    def mostrar_tela_estatisticas(self, tipo="ENTREGA"):
        self.limpar_container()
        self.tipo_historico_atual = tipo
        sidebar_label = "Hist. Delivery" if tipo == "ENTREGA" else "Hist. Retirada"
        self.atualizar_sidebar(sidebar_label)
        
        # Adicionar colunas faltantes se o banco já existir
        try:
            self.cursor.execute("ALTER TABLE pedidos ADD COLUMN subtotal REAL")
            self.cursor.execute("ALTER TABLE pedidos ADD COLUMN taxa REAL")
            self.cursor.execute("ALTER TABLE pedidos ADD COLUMN acrescimos REAL")
            self.cursor.execute("ALTER TABLE pedidos ADD COLUMN descontos REAL")
            self.cursor.execute("ALTER TABLE pedidos ADD COLUMN tipo TEXT DEFAULT 'ENTREGA'")
            self.db.commit()
        except: pass

        # --- CABEÇALHO ---
        self.frame_estat = ctk.CTkFrame(self.container, fg_color="#f9f9f9", border_color="#e0e0e0", border_width=1)
        self.frame_estat.pack(pady=10, padx=20, fill="x")

        titulo_texto = "📊 HISTÓRICO - " + ("DELIVERY" if tipo == "ENTREGA" else "RETIRADA")
        ctk.CTkLabel(self.frame_estat, text=titulo_texto, font=("Arial", 14, "bold"), text_color="#c0392b").pack(side="left", padx=15, pady=10)

        # Resumo Financeiro
        self.frame_resumo_dia = ctk.CTkFrame(self.frame_estat, fg_color="#2c3e50", corner_radius=5)
        self.frame_resumo_dia.pack(side="right", padx=10, pady=5)
        self.lbl_faturamento = ctk.CTkLabel(self.frame_resumo_dia, text="Faturamento: R$ 0,00", 
                                            text_color="white", font=("Arial", 12, "bold"), padx=10)
        self.lbl_faturamento.pack()

        # Filtro de Data
        ctk.CTkLabel(self.frame_estat, text="📅 Selecionar Data:", font=("Arial", 12)).pack(side="left", padx=(20, 5))
        
        if DateEntry:
            self.ent_filtro_data = DateEntry(self.frame_estat, width=12, background='darkblue',
                                            foreground='white', borderwidth=2, date_pattern='dd/mm/yyyy')
            self.ent_filtro_data.pack(side="left", padx=5)
        else:
            self.ent_filtro_data = ctk.CTkEntry(self.frame_estat, width=120)
            self.ent_filtro_data.pack(side="left", padx=5)
            self.ent_filtro_data.insert(0, datetime.now().strftime("%d/%m/%Y"))
        
        btn_filtrar = ctk.CTkButton(self.frame_estat, text="Filtrar", width=80, fg_color="#34495e", command=self.atualizar_lista_pedidos)
        btn_filtrar.pack(side="left", padx=5)
        
        btn_hoje = ctk.CTkButton(self.frame_estat, text="Hoje", width=60, fg_color="gray", command=lambda: (self.ent_filtro_data.delete(0, 'end'), self.ent_filtro_data.insert(0, datetime.now().strftime("%d/%m/%Y")), self.atualizar_lista_pedidos()))
        btn_hoje.pack(side="left", padx=5)

        # Botão Limpar Antigos
        btn_limpar = ctk.CTkButton(self.frame_estat, text="🗑️ Limpar Antigos", width=120, fg_color="#e67e22", command=self.limpar_historico_antigo)
        btn_limpar.pack(side="right", padx=15)

        # --- TABELA DE PEDIDOS ---
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview.Heading", font=("Arial", 12, "bold"), background="#c0392b", foreground="white")

        self.tree_pedidos = ttk.Treeview(self.container, columns=("ID", "Cliente", "Contato", "Valor", "Horário", "RealID"), show="headings", selectmode="browse")
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

        self.tree_pedidos.pack(pady=10, padx=20, fill="both", expand=True)
        
        # Bindings: Click Esquerdo (Visualizar) e Direito (Menu)
        self.tree_pedidos.bind("<ButtonRelease-1>", self.visualizar_comanda_estatisticas)
        self.tree_pedidos.bind("<Button-3>", self.mostrar_menu_contexto_estatisticas)
        
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
                           (SELECT COUNT(*) FROM pedidos p2 WHERE DATE(p2.data_pedido, 'localtime') = DATE(p1.data_pedido, 'localtime') AND p2.tipo = p1.tipo AND p2.id_pedido <= p1.id_pedido) as num_dia,
                           c.nome, p1.telefone_cliente, p1.total, p1.data_pedido, p1.id_pedido
                           FROM pedidos p1 JOIN clientes c ON p1.telefone_cliente = c.telefone 
                           WHERE DATE(p1.data_pedido, 'localtime') = ? AND p1.tipo = ? ORDER BY p1.id_pedido DESC"""
                self.cursor.execute(query, (data_iso, self.tipo_historico_atual))
                rows = self.cursor.fetchall()
                for linha in rows:
                    faturamento_total += linha[3]
                    dt = datetime.strptime(linha[4], "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M")
                    self.tree_pedidos.insert("", "end", values=(linha[0], linha[1], linha[2], f"R$ {linha[3]:.2f}", dt, linha[5]))
                
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
        self.cursor.execute("SELECT subtotal, taxa, acrescimos, descontos, total, telefone_cliente, data_pedido, tipo FROM pedidos WHERE id_pedido = ?", (id_pedido,))
        p = self.cursor.fetchone()
        vf = {'subtotal': p[0], 'taxa': p[1], 'acrescimos': p[2], 'descontos': p[3], 'total': p[4], 'tipo': p[7]}
        tel = p[5]
        data_pedido_db = p[6]

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

        # 3. Calcular o número do pedido naquele dia específico
        self.cursor.execute("""SELECT COUNT(*) FROM pedidos 
                             WHERE DATE(data_pedido, 'localtime') = DATE(?, 'localtime') 
                             AND tipo = ? 
                             AND id_pedido <= ?""", (data_pedido_db, p[7], id_pedido))
        num_dia = self.cursor.fetchone()[0]
        
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

    def limpar_historico_antigo(self):
        if messagebox.askyesno("Atenção", "Deseja excluir TODOS os pedidos de dias anteriores?"):
            try:
                # Deleta itens primeiro por causa da FK
                self.cursor.execute("DELETE FROM itens_pedido WHERE id_pedido IN (SELECT id_pedido FROM pedidos WHERE DATE(data_pedido, 'localtime') < DATE('now', 'localtime'))")
                self.cursor.execute("DELETE FROM pedidos WHERE DATE(data_pedido, 'localtime') < DATE('now', 'localtime')")
                self.db.commit()
                self.atualizar_lista_pedidos()
                messagebox.showinfo("Sucesso", "Histórico antigo removido!")
            except Exception as e:
                print(e)

    def criar_campo(self, master, texto, row, col, colspan=1):
        frame = ctk.CTkFrame(master, fg_color="transparent")
        frame.grid(row=row, column=col, columnspan=colspan, padx=10, pady=5, sticky="ew")

        lbl = ctk.CTkLabel(frame, text=texto, font=Theme.FONT_LABEL, text_color="#555")
        lbl.pack(anchor="w", padx=2)
        
        ent = ctk.CTkEntry(frame, height=32, border_color="#d1d1d1")
        ent.pack(fill="x", expand=True)
        return ent

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

    def focar_qtd(self, event):
        id_digitado = self.ent_id.get()
        if id_digitado and self.db:
            self.cursor.execute("SELECT nome, preco, id_produto FROM produtos WHERE id_produto = ? OR nome LIKE ?", (id_digitado, f"%{id_digitado}%"))
            res = self.cursor.fetchone()
            if res:
                self.ent_id.delete(0, 'end'); self.ent_id.insert(0, res[2]) # Garante o ID no campo
                self.lbl_nome_prod.configure(text=f"{res[0]} - R$ {res[1]}", text_color=Theme.SUCCESS)
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
                self.ent_id.delete(0, 'end'); self.ent_qtd.delete(0, 'end'); self.ent_obs.delete(0, 'end')
                self.lbl_nome_prod.configure(text="Produto: ---")
                self.ent_id.focus()
                self.atualizar_total()

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
            lbl = ctk.CTkLabel(main_f, text=label, font=("Arial", 12, "bold"))
            lbl.pack(anchor="w", pady=(10, 0))
            ent = ctk.CTkEntry(main_f, height=35, font=("Arial", 14))
            ent.insert(0, f"{valor_init:.2f}")
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
                total = float(self.ed_sub.get()) + float(self.ed_acr.get()) + float(self.ed_tax.get()) - float(self.ed_des.get())
                recebido = float(self.ed_recebido.get())
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
                # SQLite UPSERT: Insere ou substitui se o telefone já existir
                sql = """INSERT INTO clientes (telefone, nome, bairro, rua, numero, complemento) 
                         VALUES (?, ?, ?, ?, ?, ?) 
                         ON CONFLICT(telefone) DO UPDATE SET 
                         nome=excluded.nome, 
                         bairro=CASE WHEN excluded.bairro != '' THEN excluded.bairro ELSE clientes.bairro END,
                         rua=CASE WHEN excluded.rua != '' THEN excluded.rua ELSE clientes.rua END,
                         numero=CASE WHEN excluded.numero != '' THEN excluded.numero ELSE clientes.numero END,
                         complemento=CASE WHEN excluded.complemento != '' THEN excluded.complemento ELSE clientes.complemento END"""
                val = (tel, nome, bairro, rua, num, comp)
                try:
                    # 1. Salva/Atualiza Cliente
                    self.cursor.execute(sql, val)

                    vf = self.valores_finais
                    if self.editando_id_pedido:
                        # 2. Atualiza o Pedido Existente em vez de criar um novo
                        self.cursor.execute("""UPDATE pedidos SET telefone_cliente=?, subtotal=?, taxa=?, acrescimos=?, descontos=?, total=?, tipo=? 
                                             WHERE id_pedido=?""", 
                                             (tel, vf['subtotal'], vf['taxa'], vf['acrescimos'], vf['descontos'], vf['total'], tipo_pedido, self.editando_id_pedido))
                        id_pedido = self.editando_id_pedido
                        # Limpa os itens antigos para re-inserir a nova versão editada
                        self.cursor.execute("DELETE FROM itens_pedido WHERE id_pedido=?", (id_pedido,))
                    else:
                        # 2. Insere um Novo Pedido
                        self.cursor.execute("""INSERT INTO pedidos (telefone_cliente, subtotal, taxa, acrescimos, descontos, total, tipo) 
                                             VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                                             (tel, vf['subtotal'], vf['taxa'], vf['acrescimos'], vf['descontos'], vf['total'], tipo_pedido))
                        id_pedido = self.cursor.lastrowid

                    # Calcula o número do pedido no dia (num_dia) baseado na data do pedido e IDs existentes
                    self.cursor.execute("""SELECT COUNT(*) FROM pedidos 
                                         WHERE DATE(data_pedido, 'localtime') = (SELECT DATE(data_pedido, 'localtime') FROM pedidos WHERE id_pedido = ?) 
                                         AND tipo = ? 
                                         AND id_pedido <= ?""", (id_pedido, tipo_pedido, id_pedido))
                    num_dia = self.cursor.fetchone()[0]

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

        try:
            # Configurações de caracteres baseadas na largura do papel (ESC/POS)
            limit = int(self.largura_papel * 0.53)
            
            # Comandos ESC/POS básicos
            INIT = b'\x1b@'
            CENTER = b'\x1ba\x01'
            LEFT = b'\x1ba\x00'
            BOLD_ON = b'\x1bE\x01'
            BOLD_OFF = b'\x1bE\x00'
            # GS ! n (Tamanho da fonte: 0x00=normal, 0x01=dobro altura, 0x11=dobro total)
            TAM_MAP = [b'\x1d!\x00', b'\x1d!\x01', b'\x1d!\x10', b'\x1d!\x11', b'\x1d!\x21']
            
            raw = INIT + CENTER
            
            # Cabeçalho
            raw += TAM_MAP[self.tam_cabecalho] + BOLD_ON + self.nome_empresa.encode('ascii', 'ignore') + b'\n'
            raw += TAM_MAP[0] + BOLD_OFF + self.fone_empresa.encode('ascii', 'ignore') + b'\n'
            
            label_tipo = "Entrega" if tipo == "ENTREGA" else "Retirada"
            raw += b'\n' + BOLD_ON + f"{label_tipo.upper()} N. {num_dia}".encode() + BOLD_OFF + b'\n'
            raw += datetime.now().strftime("%d/%m/%Y %H:%M").encode() + b'\n'
            raw += b'-' * limit + b'\n'
            
            # Cliente e Endereço
            raw += LEFT + TAM_MAP[self.tam_endereco]
            if cliente_info is None:
                cliente_info = {'nome': self.ent_nome.get(), 'tel': self.ent_tel.get(), 'rua': self.ent_rua.get(), 
                               'num': self.ent_num.get(), 'bairro': self.ent_bairro.get(), 'comp': self.ent_comp.get()}
            
            cli_txt = f"Cliente: {cliente_info['nome']}\nTel: {cliente_info['tel']}\n"
            if tipo == "ENTREGA":
                cli_txt += f"End: {cliente_info['rua']}, {cliente_info['num']}\nBairro: {cliente_info['bairro']}\n"
                if cliente_info['comp']: cli_txt += f"Comp: {cliente_info['comp']}\n"
            
            for linha in cli_txt.split('\n'):
                for wrap_l in textwrap.wrap(linha, width=limit):
                    raw += wrap_l.encode('ascii', 'ignore') + b'\n'
            
            raw += b'-' * limit + b'\n'
            
            # Itens
            raw += BOLD_ON + b"ITENS\n" + BOLD_OFF + TAM_MAP[self.tam_itens]
            if itens_comanda is None:
                itens_comanda = [self.tree.item(item_id)['values'] for item_id in self.tree.get_children()]
            
            for val in itens_comanda:
                # val: (ID, Produto, Qtd, PrecoUnit, Total, Obs)
                qtd_nome = f"{val[2]}x {val[1]}"
                preco = f"R$ {val[4]}"
                
                espacos = limit - len(qtd_nome) - len(preco)
                if espacos < 1:
                    linhas_nome = textwrap.wrap(qtd_nome, width=limit-10)
                    raw += linhas_nome[0].encode('ascii', 'ignore')
                    espacos = limit - len(linhas_nome[0]) - len(preco)
                    raw += b' ' * espacos + preco.encode() + b'\n'
                    for extra in linhas_nome[1:]:
                        raw += b'  ' + extra.encode('ascii', 'ignore') + b'\n'
                else:
                    raw += qtd_nome.encode('ascii', 'ignore') + (b' ' * espacos) + preco.encode() + b'\n'
                
                if val[5]: # Observação
                    for obs_l in textwrap.wrap(f"Obs: {val[5]}", width=limit-2):
                        raw += b'  ' + obs_l.encode('ascii', 'ignore') + b'\n'
            
            raw += b'-' * limit + b'\n'
            
            # Valores Finais
            raw += TAM_MAP[self.tam_valores]
            vals = [("Sub-total:", vf['subtotal']), ("Taxa Entrega:", vf['taxa']), 
                    ("Descontos:", -vf['descontos']), ("TOTAL:", vf['total'])]
            
            for lbl, v in vals:
                txt_v = f"R$ {v:.2f}"
                espacos = limit - len(lbl) - len(txt_v)
                raw += lbl.encode() + (b' ' * espacos) + txt_v.encode() + b'\n'
            
            raw += b'\n' + BOLD_ON + CENTER + f"PAGAMENTO: {vf.get('pagamento', 'N/A')}".encode() + b'\n'
            
            # Rodapé e Corte
            raw += b'\n' * 3 + b'\x1dV\x42\x00' # Comando de corte
            
            # Envio para impressora
            printer_to_use = self.impressora_selecionada if self.impressora_selecionada and self.impressora_selecionada != "Nenhuma" else win32print.GetDefaultPrinter()
            hPrinter = win32print.OpenPrinter(printer_to_use)
            try:
                for _ in range(self.num_vias):
                    win32print.StartDocPrinter(hPrinter, 1, ("Comanda VEX", None, "RAW"))
                    win32print.StartPagePrinter(hPrinter)
                    win32print.WritePrinter(hPrinter, raw)
                    win32print.EndPagePrinter(hPrinter)
                    win32print.EndDocPrinter(hPrinter)
                    time.sleep(0.1)
            finally:
                win32print.ClosePrinter(hPrinter)
                
        except Exception as e:
            messagebox.showerror("Erro de Impressão", f"Não foi possível imprimir: {e}")

    def mostrar_tela_configuracoes(self):
        self.limpar_container()
        self.atualizar_sidebar("Configurações")

        # --- SEÇÃO 1: DADOS DO ESTABELECIMENTO ---
        frame_empresa = self.criar_card_container("🏪 DADOS DO ESTABELECIMENTO")
        frame_empresa.grid_columnconfigure((0, 1), weight=1)
        
        self.ent_conf_nome = self.criar_campo(frame_empresa, "Nome da Empresa (Cabeçalho)", 1, 0)
        self.ent_conf_nome.insert(0, self.nome_empresa)
        
        self.ent_conf_fone = self.criar_campo(frame_empresa, "Telefone de Contato", 1, 1)
        self.ent_conf_fone.insert(0, self.fone_empresa)
        
        self.ent_conf_end = self.criar_campo(frame_empresa, "Endereço Completo", 2, 0, colspan=2)
        self.ent_conf_end.insert(0, self.end_empresa)

        # --- SEÇÃO 2: CONFIGURAÇÕES DE IMPRESSÃO ---
        frame_print = self.criar_card_container("🖨️ CONFIGURAÇÕES DE IMPRESSÃO")
        frame_print.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame_print, text="Impressora Selecionada:", font=Theme.FONT_LABEL).grid(row=1, column=0, padx=15, pady=10, sticky="w")
        
        impressoras_disponiveis = ["Nenhuma"]
        if WIN32_PRINTER_AVAILABLE:
            try:
                # Enumera todas as impressoras locais e de rede conectadas
                # Tenta primeiro o Nível 2 (mais detalhado) e depois o Nível 1 como fallback
                printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS, None, 2)
                impressoras_disponiveis.extend([p['pPrinterName'] for p in printers])
                
                if len(impressoras_disponiveis) == 1: # Se só tem o "Nenhuma", tenta Nível 1
                    printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS, None, 1)
                    impressoras_disponiveis.extend([p[2] for p in printers if p[2] not in impressoras_disponiveis])
            except Exception as e:
                messagebox.showwarning("Erro", f"Não foi possível listar impressoras: {e}")
                print(f"Erro ao listar impressoras: {e}")
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

        # --- SEÇÃO 3: OPERACIONAL ---
        frame_pref = self.criar_card_container("⚙️ PREFERÊNCIAS OPERACIONAIS")
        btn_cfg_print = ctk.CTkButton(frame_pref, text="⚙️ AJUSTES DE TAMANHO E PAPEL", 
                                      fg_color="#34495e", command=self.abrir_config_impressora)
        btn_cfg_print.grid(row=1, column=0, padx=15, pady=15, sticky="w")

        # Botão Salvar Geral
        btn_salvar_tudo = ctk.CTkButton(self.container, text="💾 SALVAR TODAS AS CONFIGURAÇÕES", 
                                        fg_color=Theme.SUCCESS, hover_color="#219150", 
                                        height=50, font=("Arial", 16, "bold"),
                                        command=self.salvar_todas_configs)
        btn_salvar_tudo.pack(pady=20, padx=20, fill="x")

    def abrir_config_impressora(self):
        pop = ctk.CTkToplevel(self)
        pop.title("Ajustes de Impressão")
        pop.geometry("450x550")
        pop.grab_set()
        pop.attributes("-topmost", True)

        f = ctk.CTkFrame(pop, fg_color="white")
        f.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(f, text="📏 LARGURA E FONTES", font=Theme.FONT_H2).pack(pady=10)

        def criar_slider(label, var_name, current_val):
            ctk.CTkLabel(f, text=label, font=Theme.FONT_LABEL).pack(anchor="w", padx=10)
            s = ctk.CTkSegmentedButton(f, values=["Mínimo", "Pequeno", "Médio", "Grande", "Máximo"])
            s.pack(fill="x", padx=10, pady=(0, 10))
            s.set(["Mínimo", "Pequeno", "Médio", "Grande", "Máximo"][current_val])
            return s

        ctk.CTkLabel(f, text="Largura do Papel (mm):", font=Theme.FONT_LABEL).pack(anchor="w", padx=10)
        ed_largura = ctk.CTkEntry(f)
        ed_largura.insert(0, str(self.largura_papel))
        ed_largura.pack(fill="x", padx=10, pady=(0, 15))

        seg_cab = criar_slider("Tamanho do Cabeçalho:", "tam_cabecalho", self.tam_cabecalho)
        seg_end = criar_slider("Tamanho do Endereço:", "tam_endereco", self.tam_endereco)
        seg_itm = criar_slider("Tamanho dos Itens:", "tam_itens", self.tam_itens)
        seg_val = criar_slider("Tamanho dos Valores:", "tam_valores", self.tam_valores)

        def aplicar():
            mapa = {"Mínimo": 0, "Pequeno": 1, "Médio": 2, "Grande": 3, "Máximo": 4}
            self.largura_papel = int(ed_largura.get())
            self.tam_cabecalho = mapa[seg_cab.get()]
            self.tam_endereco = mapa[seg_end.get()]
            self.tam_itens = mapa[seg_itm.get()]
            self.tam_valores = mapa[seg_val.get()]
            self.salvar_todas_configs()
            pop.destroy()

        def imprimir_teste():
            mapa = {"Mínimo": 0, "Pequeno": 1, "Médio": 2, "Grande": 3, "Máximo": 4}
            try:
                largura = int(ed_largura.get())
                self.imprimir_pagina_teste(
                    largura,
                    mapa[seg_cab.get()],
                    mapa[seg_end.get()],
                    mapa[seg_itm.get()],
                    mapa[seg_val.get()]
                )
            except ValueError:
                messagebox.showerror("Erro", "Largura do papel inválida!")

        ctk.CTkButton(f, text="🖨️ IMPRIMIR PÁGINA TESTE", fg_color="#34495e", command=imprimir_teste).pack(pady=(10, 0), fill="x", padx=10)
        ctk.CTkButton(f, text="APLICAR E SALVAR", fg_color=Theme.SUCCESS, command=aplicar).pack(pady=20, fill="x", padx=10)

    def imprimir_pagina_teste(self, largura, tam_cab, tam_end, tam_itm, tam_val):
        # Preserva configs atuais
        old_largura, old_cab, old_end, old_itm, old_val = self.largura_papel, self.tam_cabecalho, self.tam_endereco, self.tam_itens, self.tam_valores
        
        # Aplica temporariamente para o teste
        self.largura_papel, self.tam_cabecalho, self.tam_endereco, self.tam_itens, self.tam_valores = largura, tam_cab, tam_end, tam_itm, tam_val
        
        vf = {'subtotal': 15.0, 'taxa': 5.0, 'acrescimos': 0.0, 'descontos': 0.0, 'total': 20.0, 'recebido': 50.0, 'pagamento': 'DINHEIRO'}
        cliente = {'nome': 'CLIENTE TESTE IMPRESSÃO', 'tel': '(00) 00000-0000', 'rua': 'RUA DE TESTE EQUIPAMENTO', 'num': '123', 'bairro': 'BAIRRO EXEMPLO', 'comp': 'LOJA 01'}
        itens = [
            (1, "PRODUTO TESTE 01", 2, "R$ 5.00", "10.00", "Sem cebola"),
            (2, "PRODUTO TESTE 02", 1, "R$ 5.00", "5.00", "")
        ]
        
        try:
            self.gerar_e_imprimir_comanda(0, vf, 1, tipo="ENTREGA", cliente_info=cliente, itens_comanda=itens)
        finally:
            # Restaura para as configurações salvas anteriormente
            self.largura_papel, self.tam_cabecalho, self.tam_endereco, self.tam_itens, self.tam_valores = old_largura, old_cab, old_end, old_itm, old_val

    def salvar_todas_configs(self):
        try:
            configs = {
                'nome_empresa': self.ent_conf_nome.get(),
                'fone_empresa': self.ent_conf_fone.get(),
                'end_empresa': self.ent_conf_end.get(),
                'num_vias': self.ent_conf_vias.get(),
                'impressora_selecionada': self.cb_impressora.get(),
                'largura_papel': str(self.largura_papel),
                'tam_cabecalho': str(self.tam_cabecalho),
                'tam_endereco': str(self.tam_endereco),
                'tam_itens': str(self.tam_itens),
                'tam_valores': str(self.tam_valores)
            }
            
            for chave, valor in configs.items():
                self.cursor.execute("INSERT OR REPLACE INTO config (chave, valor) VALUES (?, ?)", (chave, valor))
            
            self.db.commit()
            
            # Atualiza variáveis locais
            self.nome_empresa = configs['nome_empresa']
            self.fone_empresa = configs['fone_empresa']
            self.end_empresa = configs['end_empresa']
            self.num_vias = int(configs['num_vias']) if configs['num_vias'].isdigit() else 1
            self.impressora_selecionada = None if configs['impressora_selecionada'] == "Nenhuma" else configs['impressora_selecionada']

            messagebox.showinfo("Sucesso", "Configurações aplicadas!")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao salvar: {e}")

    def limpar_historico_antigo(self):
        if messagebox.askyesno("Atenção", "Deseja excluir TODOS os pedidos de dias anteriores?"):
            try:
                # Deleta itens primeiro por causa da FK
                self.cursor.execute("DELETE FROM itens_pedido WHERE id_pedido IN (SELECT id_pedido FROM pedidos WHERE DATE(data_pedido, 'localtime') < DATE('now', 'localtime'))")
                self.cursor.execute("DELETE FROM pedidos WHERE DATE(data_pedido, 'localtime') < DATE('now', 'localtime')")
                self.db.commit()
                self.atualizar_lista_pedidos()
                messagebox.showinfo("Sucesso", "Histórico antigo removido!")
            except Exception as e:
                print(e)

if __name__ == "__main__":
    app = GestorDelivery()
    app.mainloop()