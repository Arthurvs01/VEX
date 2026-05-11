import os
import sys
import socket

def resource_path(relative_path):
    """ Retorna o caminho absoluto para recursos, lidando com o empacotamento do PyInstaller. """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def obter_ip_local():
    """ Retorna o IP da máquina na rede local para o servidor Flask. """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def format_currency(value):
    """ Helper para formatar valores monetários. """
    try:
        return f"R$ {float(value):.2f}"
    except:
        return "R$ 0,00"