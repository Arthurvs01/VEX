import customtkinter as ctk

class Theme:
    """Definições de cores e fontes para manter a identidade visual do sistema."""
    PRIMARY = "#c0392b"      # Vermelho principal
    PRIMARY_HOVER = "#a93226"
    SUCCESS = "#27ae60"      # Verde sucesso
    BG_CARD = "#f9f9f9"      # Fundo dos cards
    BORDER = "#e0e0e0"       # Cor das bordas
    TEXT_MAIN = "#2c3e50"    # Texto principal
    
    # Definições de Fontes
    FONT_H1 = ("Arial", 16, "bold")
    FONT_H2 = ("Arial", 14, "bold")
    FONT_LABEL = ("Arial", 11, "bold")

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