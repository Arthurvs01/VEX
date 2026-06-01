import customtkinter as ctk
from tkinter import ttk
from typing import Tuple


class Theme:
    """Definições de cores e fontes para manter a identidade visual do sistema."""
    
    # Cores Principais
    PRIMARY: str = "#b83237"      # Vermelho mais elegante
    PRIMARY_HOVER: str = "#92242d"
    SECONDARY: str = "#2f3a4f"    # Azul escuro sólido
    ACCENT: str = "#1f8fbe"       # Azul claro para destaques
    SUCCESS: str = "#28a745"      # Verde seguro
    DANGER: str = "#c0392b"
    
    BG_MAIN: str = "#eef2f6"      # Fundo suave com leve tom frio
    BG_CARD: str = "#ffffff"      # Cards brancos para destaque
    BORDER: str = "#d6dbe8"       # Bordas suaves e discretas
    TEXT_MAIN: str = "#2c3e50"    # Azul-escuro para leitura
    TEXT_MUTED: str = "#6c788e"   # Texto secundário vibrante
    HEADING_BG: str = "#f7f9fd"
    WINDOW_BG: str = "#eff3f8"
    
    # Definições de Fontes (font_family, size, weight)
    FONT_H1: Tuple[str, int, str] = ("Segoe UI", 18, "bold")
    FONT_H2: Tuple[str, int, str] = ("Segoe UI", 14, "bold")
    FONT_LABEL: Tuple[str, int, str] = ("Segoe UI", 10, "bold")
    FONT_NORMAL: Tuple[str, int] = ("Segoe UI", 11)
    FONT_SMALL: Tuple[str, int] = ("Segoe UI", 9)
    
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
        background=Theme.BG_CARD,
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
        font=("Segoe UI", 11, "bold"), 
        background=Theme.HEADING_BG, 
        foreground=Theme.TREEVIEW_HEADING_COLOR, 
        relief="flat"
    )