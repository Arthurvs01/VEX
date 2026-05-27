"""
Constantes globais e configurações padrão para o VEX Gestor de Comandas.
"""

# --- Configuração do Aplicativo ---
APP_NAME = "VEX - Gestor de Comandas"
APP_TITLE_LOADING = f"{APP_NAME} [Carregando...]"
WINDOWS_APP_ID = 'vex.gestor.comandas.v1'
WINDOW_SCALE_FACTOR = 0.8  # Janela ocupa 80% da tela

# --- Configurações de Empresa (Padrão) ---
DEFAULT_COMPANY_NAME = "MINHA EMPRESA"
DEFAULT_COMPANY_PHONE = "(00) 0000-0000"
DEFAULT_COMPANY_ADDRESS = ""
DEFAULT_NUM_VIAS = 1

# --- Configurações de Numeração ---
DEFAULT_NUMBERING_TYPE = "SEQUENCIAL"
DEFAULT_HISTORY_TYPE = "ENTREGA"

# --- Configurações de Impressão ---
DEFAULT_PAPER_WIDTH = 80
DEFAULT_HEADER_SIZE = 2      # Índice 2 = Médio (14pt)
DEFAULT_ORDER_SIZE = 0
DEFAULT_ADDRESS_SIZE = 2     # Índice 2 = Médio (10pt)
DEFAULT_ITEMS_SIZE = 2       # Índice 2 = Médio (9pt)
DEFAULT_VALUES_SIZE = 2      # Índice 2 = Médio (9pt)
DEFAULT_PAYMENT_SIZE = 0

# Visibilidade de seções na impressão
DEFAULT_PRINT_VISIBILITY = {
    'header': True,
    'order': True,
    'client': True,
    'items': True,
    'totals': True,
    'payment': True
}
DEFAULT_WEBAPP_MENU_ENABLED = True
DEFAULT_WEBAPP_ADMIN_ENABLED = False

# --- Atalhos de Teclado Padrão ---
DEFAULT_SHORTCUTS = {
    "Delivery": {
        "Finalizar": "F1",
        "Consulta": "F5",
        "Limpar": "F6",
        "Editar Item": "F2",
        "Excluir Item": "Delete"
    },
    "Histórico": {
        "Visualizar": "F1",
        "Editar": "F2",
        "Reimprimir": "F3",
        "Excluir": "Delete"
    },
    "Cardápio": {
        "Salvar": "F2",
        "Limpar": "F3",
        "Excluir": "Delete"
    }
}

# --- Diretórios e Caminhos ---
APPDATA_FOLDER = "VEXGestor"
DATABASE_FILENAME = "delivery.db"

# --- Configurações de UI ---
SIDEBAR_EXPANDED = True
BLOCK_UNKNOWN_NEIGHBORHOOD = True

# --- Valores Padrão ---
DEFAULT_DELIVERY_FEE = 0.0
DEFAULT_EDITING_ORDER_ID = None

# --- Navios de Teclado ---
MODIFIER_KEYS = {"Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Caps_Lock"}
NAVIGATION_KEYS = {"Up", "Down", "Left", "Right"}
NAVIGATION_BINDING_KEYS = ["<Up>", "<Down>", "<Left>", "<Right>"]

# --- Timeouts e Delays ---
DEFERRED_INIT_DELAY = 100  # ms
WEB_SERVER_PORT = 5000
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_DEBUG = False

# --- Estados da Aplicação ---
ORDER_TYPES = ["ENTREGA", "RETIRADA"]
ORDER_TYPE_DELIVERY = "ENTREGA"
ORDER_TYPE_PICKUP = "RETIRADA"
