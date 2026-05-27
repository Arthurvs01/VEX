import textwrap
import time
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from tkinter import messagebox

try:
    import win32print
    WIN32_PRINTER_AVAILABLE = True
except ImportError:
    WIN32_PRINTER_AVAILABLE = False


# Constantes ESC/POS
class ESCPOSCommands:
    """Comandos e configurações para impressoras térmicas ESC/POS."""
    INIT = b'\x1b@'
    CENTER = b'\x1ba\x01'
    LEFT = b'\x1ba\x00'
    BOLD_ON = b'\x1bE\x01'
    BOLD_OFF = b'\x1bE\x00'
    SET_CP850 = b'\x1bt\x02'  # Tabela CP850
    NEWLINE = b'\r\n'
    CUT_PAPER = b'\x1dV\x42\x00'
    # Mapa de tamanhos [normal, pequeno, médio-pequeno, médio, grande-médio, grande]
    SIZE_MAP = [b'\x1d!\x00', b'\x1d!\x01', b'\x1d!\x10', 
                b'\x1d!\x11', b'\x1d!\x21']
    DEFAULT_PAPER_WIDTH = 80
    DEFAULT_SPACING = 3
    SEPARATOR = b'-'


class PrinterManager:
    """Gerencia a comunicação com impressoras térmicas via comandos ESC/POS."""
    
    @staticmethod
    def listar_impressoras() -> List[str]:
        """
        Retorna uma lista de nomes de impressoras disponíveis no sistema.
        
        Returns:
            Lista de nomes de impressoras ou ["Nenhuma"] se indisponível
        """
        if not WIN32_PRINTER_AVAILABLE:
            return ["Nenhuma"]
        try:
            # Tenta listar usando nível 2 (mais completo)
            printers = win32print.EnumPrinters(
                win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS, 
                None, 2
            )
            names = [p['pPrinterName'] for p in printers]
            if not names:
                # Fallback para nível 1 se nível 2 falhar
                printers = win32print.EnumPrinters(
                    win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS, 
                    None, 1
                )
                names = [p[2] for p in printers]
            return ["Nenhuma"] + names
        except Exception as e:
            print(f"Erro ao listar impressoras: {e}")
            return ["Nenhuma"]

    @staticmethod
    def _encode_text(text: str) -> bytes:
        """Codifica texto para CP850, ignorando caracteres incompatíveis."""
        return text.encode('cp850', 'ignore')

    @staticmethod
    def _format_item_line(qtd_nome: str, preco: str, limit: int) -> bytes:
        """
        Formata uma linha de item com espaçamento e alinhamento.
        
        Args:
            qtd_nome: String com quantidade e nome do item
            preco: String com preço formatado
            limit: Largura do papel em caracteres
            
        Returns:
            Bytes formatados para impressão
        """
        raw = b''
        espacos = limit - len(qtd_nome) - len(preco)
        
        if espacos < 1:
            # Quebra o nome se muito longo
            linhas_nome = textwrap.wrap(qtd_nome, width=limit - 10)
            raw += PrinterManager._encode_text(linhas_nome[0])
            espacos = limit - len(linhas_nome[0]) - len(preco)
            raw += b' ' * espacos + PrinterManager._encode_text(preco) + ESCPOSCommands.NEWLINE
            for extra in linhas_nome[1:]:
                raw += b'  ' + PrinterManager._encode_text(extra) + ESCPOSCommands.NEWLINE
        else:
            raw += PrinterManager._encode_text(qtd_nome)
            raw += b' ' * espacos
            raw += PrinterManager._encode_text(preco) + ESCPOSCommands.NEWLINE
        
        return raw

    @staticmethod
    def imprimir_comanda(
        config: Dict, 
        pedido_info: Dict, 
        cliente_info: Dict, 
        itens: List[Tuple], 
        empresa_info: Dict
    ) -> bool:
        """
        Imprime comanda em impressora térmica usando comandos ESC/POS.
        
        Args:
            config: Dicionário de configurações de impressão
            pedido_info: Informações do pedido
            cliente_info: Dados do cliente
            itens: Lista de itens (tuplas com ID, Produto, Qtd, PrecoUnit, Total, Obs)
            empresa_info: Informações da empresa
            
        Returns:
            True se impressão bem-sucedida, False caso contrário
        """
        if not WIN32_PRINTER_AVAILABLE:
            return False

        try:
            # Configurações de largura
            limit = int(config.get('largura_papel', ESCPOSCommands.DEFAULT_PAPER_WIDTH) * 0.53)
            
            raw = ESCPOSCommands.INIT + ESCPOSCommands.SET_CP850 + ESCPOSCommands.CENTER
            
            # 1. Cabeçalho Empresa
            if config.get('vis_cabecalho', True):
                raw += (ESCPOSCommands.SIZE_MAP[config.get('tam_cabecalho', 2)] + 
                        ESCPOSCommands.BOLD_ON + 
                        PrinterManager._encode_text(empresa_info['nome']) + 
                        ESCPOSCommands.NEWLINE)
                raw += (ESCPOSCommands.SIZE_MAP[0] + ESCPOSCommands.BOLD_OFF + 
                        PrinterManager._encode_text(empresa_info['fone']) + 
                        ESCPOSCommands.NEWLINE)
            
            # 2. Info do Pedido
            if config.get('vis_pedido', True):
                tipo_txt = "ENTREGA" if pedido_info['tipo'] == "ENTREGA" else "RETIRADA"
                raw += (ESCPOSCommands.NEWLINE + 
                        ESCPOSCommands.SIZE_MAP[config.get('tam_pedido', 0)] + 
                        ESCPOSCommands.BOLD_ON + 
                        PrinterManager._encode_text(f"{tipo_txt} N. {pedido_info['num_dia']}") + 
                        ESCPOSCommands.BOLD_OFF + 
                        ESCPOSCommands.NEWLINE)
                raw += (PrinterManager._encode_text(datetime.now().strftime("%d/%m/%Y %H:%M")) + 
                        ESCPOSCommands.NEWLINE +
                        ESCPOSCommands.SEPARATOR * limit + ESCPOSCommands.NEWLINE)
            
            # 3. Cliente
            if config.get('vis_cliente', True):
                raw += (ESCPOSCommands.LEFT + 
                        ESCPOSCommands.SIZE_MAP[config.get('tam_endereco', 2)])
                
                cli_txt = f"Cliente: {cliente_info['nome']}\nTel: {cliente_info['tel']}\n"
                if pedido_info['tipo'] == "ENTREGA":
                    cli_txt += f"End: {cliente_info['rua']}, {cliente_info['num']}\nBairro: {cliente_info['bairro']}\n"
                    if cliente_info.get('comp'): 
                        cli_txt += f"Comp: {cliente_info['comp']}\n"
                
                for linha in cli_txt.split('\n'):
                    for wrap_l in textwrap.wrap(linha, width=limit):
                        raw += PrinterManager._encode_text(wrap_l) + ESCPOSCommands.NEWLINE
                
                raw += ESCPOSCommands.SEPARATOR * limit + ESCPOSCommands.NEWLINE
            
            # 4. Itens
            if config.get('vis_itens', True):
                raw += (ESCPOSCommands.BOLD_ON + 
                        PrinterManager._encode_text("ITENS") + 
                        ESCPOSCommands.NEWLINE + ESCPOSCommands.BOLD_OFF + 
                        ESCPOSCommands.SIZE_MAP[config.get('tam_itens', 2)])
                
                for val in itens:
                    # val: (ID, Produto, Qtd, PrecoUnit, Total, Obs)
                    qtd_nome = f"{val[2]}x {val[1]}"
                    preco = f"R$ {val[4]}"
                    raw += PrinterManager._format_item_line(qtd_nome, preco, limit)
                    
                    if val[5]:  # Observação
                        for obs_l in textwrap.wrap(f"  Obs: {val[5]}", width=limit):
                            raw += PrinterManager._encode_text(obs_l) + ESCPOSCommands.NEWLINE
                
                raw += ESCPOSCommands.SEPARATOR * limit + ESCPOSCommands.NEWLINE
            
            # 5. Totais
            if config.get('vis_totais', True):
                raw += ESCPOSCommands.SIZE_MAP[config.get('tam_valores', 2)]
                vf = pedido_info['valores']
                
                total_lines: List[Tuple[str, float]] = [
                    ("Sub-total:", vf.get('subtotal', 0))
                ]
                if vf.get('taxa', 0) > 0: 
                    total_lines.append(("Taxa Entrega:", vf['taxa']))
                if vf.get('acrescimos', 0) > 0: 
                    total_lines.append(("Acréscimos:", vf['acrescimos']))
                if vf.get('descontos', 0) > 0: 
                    total_lines.append(("Descontos:", -vf['descontos']))
                
                total = vf.get('total', 0)
                total_lines.append(("TOTAL:", total))
                
                for lbl, v in total_lines:
                    txt_v = f"R$ {v:.2f}"
                    espacos = limit - len(lbl) - len(txt_v)
                    raw += (PrinterManager._encode_text(lbl) + 
                            (b' ' * max(1, espacos)) + 
                            PrinterManager._encode_text(txt_v) + 
                            ESCPOSCommands.NEWLINE)

                # 5.1 Troco (Exibir apenas se houver)
                recebido = vf.get('recebido', 0)
                if recebido > total:
                    troco = recebido - total
                    lbl_t, txt_t = "Troco:", f"R$ {troco:.2f}"
                    esp = limit - len(lbl_t) - len(txt_t)
                    raw += (PrinterManager._encode_text(lbl_t) + 
                            (b' ' * max(1, esp)) + 
                            PrinterManager._encode_text(txt_t) + 
                            ESCPOSCommands.NEWLINE)
            
            # 6. Pagamento
            if config.get('vis_pagamento', True):
                vf = pedido_info['valores']
                raw += (ESCPOSCommands.NEWLINE + 
                        ESCPOSCommands.SIZE_MAP[config.get('tam_pagamento', 0)] + 
                        ESCPOSCommands.BOLD_ON + 
                        ESCPOSCommands.CENTER + 
                        PrinterManager._encode_text(f"PAGAMENTO: {vf.get('pagamento', 'N/A')}") + 
                        ESCPOSCommands.NEWLINE)
            
            # Corte de papel
            raw += ESCPOSCommands.NEWLINE * ESCPOSCommands.DEFAULT_SPACING + ESCPOSCommands.CUT_PAPER
            
            # Envio
            printer_name = config.get('printer_name') or win32print.GetDefaultPrinter()
            hPrinter = win32print.OpenPrinter(printer_name)
            try:
                for _ in range(config.get('num_vias', 1)):
                    win32print.StartDocPrinter(hPrinter, 1, ("Comanda VEX", None, "RAW"))
                    win32print.WritePrinter(hPrinter, raw)
                    win32print.EndDocPrinter(hPrinter)
                    time.sleep(0.1)
                return True
            finally:
                win32print.ClosePrinter(hPrinter)
                
        except Exception as e:
            print(f"Erro de Impressão: {e}")
            return False