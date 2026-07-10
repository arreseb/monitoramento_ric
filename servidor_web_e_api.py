# -*- coding: utf-8 -*-
"""
SISTEMA DE MONITORAMENTO DE RICs
Servidor Web Autônomo para Nuvem AWS (EC2)
Tecnologias: Python, Flask, SQLite3 (Modo Concorrente WAL), HTML5/CSS3 Nativo
"""

import os
import sqlite3
import json
from flask import Flask, jsonify, request, make_response

app = Flask(__name__)
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rics.db')

# Cria e retorna uma nova conexão com o banco SQLite para cada chamada.
# Motivo: em servidores web (múltiplas threads/processos) é mais seguro abrir
# conexões por requisição em vez de compartilhar uma única conexão global.
# O `row_factory` é configurado para permitir acesso por nome de coluna
# (ex: row['sei']). O PRAGMA ativa o modo WAL (Write-Ahead Logging) para
# melhorar concorrência entre leituras e escritas.


def obter_conexao():
    """Retorna uma conexão segura com o SQLite configurada para multi-usuários."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    # Ativa o modo WAL (Write-Ahead Logging) para permitir leituras e escritas concorrentes sem travar o banco
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn


def inicializar_banco():
    """Cria a tabela de monitoramento se ela não existir.

    Observações:
    - O campo `areas` armazena um JSON serializado (string) contendo um array
      com códigos das áreas responsáveis. Ao ler/escrever precisamos usar
      `json.loads` / `json.dumps`.
    - `status` tem valor padrão 'Pendente'.
    """
    with obter_conexao() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS rics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sei TEXT NOT NULL,
                ric TEXT NOT NULL,
                assunto TEXT NOT NULL,
                responsavel TEXT NOT NULL,
                areas TEXT NOT NULL, -- Armazenado como JSON array formatado
                prazo_dias INTEGER NOT NULL,
                data_vencimento TEXT NOT NULL,
                data_repactuada TEXT,
                observacao TEXT,
                status TEXT DEFAULT 'Pendente'
            )
        ''')
        conn.commit()


# HTML Premium da Aplicação (Injetado pelo Servidor)
# NOTE: o template abaixo contém todo o frontend (HTML/CSS/JS). As
# funções JavaScript para o cliente (sincronizarDados, adicionarDiasUteis,
# renderizarTabela, prepararEmail, etc.) estão embutidas nessa string e são
# executadas no navegador do usuário. O backend Flask serve esse template
# na rota raiz e expõe a API REST para persistência.

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GABPRE - Monitoramento de RICs</title>
    <style>
        /* RESET E VARIÁVEIS DE DESIGN CORPORATIVO */
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
            transition: all 0.2s ease-in-out;
        }

        body {
            background-color: #f8fafc;
            color: #1e293b;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            padding: 1.5rem;
        }

        .app-container {
            max-width: 1400px;
            margin: 0 auto;
            width: 100%;
        }

        /* CABEÇALHO PREMIUM */
        .ric-header {
            background: linear-gradient(135deg, #1e3a8a 0%, #0f172a 100%);
            color: #ffffff;
            border-radius: 1rem;
            padding: 1.5rem 2rem;
            display: flex;
            flex-direction: row;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 10px 15px -3px rgba(30, 58, 138, 0.2);
            margin-bottom: 2rem;
            flex-wrap: wrap;
            gap: 1rem;
        }

        .ric-header-title-container {
            display: flex;
            align-items: center;
            gap: 1rem;
        }

        .ric-header-icon {
            background-color: rgba(255, 255, 255, 0.15);
            padding: 0.75rem;
            border-radius: 0.75rem;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .ric-header-h1 {
            font-size: 1.5rem;
            font-weight: 800;
            letter-spacing: -0.025em;
        }

        .ric-header-p {
            font-size: 0.85rem;
            color: #93c5fd;
            font-weight: 500;
        }

        .ric-sync-panel {
            text-align: right;
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 0.25rem;
        }

        .ric-sync-badge {
            background-color: rgba(16, 185, 129, 0.15);
            border: 1px solid #10b981;
            color: #34d399;
            padding: 0.35rem 0.75rem;
            border-radius: 2rem;
            font-size: 0.75rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .ric-sync-pulse {
            width: 0.6rem;
            height: 0.6rem;
            background-color: #10b981;
            border-radius: 50%;
            display: inline-block;
            animation: pulse-subtle 2s infinite;
        }

        /* GRID DE CARD METRICAS */
        .ric-metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1.25rem;
            margin-bottom: 2rem;
        }

        .ric-metric-card {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 1rem;
            padding: 1.25rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        }

        .ric-metric-label {
            font-size: 0.75rem;
            text-transform: uppercase;
            font-weight: 700;
            color: #64748b;
            letter-spacing: 0.05em;
        }

        .ric-metric-value {
            font-size: 2rem;
            font-weight: 900;
            color: #0f172a;
            margin-top: 0.25rem;
        }

        .ric-metric-icon {
            padding: 0.75rem;
            border-radius: 0.75rem;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        /* CORES DOS CARDS */
        .metric-blue { background-color: #eff6ff; color: #1d4ed8; }
        .metric-green { background-color: #ecfdf5; color: #047857; }
        .metric-amber { background-color: #fffbeb; color: #b45309; }
        .metric-red { background-color: #fef2f2; color: #b91c1c; }
        .metric-indigo { background-color: #f5f3ff; color: #6d28d9; }

        /* CONTAINER DO FORMULÁRIO */
        .ric-section-card {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 1rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            margin-bottom: 2rem;
            overflow: hidden;
        }

        .ric-section-header {
            background-color: #f8fafc;
            padding: 1rem 1.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
            border-bottom: 1px solid #e2e8f0;
        }

        .ric-section-header-title {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-weight: 700;
            color: #1e293b;
        }

        .ric-form-body {
            padding: 1.5rem;
        }

        .ric-form-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.25rem;
            margin-bottom: 1.25rem;
        }

        .ric-form-group {
            display: flex;
            flex-direction: column;
            gap: 0.35rem;
        }

        .ric-form-label {
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            color: #475569;
        }

        .ric-input {
            width: 100%;
            padding: 0.65rem 0.85rem;
            border: 1.5px solid #cbd5e1;
            border-radius: 0.5rem;
            font-size: 0.875rem;
            outline: none;
            background-color: #ffffff;
        }

        .ric-input:focus {
            border-color: #1e3a8a;
            box-shadow: 0 0 0 3px rgba(30, 58, 138, 0.15);
        }

        .ric-input[readonly] {
            background-color: #f1f5f9;
            cursor: not-allowed;
        }

        /* ÁREAS TÉCNICAS */
        .ric-areas-box {
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 0.75rem;
            padding: 1rem;
            margin-bottom: 1.25rem;
        }

        .ric-areas-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(115px, 1fr));
            gap: 0.75rem;
            margin-top: 0.5rem;
        }

        .ric-checkbox-label {
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            padding: 0.5rem;
            border-radius: 0.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            cursor: pointer;
            font-size: 0.75rem;
            font-weight: 700;
            color: #334155;
            user-select: none;
        }

        /* BOTÕES */
        .ric-btn-container {
            display: flex;
            justify-content: flex-end;
            gap: 0.75rem;
            padding-top: 0.5rem;
        }

        .ric-btn {
            padding: 0.65rem 1.25rem;
            border-radius: 0.5rem;
            font-size: 0.875rem;
            font-weight: 700;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            border: none;
        }

        .ric-btn-secondary { background-color: #ffffff; border: 1px solid #cbd5e1; color: #475569; }
        .ric-btn-secondary:hover { background-color: #f1f5f9; }
        .ric-btn-primary { background-color: #1e3a8a; color: #ffffff; }
        .ric-btn-primary:hover { background-color: #1e40af; }

        /* TABELA DE DADOS */
        .ric-table-toolbar {
            padding: 1.25rem;
            background-color: #f8fafc;
            border-bottom: 1px solid #e2e8f0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
        }

        .ric-search-container {
            position: relative;
            flex: 1;
            max-width: 400px;
            width: 100%;
        }

        .ric-search-input {
            width: 100%;
            padding: 0.65rem 1rem 0.65rem 2.5rem;
            border: 1.5px solid #cbd5e1;
            border-radius: 0.5rem;
            font-size: 0.875rem;
            outline: none;
        }

        .ric-search-icon {
            position: absolute;
            left: 0.75rem;
            top: 50%;
            transform: translateY(-50%);
            color: #94a3b8;
        }

        .ric-filter-tabs {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }

        .ric-tab {
            padding: 0.45rem 1rem;
            border-radius: 2rem;
            font-size: 0.75rem;
            font-weight: 700;
            border: 1px solid #cbd5e1;
            background-color: #ffffff;
            color: #475569;
            cursor: pointer;
        }

        .ric-tab-active { background-color: #1e3a8a; color: #ffffff; border-color: #1e3a8a; }

        .ric-table-container { overflow-x: auto; width: 100%; }
        .ric-table { width: 100%; border-collapse: collapse; text-align: left; font-size: 0.85rem; }
        .ric-table th { background-color: #f1f5f9; color: #475569; font-weight: 700; text-transform: uppercase; font-size: 0.75rem; padding: 1rem 1.25rem; border-bottom: 2px solid #e2e8f0; }
        .ric-table td { padding: 1rem 1.25rem; border-bottom: 1px solid #f1f5f9; vertical-align: middle; }
        .ric-table tr:hover { background-color: #f8fafc; }

        /* BADGES */
        .ric-badge-area { display: inline-block; background-color: #f1f5f9; border: 1px solid #cbd5e1; color: #334155; font-family: monospace; font-weight: 700; font-size: 0.65rem; padding: 0.15rem 0.4rem; border-radius: 0.25rem; margin-right: 0.25rem; margin-top: 0.25rem; }
        .ric-badge-status-pendente { background-color: #fffbeb; color: #b45309; font-weight: 700; padding: 0.25rem 0.6rem; border-radius: 2rem; font-size: 0.75rem; border: 1px solid #fde68a; }
        .ric-badge-status-respondido { background-color: #eff6ff; color: #1d4ed8; font-weight: 700; padding: 0.25rem 0.6rem; border-radius: 2rem; font-size: 0.75rem; border: 1px solid #bfdbfe; }
        
        .ric-deadline-atrasado { background-color: #fef2f2; color: #b91c1c; font-weight: 700; padding: 0.25rem 0.5rem; border-radius: 0.35rem; border: 1px solid #fca5a5; font-size: 0.75rem; }
        .ric-deadline-urgente { background-color: #fffbeb; color: #d97706; font-weight: 700; padding: 0.25rem 0.5rem; border-radius: 0.35rem; border: 1px solid #fde68a; font-size: 0.75rem; }
        .ric-deadline-normal { background-color: #ecfdf5; color: #047857; font-weight: 700; padding: 0.25rem 0.5rem; border-radius: 0.35rem; border: 1px solid #a7f3d0; font-size: 0.75rem; }

        .ric-action-btn-group { display: flex; gap: 0.35rem; justify-content: center; }
        .ric-action-btn { background: none; border: none; cursor: pointer; padding: 0.4rem; border-radius: 0.35rem; display: flex; align-items: center; justify-content: center; }
        .ric-action-btn-blue { background-color: #eff6ff; color: #1d4ed8; }
        .ric-action-btn-blue:hover { background-color: #dbeafe; }
        .ric-action-btn-purple { background-color: #f5f3ff; color: #6d28d9; }
        .ric-action-btn-purple:hover { background-color: #ede9fe; }
        .ric-action-btn-green { background-color: #ecfdf5; color: #047857; }
        .ric-action-btn-green:hover { background-color: #d1fae5; }
        .ric-action-btn-red { background-color: #fef2f2; color: #b91c1c; }
        .ric-action-btn-red:hover { background-color: #fee2e2; }

        /* MODAIS */
        .ric-modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background-color: rgba(15, 23, 42, 0.6); backdrop-filter: blur(4px); display: flex; align-items: center; justify-content: center; z-index: 1000; }
        .ric-modal-box { background-color: #ffffff; border-radius: 1rem; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25); max-width: 600px; width: 100%; overflow: hidden; border: 1px solid #e2e8f0; display: flex; flex-direction: column; max-height: 90vh; }
        .ric-modal-header { background-color: #1e3a8a; color: #ffffff; padding: 1.25rem 1.5rem; display: flex; justify-content: space-between; align-items: center; }
        .ric-modal-body { padding: 1.5rem; overflow-y: auto; display: flex; flex-direction: column; gap: 1rem; }
        .ric-modal-footer { background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 1rem 1.5rem; display: flex; justify-content: flex-end; gap: 0.5rem; }

        @keyframes pulse-subtle { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.6; transform: scale(0.95); } }

        /* TOAST NOTIFICATION */
        .ric-toast { position: fixed; bottom: 1.5rem; right: 1.5rem; background-color: #0f172a; color: #ffffff; padding: 1rem 1.5rem; border-radius: 0.75rem; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.3); display: flex; align-items: center; gap: 0.75rem; z-index: 2000; font-size: 0.85rem; font-weight: 600; border: 1px solid #334155; }
        .hidden { display: none !important; }
    </style>
</head>
<body>
    <div class="app-container">
        <!-- CABEÇALHO -->
        <header class="ric-header">
            <div class="ric-header-title-container">
                <div class="ric-header-icon">
                    <svg width="32" height="32" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="color: #fbbf24;">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                    </svg>
                </div>
                <div>
                    <h1 class="ric-header-h1">GABPRE - INSS</h1>
                    <p class="ric-header-p">Painel Corporativo de Monitoramento de Requerimentos de Informação (RIC)</p>
                </div>
            </div>
            
            <div class="ric-sync-panel">
                <div class="ric-sync-badge">
                    <span class="ric-sync-pulse"></span>
                    <span>AWS Cloud Database - Conectado</span>
                </div>
                <div style="font-size: 0.75rem; color: #cbd5e1; margin-top: 0.25rem;">
                    <span id="sync-timer">Atualizando em 30s...</span> | 
                    <span onclick="forcarSincronizacao()" style="text-decoration: underline; cursor: pointer; font-weight: bold; color: #ffffff;">Sincronizar Agora</span>
                </div>
            </div>
        </header>

        <!-- DASHBOARD DE MÉTRICAS -->
        <div class="ric-metrics-grid">
            <div class="ric-metric-card">
                <div>
                    <p class="ric-metric-label">Total RICs</p>
                    <p class="ric-metric-value" id="stat-total">0</p>
                </div>
                <div class="ric-metric-icon metric-blue">
                    <svg width="24" height="24" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path></svg>
                </div>
            </div>
            
            <div class="ric-metric-card">
                <div>
                    <p class="ric-metric-label">No Prazo</p>
                    <p class="ric-metric-value" id="stat-no-prazo" style="color: #047857;">0</p>
                </div>
                <div class="ric-metric-icon metric-green">
                    <svg width="24" height="24" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                </div>
            </div>

            <div class="ric-metric-card">
                <div>
                    <p class="ric-metric-label">Urgentes (≤3d)</p>
                    <p class="ric-metric-value" id="stat-urgentes" style="color: #b45309;">0</p>
                </div>
                <div class="ric-metric-icon metric-amber">
                    <svg width="24" height="24" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
                </div>
            </div>

            <div class="ric-metric-card">
                <div>
                    <p class="ric-metric-label">Atrasadas</p>
                    <p class="ric-metric-value" id="stat-atrasadas" style="color: #b91c1c;">0</p>
                </div>
                <div class="ric-metric-icon metric-red">
                    <svg width="24" height="24" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                </div>
            </div>

            <div class="ric-metric-card">
                <div>
                    <p class="ric-metric-label">Respondidas</p>
                    <p class="ric-metric-value" id="stat-concluidas" style="color: #6d28d9;">0</p>
                </div>
                <div class="ric-metric-icon metric-indigo">
                    <svg width="24" height="24" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                </div>
            </div>
        </div>

        <!-- FORMULÁRIO -->
        <div class="ric-section-card">
            <div class="ric-section-header" onclick="toggleForm()">
                <div class="ric-section-header-title">
                    <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="color: #1e3a8a;"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v3m0 0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    <span>Cadastrar Novo Requerimento (RIC)</span>
                </div>
                <svg id="arrow-toggle" width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="color: #64748b; transform: rotate(0deg);"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
            </div>
            
            <form id="ric-form" class="ric-form-body">
                <div class="ric-form-grid">
                    <div class="ric-form-group">
                        <label class="ric-form-label">Processo SEI *</label>
                        <input type="text" id="form-sei" class="ric-input" placeholder="Ex: 35014.123456/2026-01" required>
                    </div>
                    <div class="ric-form-group">
                        <label class="ric-form-label">Nº do Requerimento (RIC) *</label>
                        <input type="text" id="form-ric" class="ric-input" placeholder="Ex: RIC 123/2026" required>
                    </div>
                    <div class="ric-form-group">
                        <label class="ric-form-label">Responsável GABPRE *</label>
                        <input type="text" id="form-responsavel" class="ric-input" placeholder="Ex: Maria Souza" required>
                    </div>
                </div>

                <div class="ric-form-group" style="margin-bottom: 1.25rem;">
                    <label class="ric-form-label">Assunto do Requerimento / E-mail *</label>
                    <input type="text" id="form-assunto" class="ric-input" placeholder="Ex: Requerimento de Informação sobre despesas com Tecnologia" required>
                </div>

                <!-- CHECKBOXES -->
                <div class="ric-areas-box">
                    <label class="ric-form-label">Áreas Técnicas Responsáveis *</label>
                    <div class="ric-areas-grid">
                        <label class="ric-checkbox-label"><input type="checkbox" name="area-tecnica" value="DIRBEN"> <span>DIRBEN</span></label>
                        <label class="ric-checkbox-label"><input type="checkbox" name="area-tecnica" value="DTI"> <span>DTI</span></label>
                        <label class="ric-checkbox-label"><input type="checkbox" name="area-tecnica" value="DIROFL"> <span>DIROFL</span></label>
                        <label class="ric-checkbox-label"><input type="checkbox" name="area-tecnica" value="DGP"> <span>DGP</span></label>
                        <label class="ric-checkbox-label"><input type="checkbox" name="area-tecnica" value="DIGOV"> <span>DIGOV</span></label>
                        <label class="ric-checkbox-label"><input type="checkbox" name="area-tecnica" value="Ouvidoria"> <span>Ouvidoria</span></label>
                        <label class="ric-checkbox-label"><input type="checkbox" name="area-tecnica" value="CGPLAN"> <span>CGPLAN</span></label>
                        <label class="ric-checkbox-label"><input type="checkbox" name="area-tecnica" value="PFE"> <span>PFE</span></label>
                        <label class="ric-checkbox-label"><input type="checkbox" name="area-tecnica" value="Corregedoria"> <span>Corregedoria</span></label>
                        <label class="ric-checkbox-label"><input type="checkbox" name="area-tecnica" value="AUDGER"> <span>AUDGER</span></label>
                        <label class="ric-checkbox-label"><input type="checkbox" name="area-tecnica" value="ASCOM"> <span>ASCOM</span></label>
                    </div>
                </div>

                <div class="ric-form-grid">
                    <div class="ric-form-group">
                        <label class="ric-form-label">Prazo de Atendimento (Dias Úteis) *</label>
                        <input type="number" id="form-prazo-dias" class="ric-input" min="1" placeholder="Ex: 5" required>
                    </div>
                    <div class="ric-form-group">
                        <label class="ric-form-label">Data Vencimento Inicial (Automático)</label>
                        <input type="date" id="form-vencimento" class="ric-input" readonly>
                    </div>
                    <div class="ric-form-group">
                        <label class="ric-form-label">Data de Início (Opcional)</label>
                        <input type="date" id="form-database" class="ric-input">
                    </div>
                </div>

                <div class="ric-form-group" style="margin-bottom: 1.5rem;">
                    <label class="ric-form-label">Observação</label>
                    <textarea id="form-observacao" class="ric-input" rows="2" placeholder="Informações de suporte..."></textarea>
                </div>

                <div class="ric-btn-container">
                    <button type="button" onclick="limparFormulario()" class="ric-btn ric-btn-secondary">Limpar</button>
                    <button type="submit" class="ric-btn ric-btn-primary">Salvar Requerimento</button>
                </div>
            </form>
        </div>

        <!-- TABELA -->
        <div class="ric-section-card">
            <div class="ric-table-toolbar">
                <div class="ric-search-container">
                    <input type="text" id="table-search" class="ric-search-input" placeholder="Filtrar por SEI, RIC, Assunto...">
                    <span class="ric-search-icon">🔍</span>
                </div>
                <div class="ric-filter-tabs">
                    <button onclick="filtrarStatus('Todas')" class="ric-tab ric-tab-active">Todas</button>
                    <button onclick="filtrarStatus('Pendente')" class="ric-tab">Pendentes</button>
                    <button onclick="filtrarStatus('Urgente')" class="ric-tab">Urgentes</button>
                    <button onclick="filtrarStatus('Atrasada')" class="ric-tab">Atrasadas</button>
                    <button onclick="filtrarStatus('Respondida')" class="ric-tab">Respondidas</button>
                </div>
            </div>

            <div class="ric-table-container">
                <table class="ric-table">
                    <thead>
                        <tr>
                            <th style="width: 25%;">Processo SEI / RIC</th>
                            <th style="width: 30%;">Assunto</th>
                            <th style="width: 20%;">Responsável / Áreas</th>
                            <th style="width: 13%;">Vencimento</th>
                            <th style="width: 5%;">Status</th>
                            <th style="width: 7%; text-align: center;">Ações</th>
                        </tr>
                    </thead>
                    <tbody id="rics-list"></tbody>
                </table>
            </div>

            <div id="no-records" class="hidden" style="text-align: center; padding: 4rem 1.5rem; color: #64748b;">
                <h3 style="font-size: 1.1rem; font-weight: 700; color: #334155;">Nenhum registro encontrado</h3>
            </div>
        </div>
    </div>

    <!-- MODAL DE COBRANÇA -->
    <div id="email-modal" class="ric-modal-overlay hidden">
        <div class="ric-modal-box">
            <div class="ric-modal-header">
                <div>
                    <h3 style="font-size: 1.1rem; font-weight: 800;">Módulo de Cobrança GABPRE</h3>
                    <p style="font-size: 0.75rem; color: #bfdbfe;">Layout de cobrança oficial de urgência</p>
                </div>
                <button onclick="fecharEmailModal()" style="background:none; border:none; color:white; font-size:1.5rem; cursor:pointer;">&times;</button>
            </div>
            <div class="ric-modal-body">
                <div style="background-color: #f8fafc; padding: 1rem; border-radius: 0.5rem; border: 1px solid #e2e8f0;">
                    <div style="font-size: 0.7rem; font-weight: 700; color: #64748b; text-transform: uppercase;">Para</div>
                    <div id="modal-emails-to" style="font-size: 0.85rem; font-weight: 700; color: #1e3a8a; margin-top: 0.25rem; font-family: monospace;">-</div>
                </div>
                <div style="background-color: #f8fafc; padding: 1rem; border-radius: 0.5rem; border: 1px solid #e2e8f0;">
                    <div style="font-size: 0.7rem; font-weight: 700; color: #64748b; text-transform: uppercase;">Assunto</div>
                    <div id="modal-email-subject" style="font-size: 0.85rem; font-weight: 700; color: #334155; margin-top: 0.25rem;">-</div>
                </div>
                <div>
                    <span style="font-size: 0.7rem; font-weight: 700; color: #64748b; display: block; margin-bottom: 0.35rem;">Corpo</span>
                    <div id="modal-email-body" style="background-color: #fffbeb; padding: 1.25rem; border-radius: 0.5rem; border: 1px solid #fde68a; font-family: monospace; font-size: 0.75rem; white-space: pre-wrap; line-height: 1.5; color: #334155;">-</div>
                </div>
            </div>
            <div class="ric-modal-footer">
                <button onclick="copiarCorpoEmail()" class="ric-btn ric-btn-secondary">Copiar</button>
                <button id="btn-disparar" onclick="abrirClienteEmail()" class="ric-btn ric-btn-primary">Abrir Outlook</button>
            </div>
        </div>
    </div>

    <!-- MODAL REPACTUAÇÃO -->
    <div id="repactuar-modal" class="ric-modal-overlay hidden">
        <div class="ric-modal-box" style="max-width: 450px;">
            <div class="ric-modal-header">
                <h3 style="font-size: 1.1rem; font-weight: 800;">Repactuar Prazo Final</h3>
                <button onclick="fecharRepactuarModal()" style="background:none; border:none; color:white; font-size:1.5rem; cursor:pointer;">&times;</button>
            </div>
            <div class="ric-modal-body">
                <input type="hidden" id="repactuar-id">
                <div class="ric-form-group">
                    <label class="ric-form-label">Processo SEI</label>
                    <input type="text" id="repactuar-sei-display" class="ric-input" readonly>
                </div>
                <div class="ric-form-group">
                    <label class="ric-form-label">Vencimento Original</label>
                    <input type="text" id="repactuar-vencimento-atual" class="ric-input" readonly>
                </div>
                <div class="ric-form-group">
                    <label class="ric-form-label">Nova Data Repactuada *</label>
                    <input type="date" id="repactuar-nova-data" class="ric-input" required>
                </div>
            </div>
            <div class="ric-modal-footer">
                <button onclick="fecharRepactuarModal()" class="ric-btn ric-btn-secondary">Cancelar</button>
                <button onclick="salvarRepactuacao()" class="ric-btn ric-btn-primary">Salvar</button>
            </div>
        </div>
    </div>

    <!-- TOAST -->
    <div id="toast" class="ric-toast hidden">
        <span id="toast-icon"></span>
        <p id="toast-message"></p>
    </div>

    <script>
        const areasMapeamento = {
            'DIRBEN': { nome: 'Diretoria de Benefícios', email: 'dirben@inss.gov.br' },
            'DTI': { nome: 'Diretoria de Tecnologia da Informação', email: 'dti@inss.gov.br' },
            'DIROFL': { nome: 'Diretoria de Orçamento Finanças e Logística', email: 'dirofl@inss.gov.br' },
            'DGP': { nome: 'Diretoria de Gestão de Pessoas', email: 'dgp@inss.gov.br' },
            'DIGOV': { nome: 'Diretoria de Governança, Planejamento e Inovação', email: 'digov@inss.gov.br' },
            'Ouvidoria': { nome: 'Ouvidoria do INSS', email: 'ouvidoria@inss.gov.br' },
            'CGPLAN': { nome: 'Coordenação Geral de Planejamento e Gestão', email: 'cgplan@inss.gov.br' },
            'PFE': { nome: 'Procuradoria Federal Especializada', email: 'pfe@inss.gov.br' },
            'Corregedoria': { nome: 'Corregedoria Geral', email: 'corregedoria@inss.gov.br' },
            'AUDGER': { nome: 'Auditoria Geral', email: 'audger@inss.gov.br' },
            'ASCOM': { nome: 'Assessoria de Comunicação Social', email: 'ascom@inss.gov.br' }
        };

        let rics_data = [];
        let current_filter = 'Todas';
        let sync_countdown = 30;
        let sync_interval_id;

        window.addEventListener('DOMContentLoaded', () => {
            inicializarDataFormulario();
            configurarCalculoPrazoAutomatico();
            sincronizarDados();
            iniciarAutoSincronizacao();
        });

        // REQUISIÇÕES HTTP PARA A API BACKEND NATIVA (Flask)
        async function sincronizarDados() {
            try {
                const response = await fetch('/api/rics');
                if (!response.ok) throw new Error("Falha ao ler dados");
                rics_data = await response.json();
                renderizarDashboard();
                renderizarTabela();
            } catch (error) {
                console.error(error);
                mostrarToast("Erro ao se conectar com a API do Servidor.", true);
            }
        }

        function iniciarAutoSincronizacao() {
            clearInterval(sync_interval_id);
            sync_countdown = 30;
            sync_interval_id = setInterval(async () => {
                sync_countdown--;
                if (sync_countdown <= 0) {
                    document.getElementById('sync-timer').innerText = "Atualizando...";
                    await sincronizarDados();
                    sync_countdown = 30;
                }
                document.getElementById('sync-timer').innerText = `Atualizando em ${sync_countdown}s...`;
            }, 1000);
        }

        async function forcarSincronizacao() {
            mostrarToast("Buscando atualizações...");
            await sincronizarDados();
            iniciarAutoSincronizacao();
            mostrarToast("Painel sincronizado com sucesso!");
        }

        function adicionarDiasUteis(dataDeInicio, diasSomados) {
            let data = new Date(dataDeInicio + 'T12:00:00'); 
            let diasContados = 0;
            while (diasContados < diasSomados) {
                data.setDate(data.getDate() + 1);
                let diaSemana = data.getDay(); 
                if (diaSemana !== 0 && diaSemana !== 6) {
                    diasContados++;
                }
            }
            return data.toISOString().split('T')[0];
        }

        function inicializarDataFormulario() {
            const hoje = new Date().toISOString().split('T')[0];
            document.getElementById('form-database').value = hoje;
        }

        function configurarCalculoPrazoAutomatico() {
            const inputDias = document.getElementById('form-prazo-dias');
            const inputDataBase = document.getElementById('form-database');
            const inputVencimento = document.getElementById('form-vencimento');

            function recalcular() {
                const dias = parseInt(inputDias.value);
                const dataBase = inputDataBase.value;
                if (dias && dataBase) {
                    inputVencimento.value = adicionarDiasUteis(dataBase, dias);
                } else {
                    inputVencimento.value = "";
                }
            }
            inputDias.addEventListener('input', recalcular);
            inputDataBase.addEventListener('change', recalcular);
        }

        document.getElementById('ric-form').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const sei = document.getElementById('form-sei').value.trim();
            const ric = document.getElementById('form-ric').value.trim();
            const assunto = document.getElementById('form-assunto').value.trim();
            const responsavel = document.getElementById('form-responsavel').value.trim();
            const prazoDias = parseInt(document.getElementById('form-prazo-dias').value);
            const dataVencimento = document.getElementById('form-vencimento').value;
            const observacao = document.getElementById('form-observacao').value.trim();

            const checkboxes = document.querySelectorAll('input[name="area-tecnica"]:checked');
            const areas = Array.from(checkboxes).map(cb => cb.value);

            if (areas.length === 0) {
                mostrarToast("Erro: Selecione ao menos uma Área Técnica.", true);
                return;
            }

            const novaRic = { sei, ric, assunto, responsavel, areas, prazo_dias: prazoDias, data_vencimento: dataVencimento, observacao };

            mostrarToast("Salvando registro...");

            try {
                const response = await fetch('/api/rics', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(novaRic)
                });
                
                if (response.ok) {
                    mostrarToast("RIC cadastrada com sucesso!");
                    limparFormulario();
                    await sincronizarDados();
                } else {
                    mostrarToast("Falha ao salvar no Servidor.", true);
                }
            } catch (err) {
                mostrarToast("Erro de rede ao salvar.", true);
            }
        });

        function limparFormulario() {
            document.getElementById('ric-form').reset();
            inicializarDataFormulario();
            document.querySelectorAll('input[name="area-tecnica"]').forEach(cb => cb.checked = false);
        }

        function toggleForm() {
            const form = document.getElementById('ric-form');
            const arrow = document.getElementById('arrow-toggle');
            if (form.classList.contains('hidden')) {
                form.classList.remove('hidden');
                arrow.style.transform = 'rotate(0deg)';
            } else {
                form.classList.add('hidden');
                arrow.style.transform = 'rotate(180deg)';
            }
        }

        let email_atual = {};
        function prepararEmail(id) {
            const item = rics_data.find(r => r.id === id);
            if (!item) return;

            const emailsDestino = item.areas.map(area => {
                const conf = areasMapeamento[area];
                return conf ? conf.email : `${area.toLowerCase()}@inss.gov.br`;
            });

            const assuntoEmail = `URGENTE – Prazo próximo do vencimento – Processo SEI nº ${item.sei} (RIC ${item.ric})`;
            const dataLimite = item.data_repactuada || item.data_vencimento;
            const dataLimFormatada = formatarDataBR(dataLimite);

            const corpoEmail = `URGENTE – Prazo próximo do vencimento

Prezados(as),

Lembramos que o prazo para resposta do Processo SEI nº ${item.sei} vence em ${dataLimFormatada}. 
Solicitamos prioridade na análise e encaminhamento da manifestação da área responsável, a fim de viabilizar a resposta dentro do prazo estabelecido.

Atenciosamente,

GABPRE`;

            email_atual = { destinatarios: emailsDestino.join('; '), assunto: assuntoEmail, corpo: corpoEmail };

            document.getElementById('modal-emails-to').innerText = email_atual.destinatarios;
            document.getElementById('modal-email-subject').innerText = email_atual.assunto;
            document.getElementById('modal-email-body').innerText = email_atual.corpo;
            document.getElementById('email-modal').classList.remove('hidden');
        }

        function fecharEmailModal() { document.getElementById('email-modal').classList.add('hidden'); }

        function copiarCorpoEmail() {
            const rawText = document.getElementById('modal-email-body').innerText;
            const temp = document.createElement("textarea");
            temp.value = rawText;
            document.body.appendChild(temp);
            temp.select();
            document.execCommand("copy");
            document.body.removeChild(temp);
            mostrarToast("Texto copiado!");
        }

        function abrirClienteEmail() {
            const subject = encodeURIComponent(email_atual.assunto);
            const body = encodeURIComponent(email_atual.corpo);
            window.location.href = `mailto:${email_atual.destinatarios}?subject=${subject}&body=${body}`;
            fecharEmailModal();
        }

        function abrirRepactuar(id) {
            const item = rics_data.find(r => r.id === id);
            if (!item) return;

            document.getElementById('repactuar-id').value = item.id;
            document.getElementById('repactuar-sei-display').value = item.sei;
            const venc = item.data_repactuada || item.data_vencimento;
            document.getElementById('repactuar-vencimento-atual').value = formatarDataBR(venc);
            document.getElementById('repactuar-nova-data').value = item.data_repactuada || item.data_vencimento;
            document.getElementById('repactuar-modal').classList.remove('hidden');
        }

        function fecharRepactuarModal() { document.getElementById('repactuar-modal').classList.add('hidden'); }

        async function salvarRepactuacao() {
            const id = parseInt(document.getElementById('repactuar-id').value);
            const novaData = document.getElementById('repactuar-nova-data').value;

            if (!novaData) {
                mostrarToast("Data inválida.", true);
                return;
            }

            try {
                const response = await fetch(`/api/rics/${id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ data_repactuada: novaData })
                });
                
                if (response.ok) {
                    mostrarToast("Prazo repactuado com sucesso!");
                    fecharRepactuarModal();
                    await sincronizarDados();
                } else {
                    mostrarToast("Falha ao salvar alteração.", true);
                }
            } catch (err) {
                mostrarToast("Erro de rede.", true);
            }
        }

        async function alterarStatusConclusao(id) {
            const item = rics_data.find(r => r.id === id);
            if (!item) return;

            const novoStatus = item.status === 'Respondida' ? 'Pendente' : 'Respondida';
            try {
                const response = await fetch(`/api/rics/${id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status: novoStatus })
                });
                
                if (response.ok) {
                    mostrarToast(`Status modificado para: ${novoStatus}`);
                    await sincronizarDados();
                } else {
                    mostrarToast("Erro ao atualizar status.", true);
                }
            } catch (err) {
                mostrarToast("Erro de rede.", true);
            }
        }

        function confirmarExclusao(id, sei) {
            const container = document.createElement('div');
            container.id = 'temp-confirm-modal';
            container.className = "ric-modal-overlay";
            container.innerHTML = `
                <div class="ric-modal-box" style="max-width: 380px;">
                    <div class="ric-modal-header" style="background-color: #dc2626;">
                        <h3 style="font-size: 1.1rem; font-weight: 800;">Excluir Monitoramento?</h3>
                    </div>
                    <div class="ric-modal-body" style="gap: 0.5rem; text-align: left;">
                        <p style="font-size: 0.85rem; color: #475569; line-height: 1.5;">
                            Deseja realmente excluir o processo <strong style="color: #0f172a;">${sei}</strong>? Esta ação é permanente.
                        </p>
                    </div>
                    <div class="ric-modal-footer">
                        <button onclick="fecharConfirmacaoExclusao()" class="ric-btn ric-btn-secondary">Cancelar</button>
                        <button onclick="executarExclusao(${id})" class="ric-btn" style="background-color: #dc2626; color: #ffffff;">Excluir</button>
                    </div>
                </div>
            `;
            document.body.appendChild(container);
        }

        function fecharConfirmacaoExclusao() {
            const el = document.getElementById('temp-confirm-modal');
            if (el) el.remove();
        }

        async function executarExclusao(id) {
            fecharConfirmacaoExclusao();
            try {
                const response = await fetch(`/api/rics/${id}`, { method: 'DELETE' });
                if (response.ok) {
                    mostrarToast("RIC excluída com sucesso.");
                    await sincronizarDados();
                } else {
                    mostrarToast("Falha ao excluir.", true);
                }
            } catch (err) {
                mostrarToast("Erro de rede.", true);
            }
        }

        function renderizarDashboard() {
            const total = rics_data.length;
            let noPrazo = 0;
            let urgentes = 0;
            let atrasadas = 0;
            let concluidas = 0;
            const hoje = new Date().toISOString().split('T')[0];

            rics_data.forEach(item => {
                if (item.status === 'Respondida') {
                    concluidas++;
                } else {
                    const dataLimite = item.data_repactuada || item.data_vencimento;
                    if (dataLimite < hoje) {
                        atrasadas++;
                    } else {
                        const diffTime = Math.abs(new Date(dataLimite) - new Date(hoje));
                        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
                        if (diffDays <= 3) {
                            urgentes++;
                        } else {
                            noPrazo++;
                        }
                    }
                }
            });

            document.getElementById('stat-total').innerText = total;
            document.getElementById('stat-no-prazo').innerText = noPrazo;
            document.getElementById('stat-urgentes').innerText = urgentes;
            document.getElementById('stat-atrasadas').innerText = atrasadas;
            document.getElementById('stat-concluidas').innerText = concluidas;
        }

        function renderizarTabela() {
            const tbody = document.getElementById('rics-list');
            const noRec = document.getElementById('no-records');
            tbody.innerHTML = "";

            const busca = document.getElementById('table-search').value.toLowerCase().trim();
            const hoje = new Date().toISOString().split('T')[0];

            let itensFiltrados = rics_data.filter(item => {
                const matchBusca = 
                    item.sei.toLowerCase().includes(busca) ||
                    item.ric.toLowerCase().includes(busca) ||
                    item.assunto.toLowerCase().includes(busca) ||
                    item.responsavel.toLowerCase().includes(busca) ||
                    item.areas.some(a => a.toLowerCase().includes(busca));

                if (!matchBusca) return false;
                if (current_filter === 'Todas') return true;
                if (current_filter === 'Respondida') return item.status === 'Respondida';
                if (item.status === 'Respondida') return false;

                const dataLimite = item.data_repactuada || item.data_vencimento;
                if (current_filter === 'Atrasada') return dataLimite < hoje;
                
                if (current_filter === 'Urgente') {
                    if (dataLimite < hoje) return false;
                    const diffTime = Math.abs(new Date(dataLimite) - new Date(hoje));
                    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
                    return diffDays <= 3;
                }

                return item.status === 'Pendente';
            });

            if (itensFiltrados.length === 0) {
                noRec.classList.remove('hidden');
                return;
            }
            noRec.classList.add('hidden');

            itensFiltrados.sort((a, b) => {
                if (a.status === 'Respondida' && b.status !== 'Respondida') return 1;
                if (a.status !== 'Respondida' && b.status === 'Respondida') return -1;
                const limiteA = a.data_repactuada || a.data_vencimento;
                const limiteB = b.data_repactuada || b.data_vencimento;
                return limiteA.localeCompare(limiteB);
            });

            itensFiltrados.forEach(item => {
                const tr = document.createElement('tr');
                const dataLimite = item.data_repactuada || item.data_vencimento;
                const dataFormatada = formatarDataBR(dataLimite);
                let vencBadge = "";

                if (item.status === 'Respondida') {
                    vencBadge = `<span style="color: #64748b; font-weight: 600;">${dataFormatada}</span>`;
                } else if (dataLimite < hoje) {
                    vencBadge = `<span class="ric-deadline-atrasado">Atrasado (${dataFormatada})</span>`;
                } else {
                    const diffTime = Math.abs(new Date(dataLimite) - new Date(hoje));
                    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
                    if (diffDays <= 3) {
                        vencBadge = `<span class="ric-deadline-urgente">Urgente (${dataFormatada})</span>`;
                    } else {
                        vencBadge = `<span class="ric-deadline-normal">No Prazo (${dataFormatada})</span>`;
                    }
                }

                const labelRepactuado = item.data_repactuada 
                    ? `<div style="font-size: 10px; color: #6d28d9; font-weight: 700; margin-top: 0.25rem;">REPACTUADO (Orig: ${formatarDataBR(item.data_vencimento)})</div>` 
                    : "";

                const badgesAreas = item.areas.map(area => 
                    `<span class="ric-badge-area" title="${areasMapeamento[area]?.nome || ''}">${area}</span>`
                ).join('');

                const badgeStatus = item.status === 'Respondida'
                    ? `<span class="ric-badge-status-respondido">Respondido</span>`
                    : `<span class="ric-badge-status-pendente">Pendente</span>`;

                tr.innerHTML = `
                    <td>
                        <div style="font-weight: 700; color: #0f172a; font-size: 0.9rem;">${item.sei}</div>
                        <div style="font-size: 0.75rem; color: #64748b; font-weight: 600; margin-top: 0.15rem;">${item.ric}</div>
                    </td>
                    <td>
                        <div style="font-weight: 600; color: #334155; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 280px;" title="${item.assunto}">${item.assunto}</div>
                        ${item.observacao ? `<div style="font-size: 11px; color: #94a3b8; font-style: italic; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 280px; margin-top: 0.25rem;">${item.observacao}</div>` : ""}
                    </td>
                    <td>
                        <div style="font-size: 0.75rem; color: #475569;">Resp: <span style="font-weight: 700; color: #1e293b;">${item.responsavel}</span></div>
                        <div style="margin-top: 0.25rem;">${badgesAreas}</div>
                    </td>
                    <td>
                        <div>${vencBadge}</div>
                        ${labelRepactuado}
                    </td>
                    <td>${badgeStatus}</td>
                    <td>
                        <div class="ric-action-btn-group">
                            <button onclick="prepararEmail(${item.id})" class="ric-action-btn ric-action-btn-blue" title="Disparar Cobrança Oficial">✉️</button>
                            <button onclick="abrirRepactuar(${item.id})" class="ric-action-btn ric-action-btn-purple" title="Repactuar Prazo">📅</button>
                            <button onclick="alterarStatusConclusao(${item.id})" class="ric-action-btn ric-action-btn-green" title="${item.status === 'Respondida' ? 'Reabrir Processo' : 'Concluir Resposta'}">✓</button>
                            <button onclick="confirmarExclusao(${item.id}, '${item.sei}')" class="ric-action-btn ric-action-btn-red" title="Remover Processo">🗑️</button>
                        </div>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        }

        function formatarDataBR(dataString) {
            if (!dataString) return "";
            const partes = dataString.split('-');
            return `${partes[2]}/${partes[1]}/${partes[0]}`;
        }

        function filtrarStatus(status) {
            current_filter = status;
            document.querySelectorAll('.ric-tab').forEach(btn => {
                if (btn.innerText.trim() === status || (status === 'Todas' && btn.innerText.trim() === 'Todas') || (status === 'Urgente' && btn.innerText.trim() === 'Urgentes') || (status === 'Atrasada' && btn.innerText.trim() === 'Atrasadas') || (status === 'Pendente' && btn.innerText.trim() === 'Pendentes') || (status === 'Respondida' && btn.innerText.trim() === 'Respondidas')) {
                    btn.classList.add('ric-tab-active');
                } else {
                    btn.classList.remove('ric-tab-active');
                }
            });
            renderizarTabela();
        }

        document.getElementById('table-search').addEventListener('input', renderizarTabela);

        let toastTimeout;
        function mostrarToast(mensagem, erro = false) {
            const toast = document.getElementById('toast');
            const msg = document.getElementById('toast-message');
            const icon = document.getElementById('toast-icon');
            msg.innerText = mensagem;
            if (erro) {
                toast.style.borderColor = '#ef4444';
                icon.innerHTML = '❌';
            } else {
                toast.style.borderColor = '#10b981';
                icon.innerHTML = '✔️';
            }
            toast.classList.remove('hidden');
            clearTimeout(toastTimeout);
            toastTimeout = setTimeout(() => toast.classList.add('hidden'), 3500);
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# ENDPOINTS DA API REST CORPORATIVA (Flask)
# ------------------------------------------------------------------------------
# Abaixo estão os endpoints que servem o frontend e a API CRUD para os RICs.
# - GET  /api/rics       => lista todas as RICs
# - POST /api/rics       => cria um novo registro
# - PUT  /api/rics/<id>  => atualiza status ou data_repactuada
# - DELETE /api/rics/<id>=> remove registro
# O frontend consome essas rotas via `fetch`.
# ============================================================================


@app.route('/')
def home():
    """Servidor web nativo do painel."""
    return make_response(HTML_TEMPLATE)


@app.route('/api/rics', methods=['GET'])
def ler_rics():
    """Lê todas as RICs cadastradas no banco."""
    try:
        with obter_conexao() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM rics')
            rows = cursor.fetchall()

            resultado = []
            for r in rows:
                resultado.append({
                    'id': r['id'],
                    'sei': r['sei'],
                    'ric': r['ric'],
                    'assunto': r['assunto'],
                    'responsavel': r['responsavel'],
                    'areas': json.loads(r['areas']),
                    'prazo_dias': r['prazo_dias'],
                    'data_vencimento': r['data_vencimento'],
                    'data_repactuada': r['data_repactuada'],
                    'observacao': r['observacao'],
                    'status': r['status']
                })
            return jsonify(resultado)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@app.route('/api/rics', methods=['POST'])
def criar_ric():
    """Salva uma nova RIC no SQLite."""
    dados = request.get_json()
    if not dados:
        return jsonify({'erro': 'Payload inválido'}), 400

    try:
        with obter_conexao() as conn:
            conn.execute('''
                INSERT INTO rics (sei, ric, assunto, responsavel, areas, prazo_dias, data_vencimento, data_repactuada, observacao, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, 'Pendente')
            ''', (
                dados['sei'],
                dados['ric'],
                dados['assunto'],
                dados['responsavel'],
                json.dumps(dados['areas']),
                dados['prazo_dias'],
                dados['data_vencimento'],
                dados['observacao']
            ))
            conn.commit()
            return jsonify({'mensagem': 'Sucesso'}), 201
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@app.route('/api/rics/<int:id>', methods=['PUT'])
def atualizar_ric(id):
    """Atualiza de forma incremental (Status ou Prazo Repactuado)."""
    dados = request.get_json()
    if not dados:
        return jsonify({'erro': 'Payload inválido'}), 400

    try:
        campos_para_atualizar = []
        valores = []

        if 'status' in dados:
            campos_para_atualizar.append("status = ?")
            valores.append(dados['status'])

        if 'data_repactuada' in dados:
            campos_para_atualizar.append("data_repactuada = ?")
            valores.append(dados['data_repactuada'])

        if not campos_para_atualizar:
            return jsonify({'erro': 'Nenhum campo informado para atualização'}), 400

        valores.append(id)
        query = f"UPDATE rics SET {', '.join(campos_para_atualizar)} WHERE id = ?"

        with obter_conexao() as conn:
            cursor = conn.execute(query, valores)
            conn.commit()
            if cursor.rowcount == 0:
                return jsonify({'erro': 'Registro não encontrado'}), 404

            return jsonify({'mensagem': 'Registro atualizado'})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@app.route('/api/rics/<int:id>', methods=['DELETE'])
def deletar_ric(id):
    """Exclui permanentemente um registro."""
    try:
        with obter_conexao() as conn:
            cursor = conn.execute('DELETE FROM rics WHERE id = ?', (id,))
            conn.commit()
            if cursor.rowcount == 0:
                return jsonify({'erro': 'Registro não encontrado'}), 404
            return jsonify({'mensagem': 'Registro excluído com sucesso'})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


if __name__ == '__main__':
    # Inicializa o banco de dados local concorrente
    inicializar_banco()

    # Executa o servidor na porta corporativa 5000 (aberto para receber requisições da intranet)
    app.run(host='0.0.0.0', port=5000, debug=False)
