import textwrap
import time
from datetime import datetime
from tkinter import messagebox

try:
    import win32print
    WIN32_PRINTER_AVAILABLE = True
except ImportError:
    WIN32_PRINTER_AVAILABLE = False

class PrinterManager:
    """Gerencia a comunicação com impressoras térmicas via comandos ESC/POS."""
    
    @staticmethod
    def listar_impressoras():
        """Retorna uma lista de nomes de impressoras disponíveis no sistema."""
        if not WIN32_PRINTER_AVAILABLE:
            return ["Nenhuma"]
        try:
            # Tenta listar usando nível 2 (mais completo)
            printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS, None, 2)
            names = [p['pPrinterName'] for p in printers]
            if not names:
                # Fallback para nível 1 se o nível 2 falhar em retornar nomes
                printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS, None, 1)
                names = [p[2] for p in printers]
            return ["Nenhuma"] + names
        except Exception as e:
            print(f"Erro ao listar impressoras: {e}")
            return ["Nenhuma"]

    @staticmethod
    def imprimir_comanda(config, pedido_info, cliente_info, itens, empresa_info):
        if not WIN32_PRINTER_AVAILABLE:
            return False

        try:
            # Configurações de largura
            limit = int(config.get('largura_papel', 80) * 0.53)
            
            # Comandos ESC/POS (Bytes)
            INIT = b'\x1b@'
            CENTER = b'\x1ba\x01'
            LEFT = b'\x1ba\x00'
            BOLD_ON = b'\x1bE\x01'
            BOLD_OFF = b'\x1bE\x00'
            TAM_MAP = [b'\x1d!\x00', b'\x1d!\x01', b'\x1d!\x10', b'\x1d!\x11', b'\x1d!\x21']
            # Comando ESC t n: Seleciona tabela de caracteres (n=2 é CP850)
            SET_CP850 = b'\x1bt\x02'
            
            raw = INIT + SET_CP850 + CENTER
            
            # 1. Cabeçalho Empresa
            if config.get('vis_cabecalho', True):
                raw += TAM_MAP[config.get('tam_cabecalho', 2)] + BOLD_ON + empresa_info['nome'].encode('cp850', 'ignore') + b'\n'
                raw += TAM_MAP[0] + BOLD_OFF + empresa_info['fone'].encode('cp850', 'ignore') + b'\n'
            
            # 2. Info do Pedido
            if config.get('vis_pedido', True):
                tipo_txt = "ENTREGA" if pedido_info['tipo'] == "ENTREGA" else "RETIRADA"
                raw += b'\n' + TAM_MAP[config.get('tam_pedido', 0)] + BOLD_ON + f"{tipo_txt} N. {pedido_info['num_dia']}".encode('cp850', 'ignore') + BOLD_OFF + b'\n'
                raw += datetime.now().strftime("%d/%m/%Y %H:%M").encode('cp850', 'ignore') + b'\n'
                raw += b'-' * limit + b'\n'
            
            # 3. Cliente
            if config.get('vis_cliente', True):
                raw += LEFT + TAM_MAP[config.get('tam_endereco', 2)]
                cli_txt = f"Cliente: {cliente_info['nome']}\nTel: {cliente_info['tel']}\n"
                if pedido_info['tipo'] == "ENTREGA":
                    cli_txt += f"End: {cliente_info['rua']}, {cliente_info['num']}\nBairro: {cliente_info['bairro']}\n"
                    if cliente_info.get('comp'): cli_txt += f"Comp: {cliente_info['comp']}\n"
                
                for linha in cli_txt.split('\n'):
                    for wrap_l in textwrap.wrap(linha, width=limit):
                        raw += wrap_l.encode('cp850', 'ignore') + b'\n'
                
                raw += b'-' * limit + b'\n'
            
            # 4. Itens
            if config.get('vis_itens', True):
                raw += BOLD_ON + b"ITENS\n" + BOLD_OFF + TAM_MAP[config.get('tam_itens', 2)]
                for val in itens:
                    # val: (ID, Produto, Qtd, PrecoUnit, Total, Obs)
                    qtd_nome = f"{val[2]}x {val[1]}"
                    preco = f"R$ {val[4]}"
                    
                    espacos = limit - len(qtd_nome) - len(preco)
                    if espacos < 1:
                        linhas_nome = textwrap.wrap(qtd_nome, width=limit-10)
                        raw += linhas_nome[0].encode('cp850', 'ignore')
                        espacos = limit - len(linhas_nome[0]) - len(preco)
                        raw += b' ' * espacos + preco.encode('cp850', 'ignore') + b'\n'
                        for extra in linhas_nome[1:]:
                            raw += b'  ' + extra.encode('cp850', 'ignore') + b'\n'
                    else:
                        raw += qtd_nome.encode('cp850', 'ignore') + (b' ' * espacos) + preco.encode('cp850', 'ignore') + b'\n'
                    
                    if val[5]: # Observação
                        for obs_l in textwrap.wrap(f"  Obs: {val[5]}", width=limit):
                            raw += obs_l.encode('cp850', 'ignore') + b'\n'
                
                raw += b'-' * limit + b'\n'
            
            # 5. Totais
            if config.get('vis_totais', True):
                raw += TAM_MAP[config.get('tam_valores', 2)]
                vf = pedido_info['valores']
                
                total_lines = [("Sub-total:", vf.get('subtotal', 0))]
                if vf.get('taxa', 0) > 0: total_lines.append(("Taxa Entrega:", vf['taxa']))
                if vf.get('acrescimos', 0) > 0: total_lines.append(("Acréscimos:", vf['acrescimos']))
                if vf.get('descontos', 0) > 0: total_lines.append(("Descontos:", -vf['descontos']))
                
                total = vf.get('total', 0)
                total_lines.append(("TOTAL:", total))
                
                for lbl, v in total_lines:
                    txt_v = f"R$ {v:.2f}"
                    espacos = limit - len(lbl) - len(txt_v)
                    raw += lbl.encode('cp850', 'ignore') + (b' ' * max(1, espacos)) + txt_v.encode('cp850', 'ignore') + b'\n'

                # 5.1 Troco (Exibir apenas se houver)
                recebido = vf.get('recebido', 0)
                if recebido > total:
                    troco = recebido - total
                    lbl_t, txt_t = "Troco:", f"R$ {troco:.2f}"
                    esp = limit - len(lbl_t) - len(txt_t)
                    raw += lbl_t.encode('cp850', 'ignore') + (b' ' * max(1, esp)) + txt_t.encode('cp850', 'ignore') + b'\n'
            
            # 6. Pagamento
            if config.get('vis_pagamento', True):
                vf = pedido_info['valores']
                raw += b'\n' + TAM_MAP[config.get('tam_pagamento', 0)] + BOLD_ON + CENTER + f"PAGAMENTO: {vf.get('pagamento', 'N/A')}".encode('cp850', 'ignore') + b'\n'
            
            # Corte de papel
            raw += b'\n' * 3 + b'\x1dV\x42\x00'
            
            # Envio
            printer_name = config.get('printer_name') or win32print.GetDefaultPrinter()
            hPrinter = win32print.OpenPrinter(printer_name)
            try:
                for _ in range(config.get('num_vias', 1)):
                    win32print.StartDocPrinter(hPrinter, 1, ("Comanda VEX", None, "RAW"))
                    win32print.StartPagePrinter(hPrinter)
                    win32print.WritePrinter(hPrinter, raw)
                    win32print.EndPagePrinter(hPrinter)
                    win32print.EndDocPrinter(hPrinter)
                    time.sleep(0.1)
                return True
            finally:
                win32print.ClosePrinter(hPrinter)
                
        except Exception as e:
            print(f"Erro de Impressão: {e}")
            return False