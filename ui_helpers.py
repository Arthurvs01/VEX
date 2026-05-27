import tkinter as tk
import customtkinter as ctk
from typing import Optional

from styles import Theme


class _ToolTip:
    """Pequeno tooltip (Toplevel) para widgets Tkinter/CTk.
    Mostra um texto ao passar o mouse.
    """
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tipwindow: Optional[tk.Toplevel] = None

    def show(self, event=None):
        if self.tipwindow or not self.text:
            return
        x = event.x_root + 10 if event else self.widget.winfo_rootx() + 20
        y = event.y_root + 10 if event else self.widget.winfo_rooty() + 20
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#333", foreground="white",
                         relief=tk.SOLID, borderwidth=0,
                         font=("Arial", 10))
        label.pack(ipadx=6, ipady=3)

    def hide(self, event=None):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None


def create_tooltip(widget, text: str):
    """Vincula um tooltip simples a um widget."""
    tip = _ToolTip(widget, text)
    widget.bind("<Enter>", tip.show)
    widget.bind("<Leave>", tip.hide)
    widget.bind("<ButtonPress>", tip.hide)
    return tip


def styled_nav_button(parent, texto: str, icone: str, comando, expanded: bool = True):
    """Cria um botão de navegação estilizado para a sidebar."""
    display = f"  {icone}   {texto}" if expanded else icone
    btn = ctk.CTkButton(
        parent, 
        text=display, 
        fg_color="transparent", 
        height=50,
        text_color="white", 
        hover_color=Theme.PRIMARY_HOVER,
        font=Theme.FONT_H2 if expanded else ("Arial", 18), 
        anchor="w" if expanded else "center",
        border_width=0, 
        corner_radius=8,
        command=comando
    )
    return btn


def styled_action_button(parent, text: str, color: str, command, icon: str = ""):
    """Cria um botão de ação com ícone para as telas principais."""
    display = f"{icon} {text}" if icon else text
    btn = ctk.CTkButton(
        parent, 
        text=display, 
        fg_color=color, 
        hover_color=None, # O CTk calcula automaticamente
        height=40, 
        font=("Segoe UI", 12, "bold"),
        corner_radius=6,
        command=command
    )
    return btn
