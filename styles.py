import customtkinter as ctk

class Theme:
    """Definições de cores e fontes para manter a identidade visual do sistema."""
    PRIMARY = "#D32F2F"      # Vermelho Material (mais moderno)
    PRIMARY_HOVER = "#B71C1C"
    SUCCESS = "#2E7D32"      # Verde Material (mais sóbrio)
    BG_CARD = "#ffffff"      # Branco puro para cards limpos
    BORDER = "#E0E0E0"       # Cor das bordas
    TEXT_MAIN = "#37474F"    # Azul-cinza escuro para leitura confortável
    
    # Definições de Fontes
    FONT_H1 = ("Segoe UI", 16, "bold")
    FONT_H2 = ("Segoe UI", 14, "bold")
    FONT_LABEL = ("Segoe UI", 11, "bold")

def configurar_estilos_ttk(style):
    """Configura o estilo global para widgets Treeview do Tkinter."""
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