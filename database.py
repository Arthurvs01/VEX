import sqlite3
import os
from datetime import datetime

class DatabaseManager:
    """Gerencia a conexão e as operações no banco de dados SQLite."""
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.criar_tabelas()

    def criar_tabelas(self):
        """Inicializa a estrutura do banco de dados se não existir."""
        queries = [
            "CREATE TABLE IF NOT EXISTS config (chave TEXT PRIMARY KEY, valor TEXT)",
            "CREATE TABLE IF NOT EXISTS clientes (telefone TEXT PRIMARY KEY, nome TEXT, bairro TEXT, rua TEXT, numero TEXT, complemento TEXT)",
            "CREATE TABLE IF NOT EXISTS produtos (id_produto INTEGER PRIMARY KEY, nome TEXT, preco REAL, categoria TEXT, ingredientes TEXT, visivel_web INTEGER DEFAULT 1)",
            "CREATE TABLE IF NOT EXISTS categorias (id_categoria INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE, ordem INTEGER DEFAULT 0)",
            "CREATE TABLE IF NOT EXISTS bairros (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE, taxa REAL)",
            """CREATE TABLE IF NOT EXISTS pedidos (
                id_pedido INTEGER PRIMARY KEY AUTOINCREMENT,
                telefone_cliente TEXT,
                subtotal REAL,
                taxa REAL,
                acrescimos REAL,
                descontos REAL,
                total REAL,
                forma_pagamento TEXT,
                tipo TEXT DEFAULT 'ENTREGA',
                troco REAL,
                num_dia INTEGER,
                data_pedido TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS itens_pedido (
                id_item_pedido INTEGER PRIMARY KEY AUTOINCREMENT,
                id_pedido INTEGER,
                id_produto INTEGER,
                quantidade INTEGER,
                preco_unitario REAL,
                observacao TEXT,
                FOREIGN KEY(id_pedido) REFERENCES pedidos(id_pedido)
            )"""
        ]
        for q in queries:
            self.cursor.execute(q)
        self.conn.commit()
        self.executar_migracoes()

    def executar_migracoes(self):
        """Garante que colunas novas existam em versões antigas do banco."""
        # Migrações para a tabela 'produtos'
        self.cursor.execute("PRAGMA table_info(produtos)")
        colunas_prod = [col[1] for col in self.cursor.fetchall()]
        if 'categoria' not in colunas_prod:
            self.executar("ALTER TABLE produtos ADD COLUMN categoria TEXT")
        if 'ingredientes' not in colunas_prod:
            self.executar("ALTER TABLE produtos ADD COLUMN ingredientes TEXT")
        if 'visivel_web' not in colunas_prod:
            self.executar("ALTER TABLE produtos ADD COLUMN visivel_web INTEGER DEFAULT 1")

        # Migrações para a tabela 'categorias'
        self.cursor.execute("PRAGMA table_info(categorias)")
        if 'ordem' not in [col[1] for col in self.cursor.fetchall()]:
            self.executar("ALTER TABLE categorias ADD COLUMN ordem INTEGER DEFAULT 0")

        # Migrações para a tabela 'pedidos'
        self.cursor.execute("PRAGMA table_info(pedidos)")
        colunas_ped = [col[1] for col in self.cursor.fetchall()]
        if 'num_dia' not in colunas_ped:
            self.executar("ALTER TABLE pedidos ADD COLUMN num_dia INTEGER")
            self.corrigir_numeracao_dia()
        if 'forma_pagamento' not in colunas_ped:
            self.executar("ALTER TABLE pedidos ADD COLUMN forma_pagamento TEXT")

    def corrigir_numeracao_dia(self):
        """Lógica de backfill para pedidos sem numeração diária."""
        try:
            self.cursor.execute("SELECT id_pedido, DATE(data_pedido, 'localtime'), tipo FROM pedidos ORDER BY id_pedido ASC")
            all_p = self.cursor.fetchall()
            counters = {}
            for pid, dt_p, tp_p in all_p:
                k = (dt_p, tp_p)
                counters[k] = counters.get(k, 0) + 1
                self.cursor.execute("UPDATE pedidos SET num_dia = ? WHERE id_pedido = ?", (counters[k], pid))
            self.conn.commit()
        except Exception as e:
            print(f"Erro na migração de numeração: {e}")

    def executar(self, query, params=()):
        """Executa uma query genérica."""
        self.cursor.execute(query, params)
        self.conn.commit()
        return self.cursor

    def buscar_um(self, query, params=()):
        self.cursor.execute(query, params)
        return self.cursor.fetchone()

    def buscar_todos(self, query, params=()):
        self.cursor.execute(query, params)
        return self.cursor.fetchall()

    def fechar(self):
        self.conn.close()