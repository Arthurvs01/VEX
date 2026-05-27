import os
import sys
import socket
from typing import Union

# Constantes
DEFAULT_IP = "127.0.0.1"
GOOGLE_DNS = ("8.8.8.8", 80)
DEFAULT_CURRENCY_FORMAT = "R$ 0,00"
SOCKET_TIMEOUT = 2


def resource_path(relative_path: str) -> str:
    """
    Retorna o caminho absoluto para recursos, lidando com empacotamento PyInstaller.
    
    Args:
        relative_path: Caminho relativo do recurso
        
    Returns:
        Caminho absoluto completo do recurso
    """
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def obter_ip_local() -> str:
    """
    Retorna o IP da máquina na rede local para o servidor Flask.
    
    Returns:
        IP local em formato string, ou IP padrão (127.0.0.1) se falhar
    """
    try:
        socket_conn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        socket_conn.settimeout(SOCKET_TIMEOUT)
        socket_conn.connect(GOOGLE_DNS)
        ip = socket_conn.getsockname()[0]
        socket_conn.close()
        return ip
    except (socket.error, OSError, IndexError):
        return DEFAULT_IP


def format_currency(value: Union[float, int, str]) -> str:
    """
    Formata valor monetário para o padrão brasileiro (R$).
    
    Args:
        value: Valor a formatar (float, int ou string)
        
    Returns:
        String formatada como "R$ X,XX" ou "R$ 0,00" se inválido
    """
    try:
        numeric_value = float(value)
        return f"R$ {numeric_value:.2f}"
    except (ValueError, TypeError):
        return DEFAULT_CURRENCY_FORMAT