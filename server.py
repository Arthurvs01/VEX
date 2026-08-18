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
                <title>{{ nome }} - Cardápio</title>
                <script src="https://cdn.tailwindcss.com"></script>
                <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
                <style>
                    body { font-family: 'Inter', sans-serif; background-color: #f8fafc; }
                    .bg-brand { background-color: #B22222; }
                    .text-brand { color: #B22222; }
                    .border-brand { border-color: #B22222; }
                    
                    .cat-scroll::-webkit-scrollbar { display: none; }
                    .cat-btn { transition: all 0.2s ease-in-out; }
                    .cat-btn.active { background-color: #B22222; color: white; border-color: #B22222; box-shadow: 0 4px 6px -1px rgba(178, 34, 34, 0.3); }
                    .cat-btn.inactive { background-color: white; color: #475569; border-color: #cbd5e1; }
                    
                    .product-card { transition: transform 0.1s ease; }
                    .product-card:active { transform: scale(0.98); }
                </style>
            </head>
            <body class="text-slate-800 pb-10">
                <!-- Header -->
                <header class="bg-brand text-white shadow-lg relative overflow-hidden">
                    <div class="absolute inset-0 opacity-10 bg-[url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyMCIgaGVpZ2h0PSIyMCI+PGNpcmNsZSBjeD0iMiIgY3k9IjIiIHI9IjIiIGZpbGw9IiNmZmYiLz48L3N2Zz4=')]"></div>
                    <div class="p-5 flex flex-col items-center text-center relative z-10">
                        <img src="/logo" class="w-20 h-20 rounded-full bg-white object-cover border-4 border-white/30 shadow-md mb-3" onerror="this.style.display='none'">
                        <h1 class="text-2xl font-bold tracking-tight">{{ nome }}</h1>
                        <div class="flex items-center gap-2 mt-2 opacity-90 text-sm">
                            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path d="M2 3a1 1 0 011-1h2.153a1 1 0 01.986.836l.74 4.435a1 1 0 01-.54 1.06l-1.548.773a11.037 11.037 0 006.105 6.105l.774-1.548a1 1 0 011.059-.54l4.435.74a1 1 0 01.836.986V17a1 1 0 01-1 1h-2C7.82 18 2 12.18 2 5V3z"></path></svg>
                            <span>{{ fone }}</span>
                        </div>
                        <div class="flex items-center gap-2 mt-1 opacity-90 text-sm">
                            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clip-rule="evenodd"></path></svg>
                            <span>{{ end }}</span>
                        </div>
                    </div>
                </header>
            
                <!-- Search Bar -->
                <div class="sticky top-0 bg-white shadow-sm z-20 px-4 py-3 border-b">
                    <div class="relative max-w-2xl mx-auto">
                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                            <svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                        </div>
                        <input type="text" id="searchInput" onkeyup="filterProducts()" placeholder="Buscar produtos..." class="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-xl bg-gray-50 focus:bg-white focus:ring-2 focus:ring-red-500 focus:border-transparent outline-none transition-all shadow-inner">
                    </div>
                </div>
            
                <!-- Categories -->
                <div class="bg-white/95 backdrop-blur z-10 py-3 border-b sticky top-[61px]">
                    <div id="categorias" class="flex overflow-x-auto px-4 gap-2 cat-scroll max-w-3xl mx-auto">
                        <button onclick="setCategory('TODOS')" id="cat-TODOS" class="cat-btn active px-4 py-1.5 rounded-full text-sm font-semibold whitespace-nowrap border">TODOS</button>
                    </div>
                </div>
            
                <!-- Menu Grid -->
                <main class="p-4 max-w-3xl mx-auto">
                    <div id="menu" class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <!-- Skeleton Loading -->
                        <div class="animate-pulse flex flex-col p-4 bg-white rounded-xl shadow-sm border border-gray-100">
                            <div class="h-4 bg-gray-200 rounded w-3/4 mb-3"></div>
                            <div class="h-3 bg-gray-200 rounded w-1/2 mb-4"></div>
                            <div class="flex justify-between mt-auto">
                                <div class="h-5 bg-gray-200 rounded w-1/4"></div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Pagination -->
                    <div class="flex justify-center items-center gap-4 mt-8 bg-white p-3 rounded-2xl shadow-sm border border-gray-100 w-fit mx-auto">
                        <button id="btn-prev" onclick="changePage(-1)" class="w-10 h-10 flex items-center justify-center rounded-full bg-gray-50 text-gray-600 border hover:bg-gray-100 disabled:opacity-40 transition-colors">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path></svg>
                        </button>
                        <span class="font-bold text-gray-700 min-w-[3rem] text-center"><span id="page-num">1</span></span>
                        <button id="btn-next" onclick="changePage(1)" class="w-10 h-10 flex items-center justify-center rounded-full bg-gray-50 text-gray-600 border hover:bg-gray-100 disabled:opacity-40 transition-colors">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path></svg>
                        </button>
                    </div>
                </main>
            
                <script>
                    let currentCat = 'TODOS';
                    let currentPage = 1;
                    let allCurrentProducts = []; // For local search filtering
            
                    async function loadMenu() {
                        const res = await fetch(`/api/menu?cat=${encodeURIComponent(currentCat)}&page=${currentPage}`);
                        const data = await res.json();
                        renderCategories(data.categorias);
                        allCurrentProducts = data.produtos;
                        renderProducts(allCurrentProducts);
                        document.getElementById('page-num').innerText = currentPage;
                        document.getElementById('btn-prev').disabled = currentPage === 1;
                        document.getElementById('btn-next').disabled = !data.has_next;
                        document.getElementById('searchInput').value = '';
                    }
            
                    function renderCategories(cats) {
                        const catDiv = document.getElementById('categorias');
                        if(catDiv.children.length > 1) return; // Já renderizou
                        cats.forEach(cat => {
                            const safeId = 'cat-' + cat.replace(/\s+/g, '-');
                            catDiv.innerHTML += `<button onclick="setCategory('${cat}')" id="${safeId}" class="cat-btn inactive px-4 py-1.5 rounded-full text-sm font-semibold whitespace-nowrap border">${cat}</button>`;
                        });
                    }
            
                    function renderProducts(prods) {
                        const menuDiv = document.getElementById('menu');
                        if(prods.length === 0) {
                            menuDiv.innerHTML = `<div class="col-span-full flex flex-col items-center justify-center py-12 text-gray-400">
                                <svg class="w-16 h-16 mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path></svg>
                                <p class="text-lg font-medium">Nenhum item encontrado.</p>
                            </div>`;
                            return;
                        }
                        
                        menuDiv.innerHTML = '';
                        prods.forEach(p => { 
                            const idRaw = p[0];
                            const nome = p[1];
                            const preco = p[2].toFixed(2).replace('.', ',');
                            const ingredientes = p[3] || '';
                            const idDisplay = idRaw < 100 ? `<span class="bg-gray-100 text-gray-500 text-xs px-2 py-0.5 rounded-md mr-2">#${idRaw.toString().padStart(2, '0')}</span>` : '';
                            
                            let itemHtml = `
                            <div class="product-card bg-white p-4 rounded-2xl shadow-sm border border-gray-100 flex flex-col justify-between overflow-hidden relative">
                                <div class="absolute top-0 left-0 w-1 h-full bg-brand opacity-80"></div>
                                <div>
                                    <div class="flex justify-between items-start mb-1">
                                        <h3 class="text-base font-bold text-gray-800 leading-tight pr-4">${idDisplay}${nome}</h3>
                                    </div>
                                    ${ingredientes ? `<p class="text-sm text-gray-500 mb-4 line-clamp-2">${ingredientes}</p>` : '<div class="h-2"></div>'}
                                </div>
                                <div class="mt-auto pt-3 border-t border-gray-50 flex justify-between items-center">
                                    <span class="text-lg font-black text-brand tracking-tight">R$ ${preco}</span>
                                </div>
                            </div>`;
                            menuDiv.innerHTML += itemHtml;
                        });
                    }
            
                    function filterProducts() {
                        const query = document.getElementById('searchInput').value.toLowerCase();
                        const filtered = allCurrentProducts.filter(p => {
                            return p[1].toLowerCase().includes(query) || (p[3] && p[3].toLowerCase().includes(query));
                        });
                        renderProducts(filtered);
                    }
            
                    function setCategory(cat) {
                        currentCat = cat;
                        currentPage = 1;
                        
                        // Atualiza botões
                        document.querySelectorAll('.cat-btn').forEach(btn => {
                            btn.classList.remove('active');
                            btn.classList.add('inactive');
                        });
                        
                        // Seleciona o botão correto baseado no ID para não falhar com espaços
                        const safeId = cat === 'TODOS' ? 'cat-TODOS' : 'cat-' + cat.replace(/\s+/g, '-');
                        const targetBtn = document.getElementById(safeId);
                        if(targetBtn) {
                            targetBtn.classList.add('active');
                            targetBtn.classList.remove('inactive');
                            // Centraliza o scroll no botão selecionado
                            targetBtn.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
                        }
                        
                        loadMenu();
                    }
            
                    // Intercept enter nas buscas
                    document.getElementById('searchInput').addEventListener('keypress', function (e) {
                        if (e.key === 'Enter') {
                            e.target.blur();
                        }
                    });
            
                    // Load inicial
                    loadMenu();
                </script>
            </body>
            </html>
            """, 
            nome=empresa_info.get('nome'), 
            fone=empresa_info.get('fone'), 
            end=empresa_info.get('end'))

    return app