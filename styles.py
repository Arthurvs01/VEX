import customtkinter as ctk
from tkinter import ttk
from typing import Tuple


class Theme:
    """Definições de cores e fontes para manter a identidade visual do sistema."""
    
    # Cores Principais
    PRIMARY: str = "#e74c3c"      # Vermelho vibrante
    PRIMARY_HOVER: str = "#c0392b"
    SECONDARY: str = "#34495e"    # Azul escuro/Cinza para elementos neutros
    ACCENT: str = "#3498db"       # Azul para informações e edição
    SUCCESS: str = "#2ecc71"      # Verde Esmeralda
    DANGER: str = "#e74c3c"
    
    BG_MAIN: str = "#f4f7f6"      # Fundo geral levemente cinza
    BG_CARD: str = "#ffffff"      # Cards brancos para destaque
    BORDER: str = "#dcdde1"       # Bordas mais suaves
    TEXT_MAIN: str = "#2f3640"    # Cinza muito escuro para leitura
    TEXT_MUTED: str = "#7f8c8d"   # Texto secundário
    HEADING_BG: str = "#f8f9fa"
    
    # Definições de Fontes (font_family, size, weight)
    FONT_H1: Tuple[str, int, str] = ("Segoe UI", 18, "bold")
    FONT_H2: Tuple[str, int, str] = ("Segoe UI", 14, "bold")
    FONT_LABEL: Tuple[str, int, str] = ("Segoe UI", 10, "bold")
    FONT_NORMAL: Tuple[str, int] = ("Segoe UI", 11)
    
    # Constantes de interface
    TREEVIEW_ROW_HEIGHT: int = 38
    TREEVIEW_HEADING_COLOR: str = "#555"


def configurar_estilos_ttk(style: ttk.Style) -> None:
    """
    Configura o estilo global para widgets Treeview do Tkinter.
    
    Args:
        style: Objeto ttk.Style para configurar
    """
    style.theme_use("clam")
    
    # Configuração da Treeview
    style.configure(
        "Treeview", 
        background="white",
        foreground=Theme.TEXT_MAIN, 
        rowheight=Theme.TREEVIEW_ROW_HEIGHT, 
        fieldbackground="white",
        font=Theme.FONT_NORMAL,
        borderwidth=0,
        relief="flat"
    )
    
    # Mapa de cores para Treeview
    style.map(
        "Treeview", 
        background=[('selected', Theme.PRIMARY)], 
        foreground=[('selected', 'white')]
    )
    
    # Configuração do cabeçalho da Treeview
    style.configure(
        "Treeview.Heading", 
        font=("Arial", 11, "bold"), 
        background=Theme.HEADING_BG, 
        foreground=Theme.TREEVIEW_HEADING_COLOR, 
        relief="flat"
    )