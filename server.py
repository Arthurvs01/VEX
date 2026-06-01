import os
import sqlite3
import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple
from printer import PrinterManager
from flask import Flask, jsonify, request, send_file, render_template_string


# Constantes
DB_QUERY_LIMIT = 20
FLASK_PORT = 5000
FLASK_HOST = "0.0.0.0"
LOGO_404_CODE = 404


def criar_app_vex(data_dir: str, empresa_info: Dict[str, Any], config: Dict[str, bool]) -> Flask:
    """
    Cria e configura a aplicação Flask para o sistema VEX.
    
    Args:
        data_dir: Diretório onde está o banco de dados
        empresa_info: Dicionário com informações da empresa (nome, fone, end, logo_path)
        config: Dicionário com flags 'menu_enabled' e 'admin_enabled'
        
    Returns:
        Aplicação Flask configurada
    """
    app = Flask(__name__)
    
    # Silenciar logs desnecessários no console
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    def get_db_connection() -> sqlite3.Connection:
        """Estabelece conexão com o banco de dados."""
        conn = sqlite3.connect(os.path.join(data_dir, "delivery.db"))
        conn.row_factory = sqlite3.Row
        return conn

    def get_sys_config() -> Dict[str, Any]:
        """Recupera todas as configurações do banco de dados."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT chave, valor FROM config")
                return {chave: valor for chave, valor in cursor.fetchall()}
        except Exception:
            return {}

    def get_next_num_dia(tipo: str) -> int:
        """Gera o próximo número do dia para o pedido."""
        conn = get_db_connection()
        cursor = conn.cursor()
        dia_hoje = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("SELECT COALESCE(MAX(num_dia), 0) + 1 FROM pedidos WHERE DATE(data_pedido, 'localtime') = ? AND tipo = ?", (dia_hoje, tipo))
        res = cursor.fetchone()[0]
        conn.close()
        return res

    @app.before_request
    def check_access():
        """Bloqueia acesso se o módulo estiver desligado."""
        if (request.path.startswith('/admin') or request.path.startswith('/api/admin')) and not config.get('admin_enabled'):
            return "Módulo Administrativo Web desativado nas configurações do desktop.", 403

    @app.route('/logo')
    def get_logo():
        """Retorna a imagem do logo da empresa."""
        path = empresa_info.get('logo_path')
        if path and os.path.exists(path):
            try:
                return send_file(path)
            except Exception as e:
                print(f"Erro ao servir logo: {e}")
                return "", LOGO_404_CODE
        return "", LOGO_404_CODE

    @app.route('/api/menu')
    def api_menu():
        """
        API para obter menu com paginação.
        
        Query params:
            cat: Categoria selecionada (default: 'TODOS')
            page: Número da página (default: 1)
            
        Returns:
            JSON com categorias, produtos e indicador de próxima página
        """
        cat_selecionada = request.args.get('cat', 'TODOS')
        page = int(request.args.get('page', 1))
        per_page = DB_QUERY_LIMIT
        offset = (page - 1) * per_page
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                # Categorias
                cursor.execute(
                    """SELECT DISTINCT c.nome FROM categorias c 
                       JOIN produtos p ON c.nome = p.categoria 
                       WHERE p.visivel_web = 1 ORDER BY c.ordem, c.nome"""
                )
                categorias = [r[0] for r in cursor.fetchall()]

                # Produtos
                query = "SELECT id_produto, nome, preco, ingredientes FROM produtos WHERE visivel_web = 1"
                params: List[Any] = []
                if cat_selecionada != 'TODOS':
                    query += " AND categoria = ?"
                    params.append(cat_selecionada)

                query += " ORDER BY (id_produto >= 100), CASE WHEN id_produto < 100 THEN id_produto ELSE 0 END, nome LIMIT ? OFFSET ?"
                params.extend([per_page, offset])

                cursor.execute(query, params)
                produtos = [list(row) for row in cursor.fetchall()]
            
            return jsonify({
                "categorias": categorias,
                "produtos": produtos,
                "has_next": len(produtos) == per_page
            })
        except sqlite3.DatabaseError as e:
            print(f"Erro ao consultar banco de dados: {e}")
            return jsonify({"error": "Erro ao carregar menu"}), 500
        except Exception as e:
            print(f"Erro inesperado em /api/menu: {e}")
            return jsonify({"error": "Erro interno"}), 500

    # --- API ADMIN ---
    @app.route('/api/admin/buscar_cliente/<tel>')
    def api_admin_buscar_cliente(tel):
        """Busca dados de um cliente pelo telefone."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT nome, bairro, rua, numero, complemento FROM clientes WHERE telefone = ?", (tel,))
                res = cursor.fetchone()
            return jsonify(res if res else None)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/admin/config')
    def api_admin_config():
        """Retorna as configurações atuais do sistema para o painel web."""
        return jsonify({
            "empresa": {
                "nome": empresa_info.get('nome'),
                "fone": empresa_info.get('fone'),
                "end": empresa_info.get('end')
            },
            "servidores": config
        })

    @app.route('/api/admin/produtos')
    def api_admin_produtos():
        """Retorna lista de todos os produtos para gestão web."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id_produto, nome, preco, categoria, visivel_web FROM produtos ORDER BY categoria, nome")
                rows = [list(row) for row in cursor.fetchall()]
            return jsonify(rows)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/admin/detalhes_pedido/<int:id_pedido>')
    def api_admin_detalhes_pedido(id_pedido):
        """Retorna todos os dados de um pedido específico."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT p.*, c.nome as cliente_nome, c.bairro, c.rua, c.numero, c.complemento
                    FROM pedidos p LEFT JOIN clientes c ON p.telefone_cliente = c.telefone
                    WHERE p.id_pedido = ?
                """, (id_pedido,))
                pedido = cursor.fetchone()

                if not pedido:
                    return jsonify({"error": "Pedido não encontrado"}), 404

                cursor.execute("""
                    SELECT i.*, pr.nome 
                    FROM itens_pedido i JOIN produtos pr ON i.id_produto = pr.id_produto
                    WHERE i.id_pedido = ?
                """, (id_pedido,))
                itens = [list(row) for row in cursor.fetchall()]
            return jsonify({"pedido": pedido, "itens": itens})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/admin/pedidos')
    def api_admin_pedidos():
        """Retorna pedidos do dia para o painel administrativo."""
        data_ref = request.args.get('data', datetime.now().strftime("%Y-%m-%d"))
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT p.id_pedido, c.nome, p.total, p.data_pedido, p.tipo, p.num_dia 
                    FROM pedidos p LEFT JOIN clientes c ON p.telefone_cliente = c.telefone
                    WHERE DATE(p.data_pedido, 'localtime') = ? ORDER BY p.id_pedido DESC
                """, (data_ref,))
                rows = [list(row) for row in cursor.fetchall()]
            return jsonify(rows)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/admin/excluir/<int:id_pedido>', methods=['POST'])
    def api_admin_excluir(id_pedido):
        """Exclui um pedido e seus itens."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM itens_pedido WHERE id_pedido = ?", (id_pedido,))
                cursor.execute("DELETE FROM pedidos WHERE id_pedido = ?", (id_pedido,))
                conn.commit()
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/admin/reimprimir/<int:id_pedido>', methods=['POST'])
    def api_admin_reimprimir(id_pedido):
        """Gera e envia a comanda para a impressora configurada no desktop."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM pedidos WHERE id_pedido = ?", (id_pedido,))
                p = cursor.fetchone()
                cursor.execute("SELECT i.id_produto, pr.nome, i.quantidade, i.preco_unitario, (i.quantidade*i.preco_unitario), i.observacao FROM itens_pedido i JOIN produtos pr ON i.id_produto = pr.id_produto WHERE i.id_pedido = ?", (id_pedido,))
                itens = cursor.fetchall()
                cursor.execute("SELECT nome, telefone, rua, numero, bairro, complemento FROM clientes WHERE telefone = ?", (p[1],))
                c = cursor.fetchone()

            # Configurações do sistema
            sys_cfg = get_sys_config()
            
            # Formatação para PrinterManager
            config = {
                'largura_papel': int(sys_cfg.get('largura_papel', 80)),
                'printer_name': sys_cfg.get('impressora_selecionada'),
                'num_vias': int(sys_cfg.get('num_vias', 1)),
                'vis_cabecalho': sys_cfg.get('vis_cabecalho', 'True') == 'True',
                'vis_pedido': sys_cfg.get('vis_pedido', 'True') == 'True',
                'vis_cliente': sys_cfg.get('vis_cliente', 'True') == 'True',
                'vis_itens': sys_cfg.get('vis_itens', 'True') == 'True',
                'vis_totais': sys_cfg.get('vis_totais', 'True') == 'True',
                'vis_pagamento': sys_cfg.get('vis_pagamento', 'True') == 'True',
                'tam_cabecalho': int(sys_cfg.get('tam_cabecalho', 2)),
                'tam_pedido': int(sys_cfg.get('tam_pedido', 0)),
                'tam_endereco': int(sys_cfg.get('tam_endereco', 2)),
                'tam_itens': int(sys_cfg.get('tam_itens', 2)),
                'tam_valores': int(sys_cfg.get('tam_valores', 2)),
                'tam_pagamento': int(sys_cfg.get('tam_pagamento', 0))
            }
            
            pedido_info = {
                'num_dia': p[10], 'tipo': p[8], 
                'valores': {'subtotal': p[2], 'taxa': p[3], 'acrescimos': p[4], 'descontos': p[5], 'total': p[6], 'pagamento': p[7], 'recebido': p[6]}
            }
            cliente_info = {'nome': c[0], 'tel': c[1], 'rua': c[2], 'num': c[3], 'bairro': c[4], 'comp': c[5]}
            empresa_info_print = {'nome': sys_cfg.get('nome_empresa', 'VEX'), 'fone': sys_cfg.get('fone_empresa', '')}

            if PrinterManager.imprimir_comanda(config, pedido_info, cliente_info, itens, empresa_info_print):
                return jsonify({"status": "success"})
            return jsonify({"error": "Falha na impressora"}), 500
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/admin/finalizar', methods=['POST'])
    def api_admin_finalizar():
        """Salva ou atualiza um pedido vindo da interface web."""
        data = request.json
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                c = data['cliente']
                cursor.execute("""INSERT OR REPLACE INTO clientes (telefone, nome, bairro, rua, numero, complemento) 
                                 VALUES (?, ?, ?, ?, ?, ?)""", (c['tel'], c['nome'], c['bairro'], c['rua'], c['num'], c['comp']))
                v = data['valores']
                id_pedido = data.get('id_pedido')
                tipo = data['tipo']
                if id_pedido:
                    cursor.execute("""UPDATE pedidos SET telefone_cliente=?, subtotal=?, taxa=?, acrescimos=?, descontos=?, total=?, forma_pagamento=?, tipo=?
                                     WHERE id_pedido=?""", (c['tel'], v['subtotal'], v['taxa'], v['acrescimos'], v['descontos'], v['total'], v['pagamento'], tipo, id_pedido))
                    cursor.execute("DELETE FROM itens_pedido WHERE id_pedido=?", (id_pedido,))
                else:
                    num_dia = get_next_num_dia(tipo)
                    cursor.execute("""INSERT INTO pedidos (telefone_cliente, subtotal, taxa, acrescimos, descontos, total, forma_pagamento, tipo, num_dia)
                                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", (c['tel'], v['subtotal'], v['taxa'], v['acrescimos'], v['descontos'], v['total'], v['pagamento'], tipo, num_dia))
                    id_pedido = cursor.lastrowid
                for it in data['itens']:
                    cursor.execute("""INSERT INTO itens_pedido (id_pedido, id_produto, quantidade, preco_unitario, observacao)
                                     VALUES (?, ?, ?, ?, ?)""", (id_pedido, it['id'], it['qtd'], it['preco'], it['obs']))
                conn.commit()
            return jsonify({"status": "success", "id_pedido": id_pedido})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/admin')
    def admin_index():
        """Página principal do Admin Web."""
        if not config.get('admin_enabled'):
            return "Acesso Negado", 403
        try:
            return render_template_string(
                _get_admin_html(), 
                nome=empresa_info.get('nome', 'VEX Admin')
            )
        except Exception as e:
            print(f"Erro ao renderizar admin: {e}")
            return "Erro interno", 500

    @app.route('/')
    def index():
        """Página do Cardápio."""
        if not config.get('menu_enabled'):
            return "O Cardápio Digital está temporariamente indisponível.", 503
        try:
            return render_template_string(
                _get_cardapio_html(),
                nome=empresa_info.get('nome', 'Cardápio'),
                fone=empresa_info.get('fone', ''),
                end=empresa_info.get('end', '')
            )
        except Exception as e:
            print(f"Erro ao renderizar página principal: {e}")
            return "<h1>Erro ao carregar cardápio</h1>", 500

    return app


def _get_cardapio_html() -> str:
    """
    Retorna o HTML do cardápio web.
    
    Returns:
        String HTML com template Jinja2
    """
    return """
        <!DOCTYPE html>
        <html lang="pt-br">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
            <title>{{ nome }}</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <style>
                .bg-primary { background-color: #c0392b; }
                .text-primary { color: #c0392b; }
                .cat-scroll::-webkit-scrollbar { display: none; }
                .dots-leader { flex-grow: 1; border-bottom: 2px dotted #ccc; margin: 0 5px; height: 14px; }
            </style>
        </head>
        <body class="bg-white pb-2 text-slate-800">
            <header class="bg-primary text-white p-3 flex items-center gap-3 shadow-md">
                <img src="/logo" class="w-10 h-10 rounded-full bg-white object-cover border border-white" onerror="this.style.display='none'">
                <div>
                    <h1 class="text-lg font-bold leading-tight">{{ nome }}</h1>
                    <p class="text-xs opacity-80">{{ fone }}</p>
                    <p class="text-xs opacity-80">{{ end }}</p>
                </div>
            </header>
            <div id="categorias" class="flex overflow-x-auto p-2 gap-1.5 cat-scroll sticky top-0 bg-white/95 backdrop-blur-sm z-10 border-b">
                <button onclick="setCategory('TODOS')" class="cat-btn bg-primary text-white px-3 py-1 rounded-md text-xs font-bold whitespace-nowrap border border-primary">TODOS</button>
            </div>
            <main id="menu" class="px-3 py-1 space-y-2"></main>
            <div class="flex justify-center items-center gap-3 mt-2">
                <button id="btn-prev" onclick="changePage(-1)" class="bg-white border px-3 py-1 rounded font-bold text-xs disabled:opacity-30">Anterior</button>
                <span id="page-num" class="text-xs font-bold text-gray-400">1</span>
                <button id="btn-next" onclick="changePage(1)" class="bg-white border px-3 py-1 rounded font-bold text-xs disabled:opacity-30">Próximo</button>
            </div>
            <script>
                let currentCat = 'TODOS';
                let currentPage = 1;
                
                async function loadMenu() {
                    try {
                        const res = await fetch(`/api/menu?cat=${encodeURIComponent(currentCat)}&page=${currentPage}`);
                        if (!res.ok) throw new Error('Erro ao carregar menu');
                        const data = await res.json();
                        renderCategories(data.categorias);
                        renderProducts(data.produtos);
                        document.getElementById('page-num').innerText = currentPage;
                        document.getElementById('btn-prev').disabled = currentPage === 1;
                        document.getElementById('btn-next').disabled = !data.has_next;
                    } catch (err) {
                        console.error('Erro:', err);
                        document.getElementById('menu').innerHTML = '<p class="text-center text-red-500 py-10">Erro ao carregar menu</p>';
                    }
                }
                
                function renderCategories(cats) {
                    const catDiv = document.getElementById('categorias');
                    if(catDiv.children.length > 1) return;
                    cats.forEach(cat => {
                        catDiv.innerHTML += `<button onclick="setCategory('${cat}')" class="cat-btn bg-white text-black px-3 py-1 rounded-md text-xs font-bold whitespace-nowrap border">${cat}</button>`;
                    });
                }
                
                function renderProducts(prods) {
                    const menuDiv = document.getElementById('menu');
                    menuDiv.innerHTML = prods.length ? '' : '<p class="text-center text-gray-400 py-10">Nenhum item nesta página.</p>';
                    prods.forEach(p => { 
                        const idRaw = p[0];
                        const nome = p[1];
                        const preco = p[2].toFixed(2);
                        const ingredientes = p[3] ? `(${p[3]})` : '';
                        const idDisplay = idRaw < 100 ? idRaw.toString().padStart(2, '0') + '. ' : '';
                        let itemHtml = `<div class="flex flex-col border-b border-gray-50 pb-1">`;
                        itemHtml += `<div class="flex justify-between items-end">`;
                        itemHtml += `<span class="text-sm font-bold text-gray-800">${idDisplay}${nome}</span>`;
                        if (!ingredientes) {
                            itemHtml += `<div class="dots-leader"></div><span class="text-sm font-bold text-primary">R$ ${preco}</span>`;
                        }
                        itemHtml += `</div>`;
                        if (ingredientes) {
                            itemHtml += `<div class="flex justify-between items-end text-xs text-gray-500 italic"><span>${ingredientes}</span><div class="dots-leader"></div><span class="text-sm font-bold text-primary">R$ ${preco}</span></div>`;
                        }
                        itemHtml += `</div>`;
                        menuDiv.innerHTML += itemHtml;
                    });
                }
                
                function setCategory(cat) {
                    currentCat = cat;
                    currentPage = 1;
                    loadMenu();
                    document.querySelectorAll('.cat-btn').forEach(btn => {
                        if(btn.innerText === cat) {
                            btn.classList.add('bg-primary', 'text-white');
                            btn.classList.remove('bg-white', 'text-black');
                        } else {
                            btn.classList.remove('bg-primary', 'text-white');
                            btn.classList.add('bg-white', 'text-black');
                        }
                    });
                }
                
                function changePage(step) {
                    currentPage += step;
                    loadMenu();
                    window.scrollTo({top: 0, behavior: 'smooth'});
                }
                
                loadMenu();
            </script>
        </body>
        </html>
        """

def _get_admin_html() -> str:
    """HTML Minimalista para o Dashboard Administrativo Mobile."""
    return """
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>VEX Admin - {{ nome }}</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            .bg-vex-primary { background-color: #e74c3c; }
            .text-vex-primary { color: #e74c3c; }
            .bg-vex-secondary { background-color: #34495e; }
            .active-tab { color: #e74c3c !important; border-top: 3px solid #e74c3c; }
        </style>
    </head>
    <body class="bg-slate-100 pb-20 text-slate-800">
        <nav class="bg-vex-secondary text-white p-4 sticky top-0 shadow-lg z-20">
            <h1 class="font-bold text-center">ADMINISTRAÇÃO VEX</h1>
        </nav>
        
        <main id="main-content" class="p-4 space-y-4 relative">
            <div id="view-pedidos" class="tab-view">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-xs font-bold text-slate-500 tracking-widest uppercase">Pedidos de Hoje</h2>
                    <button onclick="abrirModalPedido()" class="bg-vex-primary text-white text-[10px] font-bold px-3 py-1.5 rounded-lg shadow-md">+ NOVO PEDIDO</button>
                </div>
                <div id="lista-pedidos" class="space-y-3"><p class="text-center text-slate-400 py-4">Carregando...</p></div>
            </div>

            <div id="modal-pedido" class="hidden fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
                <div class="bg-white w-full max-w-lg max-h-[90vh] rounded-2xl overflow-y-auto p-6 shadow-2xl">
                    <div class="flex justify-between items-center mb-6 border-b pb-2">
                        <h3 id="modal-titulo" class="font-bold text-vex-secondary">NOVO PEDIDO</h3>
                        <button onclick="fecharModalPedido()" class="text-slate-400 text-2xl">&times;</button>
                    </div>
                    <div class="space-y-3 mb-6">
                        <div class="grid grid-cols-2 gap-3">
                            <input id="p-tel" placeholder="Telefone" onblur="buscarClienteWeb()" class="p-2 bg-slate-50 border rounded-lg text-sm w-full">
                            <input id="p-nome" placeholder="Nome Completo" class="p-2 bg-slate-50 border rounded-lg text-sm w-full">
                        </div>
                        <div class="grid grid-cols-2 gap-3">
                            <input id="p-bairro" placeholder="Bairro" class="p-2 bg-slate-50 border rounded-lg text-sm w-full">
                            <input id="p-rua" placeholder="Rua" class="p-2 bg-slate-50 border rounded-lg text-sm w-full">
                        </div>
                        <div class="grid grid-cols-2 gap-3">
                            <input id="p-num" placeholder="Nº" class="p-2 bg-slate-50 border rounded-lg text-sm w-full">
                            <input id="p-comp" placeholder="Comp." class="p-2 bg-slate-50 border rounded-lg text-sm w-full">
                        </div>
                    </div>
                    <div class="border-t pt-4">
                        <div class="flex justify-between items-center mb-2">
                            <h4 class="text-[10px] font-black text-slate-400 uppercase">Itens do Pedido</h4>
                            <button onclick="abrirBuscaProduto()" class="text-vex-primary text-[10px] font-bold">+ ADICIONAR</button>
                        </div>
                        <div id="p-carrinho" class="space-y-2 mb-4"></div>
                        <div class="bg-slate-50 p-3 rounded-xl space-y-2 text-sm border">
                            <div class="flex justify-between"><span>Subtotal</span><span id="p-subtotal">R$ 0,00</span></div>
                            <div class="flex justify-between"><span>Taxa</span><input id="p-taxa" value="0.00" onchange="atualizarTotalWeb()" class="w-16 text-right bg-transparent border-b"></div>
                            <div class="flex justify-between font-bold text-vex-primary text-lg pt-2 border-t"><span>TOTAL</span><span id="p-total">R$ 0,00</span></div>
                        </div>
                    </div>
                    <div class="mt-6 space-y-2">
                        <select id="p-pagamento" class="w-full p-3 bg-slate-100 rounded-xl text-sm font-bold">
                            <option>Dinheiro</option><option>Cartão Crédito</option><option>Cartão Débito</option><option>Pix</option>
                        </select>
                        <select id="p-tipo" class="w-full p-3 bg-slate-100 rounded-xl text-sm font-bold">
                            <option value="ENTREGA">ENTREGA</option><option value="RETIRADA">RETIRADA</option>
                        </select>
                        <button onclick="salvarPedidoWeb()" class="w-full bg-vex-primary text-white p-4 rounded-xl font-bold shadow-lg">FINALIZAR PEDIDO</button>
                    </div>
                </div>
            </div>

            <div id="modal-busca-prod" class="hidden fixed inset-0 bg-black/60 z-[60] p-4 flex items-center justify-center">
                <div class="bg-white w-full max-w-md rounded-2xl p-6 shadow-2xl">
                    <input id="busca-prod-input" placeholder="Buscar produto..." onkeyup="filtrarBuscaProd(this.value)" class="w-full p-3 bg-slate-100 rounded-xl mb-4 border">
                    <div id="lista-busca-prod" class="max-h-60 overflow-y-auto space-y-1"></div>
                    <button onclick="document.getElementById('modal-busca-prod').classList.add('hidden')" class="w-full mt-4 p-2 text-slate-400 font-bold">Fechar</button>
                </div>
            </div>

            <div id="modal-ver" class="hidden fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
                <div class="bg-white w-full max-w-sm rounded-2xl p-6 shadow-2xl overflow-y-auto max-h-[80vh]">
                    <div id="ver-conteudo" class="text-sm font-mono whitespace-pre-wrap"></div>
                    <div class="grid grid-cols-2 gap-2 mt-6">
                        <button id="btn-reimprimir" class="bg-green-500 text-white p-3 rounded-xl font-bold">REIMPRIMIR</button>
                        <button onclick="document.getElementById('modal-ver').classList.add('hidden')" class="bg-slate-200 text-slate-700 p-3 rounded-xl font-bold">FECHAR</button>
                    </div>
                </div>
            </div>

            <div id="view-produtos" class="tab-view hidden">
                <h2 class="text-xs font-bold text-slate-500 mb-4 tracking-widest uppercase">Meus Produtos</h2>
                <div id="lista-produtos" class="space-y-3"></div>
            </div>

            <div id="view-config" class="tab-view hidden">
                <h2 class="text-xs font-bold text-slate-500 mb-4 tracking-widest uppercase">Ajustes do Sistema</h2>
                <div id="info-config" class="bg-white p-5 rounded-xl shadow-sm border space-y-5"></div>
            </div>
        </main>

        <div class="fixed bottom-0 w-full bg-white border-t flex justify-around p-3 z-30 shadow-[0_-2px_10px_rgba(0,0,0,0.05)]">
            <button onclick="switchTab('pedidos')" id="btn-pedidos" class="tab-btn flex flex-col items-center text-slate-400 active-tab">
                <span class="text-xl">🚚</span><span class="text-[10px] font-bold mt-1">PEDIDOS</span>
            </button>
            <button onclick="switchTab('produtos')" id="btn-produtos" class="tab-btn flex flex-col items-center text-slate-400">
                <span class="text-xl">🍔</span><span class="text-[10px] font-bold mt-1">PRODUTOS</span>
            </button>
            <button onclick="switchTab('config')" id="btn-config" class="tab-btn flex flex-col items-center text-slate-400">
                <span class="text-xl">⚙️</span><span class="text-[10px] font-bold mt-1">AJUSTES</span>
            </button>
        </div>

        <script>
            let carrinhoWeb = [];
            let produtosLista = [];
            let pedidoEditandoId = null;

            function switchTab(tab) {
                document.querySelectorAll('.tab-view').forEach(v => v.classList.add('hidden'));
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active-tab'));
                document.getElementById('view-' + tab).classList.remove('hidden');
                document.getElementById('btn-' + tab).classList.add('active-tab');
                if(tab === 'pedidos') fetchPedidos();
                if(tab === 'produtos') fetchProdutos();
                if(tab === 'config') fetchConfig();
            }

            async function fetchPedidos() {
                const res = await fetch('/api/admin/pedidos');
                const data = await res.json();
                const container = document.getElementById('lista-pedidos');
                container.innerHTML = '';
                data.forEach(p => {
                    container.innerHTML += `
                        <div class="p-4 bg-white rounded-xl border border-slate-200 shadow-sm space-y-3">
                            <div class="flex justify-between items-center">
                                <div class="font-bold text-slate-800">#${p[5]} - ${p[1] || 'Avulso'}</div>
                                <div class="text-xs text-slate-500">${p[4]} | ${p[3]}</div>
                            </div>
                            <div class="flex justify-between items-center pt-2 border-t">
                                <div class="font-bold text-green-600 text-sm">R$ ${p[2].toFixed(2)}</div>
                                <div class="flex gap-2">
                                    <button onclick="verPedido(${p[0]})" class="p-1.5 bg-slate-100 rounded-lg text-xs">👁️</button>
                                    <button onclick="editarPedido(${p[0]})" class="p-1.5 bg-blue-50 text-blue-600 rounded-lg text-xs">📝</button>
                                    <button onclick="excluirPedido(${p[0]})" class="p-1.5 bg-red-50 text-red-600 rounded-lg text-xs">❌</button>
                                </div>
                            </div>
                        </div>`;
                });
            }

            async function verPedido(id) {
                const res = await fetch(`/api/admin/detalhes_pedido/${id}`);
                const data = await res.json();
                const p = data.pedido;
                let txt = `PEDIDO #${p[10]} (${p[8]})\\nCliente: ${p[12] || '---'}\\nTel: ${p[1]}\\n`;
                if(p[8]==='ENTREGA') txt += `End: ${p[14]}, ${p[15]}\\nBairro: ${p[13]}\\n`;
                txt += `\\nITENS:\\n`;
                data.itens.forEach(it => {
                    txt += `${it[3]}x ${it[6]} - R$ ${(it[3]*it[4]).toFixed(2)}\\n${it[5] ? ' Obs: '+it[5]+'\\n' : ''}`;
                });
                txt += `\\nSubtotal: R$ ${p[2].toFixed(2)}\\nTaxa: R$ ${p[3].toFixed(2)}\\nTOTAL: R$ ${p[6].toFixed(2)}\\nPGTO: ${p[7]}`;
                document.getElementById('ver-conteudo').innerText = txt;
                document.getElementById('btn-reimprimir').onclick = () => reimprimirPedido(id);
                document.getElementById('modal-ver').classList.remove('hidden');
            }

            async function reimprimirPedido(id) {
                const res = await fetch(`/api/admin/reimprimir/${id}`, {method: 'POST'});
                if(res.ok) alert("Comanda enviada!");
                else alert("Erro ao imprimir.");
            }

            async function excluirPedido(id) {
                if(!confirm("Deseja realmente excluir este pedido?")) return;
                const res = await fetch(`/api/admin/excluir/${id}`, {method: 'POST'});
                if(res.ok) fetchPedidos();
            }

            function abrirModalPedido() {
                pedidoEditandoId = null; carrinhoWeb = [];
                document.getElementById('modal-titulo').innerText = "NOVO PEDIDO";
                document.querySelectorAll('#modal-pedido input').forEach(i => i.value = '');
                document.getElementById('p-taxa').value = '0.00';
                atualizarCarrinhoUI();
                document.getElementById('modal-pedido').classList.remove('hidden');
            }

            async function editarPedido(id) {
                const res = await fetch(`/api/admin/detalhes_pedido/${id}`);
                const data = await res.json();
                const p = data.pedido;
                pedidoEditandoId = id;
                document.getElementById('modal-titulo').innerText = `EDITAR PEDIDO #${p[10]}`;
                document.getElementById('p-tel').value = p[1];
                document.getElementById('p-nome').value = p[12];
                document.getElementById('p-bairro').value = p[13];
                document.getElementById('p-rua').value = p[14];
                document.getElementById('p-num').value = p[15];
                document.getElementById('p-comp').value = p[16];
                document.getElementById('p-taxa').value = p[3].toFixed(2);
                document.getElementById('p-pagamento').value = p[7];
                document.getElementById('p-tipo').value = p[8];
                carrinhoWeb = data.itens.map(it => ({id: it[2], nome: it[6], preco: it[4], qtd: it[3], obs: it[5] || ''}));
                atualizarCarrinhoUI();
                document.getElementById('modal-pedido').classList.remove('hidden');
            }

            function fecharModalPedido() { document.getElementById('modal-pedido').classList.add('hidden'); }

            async function buscarClienteWeb() {
                const tel = document.getElementById('p-tel').value;
                if(!tel) return;
                const res = await fetch(`/api/admin/buscar_cliente/${tel}`);
                const c = await res.json();
                if(c) {
                    document.getElementById('p-nome').value = c[0];
                    document.getElementById('p-bairro').value = c[1];
                    document.getElementById('p-rua').value = c[2];
                    document.getElementById('p-num').value = c[3];
                    document.getElementById('p-comp').value = c[4];
                }
            }

            function abrirBuscaProduto() {
                document.getElementById('modal-busca-prod').classList.remove('hidden');
                document.getElementById('busca-prod-input').value = '';
                filtrarBuscaProd(''); document.getElementById('busca-prod-input').focus();
            }

            function filtrarBuscaProd(txt) {
                const container = document.getElementById('lista-busca-prod');
                container.innerHTML = ''; const t = txt.toLowerCase();
                produtosLista.filter(p => p[1].toLowerCase().includes(t)).forEach(p => {
                    container.innerHTML += `<div onclick="adicionarAoCarrinhoWeb(${p[0]}, '${p[1]}', ${p[2]})" class="p-3 border-b text-sm active:bg-slate-100 flex justify-between">
                        <span>${p[1]}</span><span class="font-bold text-vex-primary">R$ ${p[2].toFixed(2)}</span></div>`;
                });
            }

            function adicionarAoCarrinhoWeb(id, nome, preco) {
                const obs = prompt("Observação (opcional):", "");
                carrinhoWeb.push({id, nome, preco, qtd: 1, obs: obs || ''});
                document.getElementById('modal-busca-prod').classList.add('hidden');
                atualizarCarrinhoUI();
            }

            function removerItemCarrinho(idx) { carrinhoWeb.splice(idx, 1); atualizarCarrinhoUI(); }

            function atualizarCarrinhoUI() {
                const container = document.getElementById('p-carrinho');
                container.innerHTML = carrinhoWeb.length ? '' : '<p class="text-center text-slate-300 py-4 text-xs">Vazio</p>';
                let subtotal = 0;
                carrinhoWeb.forEach((it, i) => {
                    subtotal += it.preco * it.qtd;
                    container.innerHTML += `
                        <div class="flex justify-between items-center bg-slate-50 p-2 rounded-lg text-xs">
                            <div class="flex-1">
                                <div class="font-bold">${it.qtd}x ${it.nome}</div>
                                <div class="text-[10px] text-slate-400 italic">${it.obs}</div>
                            </div>
                            <div class="flex items-center gap-3">
                                <span class="font-bold">R$ ${(it.preco*it.qtd).toFixed(2)}</span>
                                <button onclick="removerItemCarrinho(${i})" class="text-red-500 font-bold px-1">×</button>
                            </div>
                        </div>`;
                });
                document.getElementById('p-subtotal').innerText = `R$ ${subtotal.toFixed(2)}`;
                atualizarTotalWeb();
            }

            function atualizarTotalWeb() {
                const sub = parseFloat(document.getElementById('p-subtotal').innerText.replace('R$ ', ''));
                const taxa = parseFloat(document.getElementById('p-taxa').value) || 0;
                document.getElementById('p-total').innerText = `R$ ${(sub + taxa).toFixed(2)}`;
            }

            async function salvarPedidoWeb() {
                const tel = document.getElementById('p-tel').value;
                const nome = document.getElementById('p-nome').value;
                if(!tel || !nome || !carrinhoWeb.length) return alert("Preencha telefone, nome e adicione itens!");
                const payload = {
                    id_pedido: pedidoEditandoId, tipo: document.getElementById('p-tipo').value,
                    cliente: { tel, nome, bairro: document.getElementById('p-bairro').value, rua: document.getElementById('p-rua').value, num: document.getElementById('p-num').value, comp: document.getElementById('p-comp').value },
                    itens: carrinhoWeb,
                    valores: { subtotal: parseFloat(document.getElementById('p-subtotal').innerText.replace('R$ ', '')), taxa: parseFloat(document.getElementById('p-taxa').value) || 0, acrescimos: 0, descontos: 0, total: parseFloat(document.getElementById('p-total').innerText.replace('R$ ', '')), pagamento: document.getElementById('p-pagamento').value }
                };
                const res = await fetch('/api/admin/finalizar', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
                if(res.ok) { fecharModalPedido(); fetchPedidos(); } else alert("Erro ao salvar pedido.");
            }

            async function fetchProdutos() {
                const res = await fetch('/api/admin/produtos');
                const data = await res.json();
                produtosLista = data;
                const container = document.getElementById('lista-produtos');
                container.innerHTML = '';
                data.forEach(p => {
                    container.innerHTML += `
                        <div class="flex justify-between items-center p-4 bg-white rounded-xl border border-slate-200 shadow-sm">
                            <div><div class="font-bold text-slate-800 text-sm">${p[1]}</div><div class="text-[10px] text-slate-400 font-bold uppercase">${p[3] || 'Sem Categoria'}</div></div>
                            <div class="text-right"><div class="font-bold text-vex-primary">R$ ${p[2].toFixed(2)}</div>
                            <div class="text-[9px] ${p[4] ? 'text-green-500' : 'text-red-400'} font-bold">${p[4] ? '● VISÍVEL' : '○ OCULTO'}</div></div>
                        </div>`;
                });
            }

            async function fetchConfig() {
                const res = await fetch('/api/admin/config');
                const data = await res.json();
                const container = document.getElementById('info-config');
                container.innerHTML = `
                    <div class="space-y-1"><label class="text-[10px] font-black text-slate-400 uppercase">Estabelecimento</label><p class="font-bold text-slate-700">${data.empresa.nome}</p></div>
                    <div class="space-y-1"><label class="text-[10px] font-black text-slate-400 uppercase">Contato</label><p class="font-bold text-slate-700">${data.empresa.fone}</p></div>
                    <div class="pt-4 border-t border-slate-100"><label class="text-[10px] font-black text-slate-400 uppercase mb-2 block">Status Módulos Web</label>
                        <div class="flex gap-2"><span class="text-[10px] px-2 py-1 rounded bg-green-100 text-green-700 font-bold">MENU: ON</span><span class="text-[10px] px-2 py-1 rounded bg-vex-primary/10 text-vex-primary font-bold">ADMIN: ON</span></div>
                    </div><p class="text-[9px] text-slate-400 text-center italic mt-4">Nota: Edições globais devem ser realizadas no computador principal.</p>`;
            }

            fetchPedidos(); setInterval(fetchPedidos, 10000);
        </script>
    </body>
    </html>
    """