#!/usr/bin/env python3
"""Backend Flask para Dashboard de Varejo - Processamento em tempo real dos CSVs"""

from flask import Flask, render_template, jsonify, request
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# Caminho dos dados
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')

# Cache de dados
_data_cache = {}
_cache_timestamp = None
CACHE_TTL_SECONDS = 60


def load_data():
    """Carrega todos os CSVs como se fossem um banco de dados"""
    global _data_cache, _cache_timestamp
    
    now = datetime.now()
    if _data_cache and _cache_timestamp and (now - _cache_timestamp).total_seconds() < CACHE_TTL_SECONDS:
        return _data_cache
    
    vendas = pd.read_csv(os.path.join(DATA_DIR, 'vendas.csv'), parse_dates=['data_pedido'])
    clientes = pd.read_csv(os.path.join(DATA_DIR, 'clientes.csv'))
    marketing = pd.read_csv(os.path.join(DATA_DIR, 'marketing.csv'), parse_dates=['data_inicio', 'data_fim'])
    atendimento = pd.read_csv(os.path.join(DATA_DIR, 'atendimento.csv'), parse_dates=['data_abertura', 'data_fechamento'])
    estoque = pd.read_csv(os.path.join(DATA_DIR, 'estoque.csv'))
    
    atendimento['data_abertura'] = pd.to_datetime(atendimento['data_abertura'], errors='coerce')
    atendimento['data_fechamento'] = pd.to_datetime(atendimento['data_fechamento'], errors='coerce')
    
    _data_cache = {
        'vendas': vendas,
        'clientes': clientes,
        'marketing': marketing,
        'atendimento': atendimento,
        'estoque': estoque
    }
    _cache_timestamp = now
    return _data_cache


def get_valid_date_range(data):
    """Determina a janela válida de dados"""
    max_date = data['data_pedido'].max()
    min_date = data['data_pedido'].min()
    return min_date, max_date


def calculate_all_kpis(data, start_date, end_date):
    """Calcula todos os KPIs para um período"""
    vendas = data['vendas']
    clientes = data['clientes']
    marketing_df = data['marketing']
    atendimento_df = data['atendimento']
    estoque = data['estoque']
    
    periodo = vendas[(vendas['data_pedido'] >= start_date) & (vendas['data_pedido'] <= end_date)]
    aprovado = periodo[periodo['status_pagamento'] == 'Aprovado']
    
    # Comercial
    receita_bruta = periodo['receita_bruta'].sum()
    pedidos = periodo['order_id'].nunique()
    ticket_medio = receita_bruta / pedidos if pedidos > 0 else 0
    conversao = (aprovado['order_id'].nunique() / pedidos * 100) if pedidos > 0 else 0
    
    # Margem
    margem_contribuicao = aprovado['margem_contribuicao'].sum()
    desconto_medio = aprovado['desconto_reais'].mean() if len(aprovado) > 0 else 0
    frete_medio = aprovado['custo_frete'].mean() if len(aprovado) > 0 else 0
    
    # Marketing
    campanhas = marketing_df[(marketing_df['data_inicio'] <= end_date) & (marketing_df['data_fim'] >= start_date)]
    cac = campanhas['cac'].mean() if len(campanhas) > 0 else 0
    roas = campanhas['roas'].mean() if len(campanhas) > 0 else 0
    conversoes_mkt = campanhas['conversoes'].sum() if len(campanhas) > 0 else 0
    
    canal_margem = campanhas.groupby('canal').agg({
        'roas': 'mean', 'investimento_reais': 'sum', 'receita_gerada': 'sum'
    }).reset_index()
    canal_margem['margem_canal'] = canal_margem['receita_gerada'] - canal_margem['investimento_reais']
    margem_por_canal = canal_margem[['canal', 'margem_canal', 'roas']].to_dict('records')
    
    # Cliente
    clientes_periodo = periodo['customer_id'].unique()
    total_clientes = len(clientes_periodo)
    compras_por_cliente = vendas[vendas['customer_id'].isin(clientes_periodo)].groupby('customer_id')['order_id'].nunique()
    recompradores = (compras_por_cliente > 1).sum()
    taxa_recompra = (recompradores / total_clientes * 100) if total_clientes > 0 else 0
    ltv_medio = clientes['ltv_acumulado'].mean() if 'ltv_acumulado' in clientes.columns else 0
    ultimos_30 = end_date - timedelta(days=30)
    clientes_ativos_recentes = vendas[vendas['data_pedido'] >= ultimos_30]['customer_id'].unique()
    churn = total_clientes - len(clientes_ativos_recentes)
    churn_rate = (churn / total_clientes * 100) if total_clientes > 0 else 0
    segmentos = clientes['segmento_rfm'].value_counts().to_dict() if 'segmento_rfm' in clientes.columns else {}
    
    # Operações
    total_pedidos = len(periodo)
    devolucoes = periodo[periodo['devolvido'] == True]['order_id'].nunique()
    taxa_devolucao = (devolucoes / total_pedidos * 100) if total_pedidos > 0 else 0
    ruptura = estoque[(estoque['estoque_disponivel'] <= estoque['ponto_pedido']) | (estoque['status_disponibilidade'] == 'Estoque Crítico')]
    taxa_ruptura = (len(ruptura) / len(estoque) * 100) if len(estoque) > 0 else 0
    giro_estoque = round(periodo['quantidade'].sum() / estoque['estoque_disponivel'].sum(), 2) if estoque['estoque_disponivel'].sum() > 0 else 0
    lead_time_medio = estoque['lead_time_reposicao'].mean()
    
    # Atendimento
    periodo_atend = atendimento_df[(atendimento_df['data_abertura'] >= start_date) & (atendimento_df['data_abertura'] <= end_date)]
    volume_tickets = len(periodo_atend)
    periodo_resolvidos = periodo_atend[periodo_atend['status_atendimento'] == 'Resolvido'].copy()
    if len(periodo_resolvidos) > 0:
        periodo_resolvidos['tempo_resolucao'] = (periodo_resolvidos['data_fechamento'] - periodo_resolvidos['data_abertura']).dt.total_seconds() / 3600
        sla = (periodo_resolvidos['tempo_resolucao'] <= 24).sum() / len(periodo_resolvidos) * 100
    else:
        sla = 0
    sentimento_medio = periodo_atend['nota_csat'].mean() if 'nota_csat' in periodo_atend.columns and periodo_atend['nota_csat'].notna().any() else 0
    custo_ticket = periodo_atend['custo_operacional_ticket'].mean() if 'custo_operacional_ticket' in periodo_atend.columns else 0
    
    # Produtividade
    tickets_repetitivos = periodo_atend[periodo_atend['categoria_problema'].isin(['Onde está meu pedido?', 'Dúvida Técnica'])]
    horas_economizadas = len(tickets_repetitivos) * 0.5
    automacao_potencial = (len(tickets_repetitivos) / len(periodo_atend) * 100) if len(periodo_atend) > 0 else 0
    retrabalho_reduzido = periodo[periodo['devolvido'] == False]['order_id'].nunique()
    tempo_resposta = periodo_atend['tempo_primeira_resposta_minutos'].mean() if 'tempo_primeira_resposta_minutos' in periodo_atend.columns else 0
    
    # Impacto
    margem_total = aprovado['margem_contribuicao'].sum()
    custos_fixos_estimados = margem_total * 0.3
    ebitda_potencial = margem_total - custos_fixos_estimados
    devolucoes_evitaveis = periodo[periodo['devolvido'] == True]['margem_contribuicao'].sum()
    economia_estimada = devolucoes_evitaveis * 0.7
    receita_protegida = aprovado['receita_liquida'].sum() * 0.8
    investimento_marketing = campanhas['investimento_reais'].sum() if len(campanhas) > 0 else 0
    payback = investimento_marketing / ebitda_potencial if ebitda_potencial > 0 else 999
    
    # Rentabilidade SKU
    sku_rentability = aprovado.groupby('sku_id').agg({
        'margem_contribuicao': 'sum', 'receita_liquida': 'sum'
    }).reset_index()
    sku_rentability['rentabilidade_pct'] = (sku_rentability['margem_contribuicao'] / sku_rentability['receita_liquida'] * 100)
    top_sku = sku_rentability.nlargest(5, 'margem_contribuicao')[['sku_id', 'rentabilidade_pct']].to_dict('records')
    
    return {
        'comercial': {'receita_bruta': round(receita_bruta, 2), 'pedidos': int(pedidos), 'ticket_medio': round(ticket_medio, 2), 'conversao': round(conversao, 2)},
        'margem': {'margem_contribuicao': round(margem_contribuicao, 2), 'desconto_medio': round(desconto_medio, 2), 'frete_medio': round(frete_medio, 2), 'rentabilidade_por_sku': top_sku},
        'marketing': {'cac': round(cac, 2), 'roas': round(roas, 2), 'conversoes': int(conversoes_mkt), 'margem_por_canal': margem_por_canal},
        'cliente': {'recompra': round(taxa_recompra, 2), 'ltv': round(ltv_medio, 2), 'churn': round(churn_rate, 2), 'segmentos': segmentos},
        'operacoes': {'taxa_devolucao': round(taxa_devolucao, 2), 'ruptura': round(taxa_ruptura, 2), 'giro_estoque': giro_estoque, 'lead_time': round(lead_time_medio, 2)},
        'atendimento': {'volume_tickets': int(volume_tickets), 'sla': round(sla, 2), 'sentimento': round(sentimento_medio, 2), 'custo_por_ticket': round(custo_ticket, 2)},
        'produtividade': {'horas_economizadas': round(horas_economizadas, 2), 'automacao_potencial': round(automacao_potencial, 2), 'retrabalho_reduzido': int(retrabalho_reduzido), 'tempo_resposta': round(tempo_resposta, 2)},
        'impacto': {'ebitda_potencial': round(ebitda_potencial, 2), 'economia_estimada': round(economia_estimada, 2), 'receita_protegida': round(receita_protegida, 2), 'payback': round(min(payback, 12), 2)}
    }


def get_time_series(vendas, kpi, period_type, start_date, end_date):
    """Retorna série temporal para gráfico"""
    periodo = vendas[(vendas['data_pedido'] >= start_date) & (vendas['data_pedido'] <= end_date)]
    
    if period_type == 'dia':
        periodo['periodo'] = periodo['data_pedido'].dt.date
    elif period_type == 'semana':
        periodo['periodo'] = periodo['data_pedido'].dt.to_period('W').apply(lambda r: r.start_time)
    else:
        periodo['periodo'] = periodo['data_pedido'].dt.to_period('M').apply(lambda r: r.start_time)
    
    if kpi == 'receita_bruta':
        grouped = periodo.groupby('periodo')['receita_bruta'].sum().reset_index()
    elif kpi == 'margem_contribuicao':
        grouped = periodo[periodo['status_pagamento'] == 'Aprovado'].groupby('periodo')['margem_contribuicao'].sum().reset_index()
    elif kpi == 'pedidos':
        grouped = periodo.groupby('periodo')['order_id'].nunique().reset_index()
        grouped.columns = ['periodo', 'valor']
    elif kpi == 'ticket_medio':
        grouped = periodo.groupby('periodo').agg({'receita_bruta': 'sum', 'order_id': 'nunique'}).reset_index()
        grouped['valor'] = grouped['receita_bruta'] / grouped['order_id']
        grouped = grouped[['periodo', 'valor']]
    elif kpi == 'conversao':
        grouped = periodo.groupby('periodo').agg({'order_id': ['count', lambda x: (x == x.drop_duplicates()).sum()]})
        grouped.columns = ['periodo', 'total', 'aprovados']
        grouped['valor'] = (grouped['aprovados'] / grouped['total'] * 100)
        grouped = grouped[['periodo', 'valor']]
    else:
        grouped = periodo.groupby('periodo')['receita_bruta'].sum().reset_index()
        grouped.columns = ['periodo', 'valor']
    
    grouped['periodo'] = grouped['periodo'].astype(str)
    return grouped.to_dict('records')


def get_top_products(vendas, start_date, end_date, limit=10):
    """Top produtos mais vendidos"""
    periodo = vendas[(vendas['data_pedido'] >= start_date) & (vendas['data_pedido'] <= end_date)]
    top = periodo.groupby(['sku_id', 'produto', 'categoria']).agg({
        'quantidade': 'sum', 'receita_bruta': 'sum', 'margem_contribuicao': 'sum'
    }).reset_index()
    top = top.nlargest(limit, 'receita_bruta')
    top.columns = ['sku_id', 'produto', 'categoria', 'quantidade', 'receita_bruta', 'margem']
    return top.to_dict('records')


def get_roas_by_channel(marketing_df, start_date, end_date):
    """ROAS por canal de marketing"""
    campanhas = marketing_df[(marketing_df['data_inicio'] <= end_date) & (marketing_df['data_fim'] >= start_date)]
    roas_canal = campanhas.groupby('canal').agg({
        'roas': 'mean', 'investimento_reais': 'sum', 'receita_gerada': 'sum', 'conversoes': 'sum'
    }).reset_index()
    return roas_canal.to_dict('records')


def get_segmentos_chart(clientes, vendas, start_date, end_date):
    """Distribuição de segmentos de clientes"""
    clientes_periodo = vendas[(vendas['data_pedido'] >= start_date) & (vendas['data_pedido'] <= end_date)]['customer_id'].unique()
    clientes_filtrados = clientes[clientes['customer_id'].isin(clientes_periodo)]
    segmentos = clientes_filtrados['segmento_rfm'].value_counts().reset_index()
    segmentos.columns = ['segmento', 'count']
    return segmentos.to_dict('records')


def generate_insights(current, previous):
    """Gera insights baseados em comparação temporal"""
    insights = []
    
    var_receita = ((current['comercial']['receita_bruta'] - previous['comercial']['receita_bruta']) / previous['comercial']['receita_bruta']) * 100 if previous['comercial']['receita_bruta'] != 0 else 0
    if var_receita > 10:
        insights.append({'tipo': 'positivo', 'titulo': 'Receita em Alta', 'descricao': f'Receita cresceu {var_receita:.1f}% vs período anterior. Aproveite o momentum.', 'prioridade': 'alta' if var_receita > 20 else 'media'})
    elif var_receita < -10:
        insights.append({'tipo': 'alerta', 'titulo': 'Queda de Receita', 'descricao': f'Receita caiu {abs(var_receita):.1f}%. Revise pricing e canais.', 'prioridade': 'alta'})
    
    var_margem = ((current['margem']['margem_contribuicao'] - previous['margem']['margem_contribuicao']) / previous['margem']['margem_contribuicao']) * 100 if previous['margem']['margem_contribuicao'] != 0 else 0
    if var_margem < -5:
        insights.append({'tipo': 'alerta', 'titulo': 'Margem Comprimida', 'descricao': f'Margem caiu {abs(var_margem):.1f}%. Analise descontos e frete.', 'prioridade': 'alta'})
    
    var_devolucao = current['operacoes']['taxa_devolucao'] - previous['operacoes']['taxa_devolucao']
    if var_devolucao > 2:
        insights.append({'tipo': 'alerta', 'titulo': 'Aumento em Devoluções', 'descricao': f'Devoluções subiram {var_devolucao:.1f}pp. Investigue qualidade.', 'prioridade': 'media'})
    
    var_cac = ((current['marketing']['cac'] - previous['marketing']['cac']) / previous['marketing']['cac']) * 100 if previous['marketing']['cac'] != 0 else 0
    if var_cac > 15:
        insights.append({'tipo': 'alerta', 'titulo': 'CAC Elevado', 'descricao': f'CAC aumentou {var_cac:.1f}%. Otimize campanhas.', 'prioridade': 'alta'})
    
    var_roas = ((current['marketing']['roas'] - previous['marketing']['roas']) / previous['marketing']['roas']) * 100 if previous['marketing']['roas'] != 0 else 0
    if var_roas > 10:
        insights.append({'tipo': 'positivo', 'titulo': 'ROAS Melhorando', 'descricao': f'ROAS cresceu {var_roas:.1f}%. Escalar investimentos.', 'prioridade': 'media'})
    
    if not insights:
        insights.append({'tipo': 'info', 'titulo': 'Operação Estável', 'descricao': 'KPIs dentro da normalidade. Foco em otimização contínua.', 'prioridade': 'baixa'})
    
    priority_order = {'alta': 0, 'media': 1, 'baixa': 2}
    insights.sort(key=lambda x: priority_order.get(x['prioridade'], 3))
    return insights


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/dashboard')
def get_dashboard():
    data = load_data()
    vendas = data['vendas']
    marketing_df = data['marketing']
    clientes = data['clientes']
    
    period_type = request.args.get('period', 'dia')
    kpi_selected = request.args.get('kpi', 'receita_bruta')
    use_latest = request.args.get('latest', 'false').lower() == 'true'
    
    min_date, max_date = get_valid_date_range(vendas)
    
    if use_latest:
        end_date = max_date
        start_date = max_date - timedelta(days=6)
        data_gap_warning = f"Dados mais recentes: {start_date.strftime('%d/%m')} a {end_date.strftime('%d/%m/%Y')}"
        prev_end_date = start_date - timedelta(days=1)
        prev_start_date = prev_end_date - timedelta(days=6)
    else:
        end_date = max_date
        start_date = max_date - timedelta(days=29)
        data_gap_warning = None
        prev_end_date = start_date - timedelta(days=1)
        prev_start_date = prev_end_date - timedelta(days=29)
    
    current_kpis = calculate_all_kpis(data, start_date, end_date)
    previous_kpis = calculate_all_kpis(data, prev_start_date, prev_end_date)
    
    chart_data = get_time_series(vendas, kpi_selected, period_type, start_date, end_date)
    top_products = get_top_products(vendas, start_date, end_date)
    roas_channels = get_roas_by_channel(marketing_df, start_date, end_date)
    segmentos_dist = get_segmentos_chart(clientes, vendas, start_date, end_date)
    insights = generate_insights(current_kpis, previous_kpis)
    
    return jsonify({
        'periodo': {'inicio': start_date.strftime('%Y-%m-%d'), 'fim': end_date.strftime('%Y-%m-%d'), 'tipo': period_type, 'data_gap_warning': data_gap_warning},
        'kpis': current_kpis,
        'chart': {'kpi': kpi_selected, 'data': chart_data},
        'top_produtos': top_products,
        'roas_canais': roas_channels,
        'segmentos_distribuicao': segmentos_dist,
        'insights': insights
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
