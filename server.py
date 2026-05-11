import os
import sqlite3
import logging
from flask import Flask, jsonify, request, send_file, render_template_string

def criar_app_cardapio(data_dir, empresa_info):
    app = Flask(__name__)
    
    # Silenciar logs desnecessários no console
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    def get_db_connection():
        return sqlite3.connect(os.path.join(data_dir, "delivery.db"))

    @app.route('/logo')
    def get_logo():
        path = empresa_info.get('logo_path')
        if path and os.path.exists(path):
            return send_file(path)
        return "", 404

    @app.route('/api/menu')
    def api_menu():
        cat_selecionada = request.args.get('cat', 'TODOS')
        page = int(request.args.get('page', 1))
        per_page = 20
        offset = (page - 1) * per_page
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Categorias
        cursor.execute("""SELECT DISTINCT c.nome FROM categorias c 
                          JOIN produtos p ON c.nome = p.categoria 
                          WHERE p.visivel_web = 1 ORDER BY c.ordem, c.nome""")
        categorias = [r[0] for r in cursor.fetchall()]
        
        # Produtos
        query = "SELECT id_produto, nome, preco, ingredientes FROM produtos WHERE visivel_web = 1"
        params = []
        if cat_selecionada != 'TODOS':
            query += " AND categoria = ?"
            params.append(cat_selecionada)

        query += " ORDER BY (id_produto >= 100), CASE WHEN id_produto < 100 THEN id_produto ELSE 0 END, nome LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        
        cursor.execute(query, params)
        produtos = cursor.fetchall()
        conn.close()
        
        return jsonify({
            "categorias": categorias,
            "produtos": produtos,
            "has_next": len(produtos) == per_page
        })

    @app.route('/')
    def index():
        return render_template_string("""
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
                        const res = await fetch(`/api/menu?cat=${currentCat}&page=${currentPage}`);
                        const data = await res.json();
                        renderCategories(data.categorias);
                        renderProducts(data.produtos);
                        document.getElementById('page-num').innerText = currentPage;
                        document.getElementById('btn-prev').disabled = currentPage === 1;
                        document.getElementById('btn-next').disabled = !data.has_next;
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
            """, 
            nome=empresa_info.get('nome'), 
            fone=empresa_info.get('fone'), 
            end=empresa_info.get('end'))

    return app