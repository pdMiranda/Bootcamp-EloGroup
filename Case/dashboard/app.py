#!/usr/bin/env python3
"""Backend Flask para o Dashboard de Varejo - Processamento de dados em tempo real dos CSVs"""

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
CACHE_TTL_SECONDS = 60  # Atualiza cache a cada 60 segundos


def load_data():
    """Carrega todos os CSVs como se fossem um banco de dados"""
    global _data_cache, _cache_timestamp
    
    now = datetime.now()
    if _data_cache and _cache_timestamp and (now - _cache_timestamp).total_seconds() < CACHE_TTL_SECONDS:
        return _data_cache
    
    # Carregar todos os CSVs
    vendas = pd.read_csv(os.path.join(DATA_DIR, 'vendas.csv'), parse_dates=['data_pedido'])
    clientes = pd.read_csv(os.path.join(DATA_DIR, 'clientes.csv'))
    marketing = pd.read_csv(os.path.join(DATA_DIR, 'marketing.csv'), parse_dates=['data_inicio', 'data_fim'])
    atendimento = pd.read_csv(os.path.join(DATA_DIR, 'atendimento.csv'), parse_dates=['data_abertura', 'data_fechamento'])
    estoque = pd.read_csv(os.path.join(DATA_DIR, 'estoque.csv'))
    
    # Normalizar datas
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
    """Determina a janela válida de dados baseado na última data disponível"""
    max_date = data['data_pedido'].max()
    min_date = data['data_pedido'].min()
    return min_date, max_date


def calculate_comercial_kpis(vendas, start_date, end_date):
    """Calcula KPIs da área Comercial"""
    periodo = vendas[(vendas['data_pedido'] >= start_date) & (vendas['data_pedido'] <= end_date)]
    
    receita_bruta = periodo['receita_bruta'].sum()
    pedidos = periodo['order_id'].nunique()
    ticket_medio = receita_bruta / pedidos if pedidos > 0 else 0
    conversao = (periodo[periodo['status_pagamento'] == 'Aprovado']['order_id'].nunique() / pedidos * 100) if pedidos > 0 else 0
    
    return {
        'receita_bruta': round(receita_bruta, 2),
        'pedidos': int(pedidos),
        'ticket_medio': round(ticket_medio, 2),
        'conversao': round(conversao, 2)
    }


def calculate_margem_kpis(vendas, start_date, end_date):
    """Calcula KPIs da área Margem"""
    periodo = vendas[(vendas['data_pedido'] >= start_date) & (vendas['data_pedido'] <= end_date)]
    aprovado = periodo[periodo['status_pagamento'] == 'Aprovado']
    
    margem_contribuicao = aprovado['margem_contribuicao'].sum()
    desconto_medio = aprovado['desconto_reais'].mean() if len(aprovado) > 0 else 0
    frete_medio = aprovado['custo_frete'].mean() if len(aprovado) > 0 else 0
    
    # Rentabilidade por SKU
    sku_rentability = aprovado.groupby('sku_id').agg({
        'margem_contribuicao': 'sum',
        'receita_liquida': 'sum'
    }).reset_index()
    sku_rentability['rentabilidade_pct'] = (sku_rentability['margem_contribuicao'] / sku_rentability['receita_liquida'] * 100)
    top_sku = sku_rentability.nlargest(5, 'margem_contribuicao')[['sku_id', 'rentabilidade_pct']].to_dict('records')
    
    return {
        'margem_contribuicao': round(margem_contribuicao, 2),
        'desconto_medio': round(desconto_medio, 2),
        'frete_medio': round(frete_medio, 2),
        'rentabilidade_por_sku': top_sku
    }


def calculate_marketing_kpis(marketing_df, start_date, end_date):
    """Calcula KPIs da área Marketing"""
    # Campanhas ativas no período
    campanhas = marketing_df[
        (marketing_df['data_inicio'] <= end_date) & 
        (marketing_df['data_fim'] >= start_date)
    ]
    
    cac = campanhas['cac'].mean() if len(campanhas) > 0 else 0
    roas = campanhas['roas'].mean() if len(campanhas) > 0 else 0
    conversoes = campanhas['conversoes'].sum() if len(campanhas) > 0 else 0
    
    # Margem por canal
    canal_margem = campanhas.groupby('canal').agg({
        'roas': 'mean',
        'investimento_reais': 'sum',
        'receita_gerada': 'sum'
    }).reset_index()
    canal_margem['margem_canal'] = canal_margem['receita_gerada'] - canal_margem['investimento_reais']
    margem_por_canal = canal_margem[['canal', 'margem_canal', 'roas']].to_dict('records')
    
    return {
        'cac': round(cac, 2),
        'roas': round(roas, 2),
        'conversoes': int(conversoes),
        'margem_por_canal': margem_por_canal
    }


def calculate_cliente_kpis(clientes_df, vendas, start_date, end_date):
    """Calcula KPIs da área Cliente"""
    # Recompra
    clientes_periodo = vendas[(vendas['data_pedido'] >= start_date) & (vendas['data_pedido'] <= end_date)]['customer_id'].unique()
    total_clientes = len(clientes_periodo)
    
    # Clientes com mais de 1 compra
    compras_por_cliente = vendas[vendas['customer_id'].isin(clientes_periodo)].groupby('customer_id')['order_id'].nunique()
    recompradores = (compras_por_cliente > 1).sum()
    taxa_recompra = (recompradores / total_clientes * 100) if total_clientes > 0 else 0
    
    # LTV médio
    ltv_medio = clientes_df['ltv_acumulado'].mean() if 'ltv_acumulado' in clientes_df.columns else 0
    
    # Churn (clientes sem compra nos últimos 30 dias do período)
    ultimos_30 = end_date - timedelta(days=30)
    clientes_ativos_recentes = vendas[vendas['data_pedido'] >= ultimos_30]['customer_id'].unique()
    churn = total_clientes - len(clientes_ativos_recentes)
    churn_rate = (churn / total_clientes * 100) if total_clientes > 0 else 0
    
    # Segmentos
    segmentos = clientes_df['segmento_rfm'].value_counts().to_dict() if 'segmento_rfm' in clientes_df.columns else {}
    
    return {
        'recompra': round(taxa_recompra, 2),
        'ltv': round(ltv_medio, 2),
        'churn': round(churn_rate, 2),
        'segmentos': segmentos
    }


def calculate_operacoes_kpis(vendas, estoque, start_date, end_date):
    """Calcula KPIs da área Operações"""
    periodo = vendas[(vendas['data_pedido'] >= start_date) & (vendas['data_pedido'] <= end_date)]
    
    # Taxa de devolução
    total_pedidos = len(periodo)
    devolucoes = periodo[periodo['devolvido'] == True]['order_id'].nunique()
    taxa_devolucao = (devolucoes / total_pedidos * 100) if total_pedidos > 0 else 0
    
    # Ruptura (produtos com estoque zerado ou crítico)
    ruptura = estoque[(estoque['estoque_disponivel'] <= estoque['ponto_pedido']) | (estoque['status_disponibilidade'] == 'Estoque Crítico')]
    taxa_ruptura = (len(ruptura) / len(estoque) * 100) if len(estoque) > 0 else 0
    
    # Giro de estoque (simplificado)
    giro_estoque = round(periodo['quantidade'].sum() / estoque['estoque_disponivel'].sum(), 2) if estoque['estoque_disponivel'].sum() > 0 else 0
    
    # Lead time médio
    lead_time_medio = estoque['lead_time_reposicao'].mean()
    
    return {
        'taxa_devolucao': round(taxa_devolucao, 2),
        'ruptura': round(taxa_ruptura, 2),
        'giro_estoque': giro_estoque,
        'lead_time': round(lead_time_medio, 2)
    }


def calculate_atendimento_kpis(atendimento_df, start_date, end_date):
    """Calcula KPIs da área Atendimento"""
    # Filtrar tickets no período
    periodo = atendimento_df[
        (atendimento_df['data_abertura'] >= start_date) & 
        (atendimento_df['data_abertura'] <= end_date)
    ]
    
    volume_tickets = len(periodo)
    
    # SLA (tickets resolvidos em até 24h)
    periodo_resolvidos = periodo[periodo['status_atendimento'] == 'Resolvido'].copy()
    if len(periodo_resolvidos) > 0:
        periodo_resolvidos['tempo_resolucao'] = (periodo_resolvidos['data_fechamento'] - periodo_resolvidos['data_abertura']).dt.total_seconds() / 3600
        sla = (periodo_resolvidos['tempo_resolucao'] <= 24).sum() / len(periodo_resolvidos) * 100
    else:
        sla = 0
    
    # Sentimento (baseado na nota CSAT)
    sentimento_medio = periodo['nota_csat'].mean() if 'nota_csat' in periodo.columns and periodo['nota_csat'].notna().any() else 0
    
    # Custo por ticket
    custo_ticket = periodo['custo_operacional_ticket'].mean() if 'custo_operacional_ticket' in periodo.columns else 0
    
    return {
        'volume_tickets': int(volume_tickets),
        'sla': round(sla, 2),
        'sentimento': round(sentimento_medio, 2),
        'custo_por_ticket': round(custo_ticket, 2)
    }


def calculate_produtividade_kpis(vendas, atendimento_df, start_date, end_date):
    """Calcula KPIs de Produtividade (estimativas baseadas em automação potencial)"""
    periodo_vendas = vendas[(vendas['data_pedido'] >= start_date) & (vendas['data_pedido'] <= end_date)]
    periodo_atendimento = atendimento_df[
        (atendimento_df['data_abertura'] >= start_date) & 
        (atendimento_df['data_abertura'] <= end_date)
    ]
    
    # Horas economizadas (estimativa: automação de tickets repetitivos)
    tickets_repetitivos = periodo_atendimento[periodo_atendimento['categoria_problema'].isin(['Onde está meu pedido?', 'Dúvida Técnica'])]
    horas_economizadas = len(tickets_repetitivos) * 0.5  # 30 min por ticket automatizado
    
    # Automação potencial (% de tickets automatizáveis)
    automacao_potencial = (len(tickets_repetitivos) / len(periodo_atendimento) * 100) if len(periodo_atendimento) > 0 else 0
    
    # Retrabalho reduzido (pedidos sem devolução)
    retrabalho_reduzido = periodo_vendas[periodo_vendas['devolvido'] == False]['order_id'].nunique()
    
    # Tempo de resposta médio
    tempo_resposta = periodo_atendimento['tempo_primeira_resposta_minutos'].mean() if 'tempo_primeira_resposta_minutos' in periodo_atendimento.columns else 0
    
    return {
        'horas_economizadas': round(horas_economizadas, 2),
        'automacao_potencial': round(automacao_potencial, 2),
        'retrabalho_reduzido': int(retrabalho_reduzido),
        'tempo_resposta': round(tempo_resposta, 2)
    }


def calculate_impacto_kpis(vendas, marketing_df, start_date, end_date):
    """Calcula KPIs de Impacto Financeiro"""
    periodo = vendas[(vendas['data_pedido'] >= start_date) & (vendas['data_pedido'] <= end_date)]
    aprovado = periodo[periodo['status_pagamento'] == 'Aprovado']
    
    # EBITDA potencial (margem de contribuição - custos fixos estimados)
    margem_total = aprovado['margem_contribuicao'].sum()
    custos_fixos_estimados = margem_total * 0.3  # Estimativa de 30%
    ebitda_potencial = margem_total - custos_fixos_estimados
    
    # Economia estimada (com automação e redução de devoluções)
    devolucoes_evitaveis = periodo[periodo['devolvido'] == True]['margem_contribuicao'].sum()
    economia_estimada = devolucoes_evitaveis * 0.7  # 70% das devoluções são evitáveis
    
    # Receita protegida (clientes fiéis)
    receita_protegida = aprovado[aprovado['status_pagamento'] == 'Aprovado']['receita_liquida'].sum() * 0.8  # 80% da receita é recorrente
    
    # Payback (meses para recuperar investimento)
    investimento_marketing = marketing_df[
        (marketing_df['data_inicio'] <= end_date) & 
        (marketing_df['data_fim'] >= start_date)
    ]['investimento_reais'].sum()
    payback = investimento_marketing / ebitda_potencial if ebitda_potencial > 0 else 999
    
    return {
        'ebitda_potencial': round(ebitda_potencial, 2),
        'economia_estimada': round(economia_estimada, 2),
        'receita_protegida': round(receita_protegida, 2),
        'payback': round(min(payback, 12), 2)  # Máximo 12 meses
    }


def get_time_series_data(vendas, kpi, period_type, start_date, end_date):
    """Retorna dados temporais para o gráfico principal"""
    periodo = vendas[(vendas['data_pedido'] >= start_date) & (vendas['data_pedido'] <= end_date)]
    
    if period_type == 'dia':
        periodo['periodo'] = periodo['data_pedido'].dt.date
    elif period_type == 'semana':
        periodo['periodo'] = periodo['data_pedido'].dt.to_period('W').apply(lambda r: r.start_time)
    else:  # mês
        periodo['periodo'] = periodo['data_pedido'].dt.to_period('M').apply(lambda r: r.start_time)
    
    # Agrupar por período
    if kpi == 'receita_bruta':
        grouped = periodo.groupby('periodo')['receita_bruta'].sum().reset_index()
    elif kpi == 'pedidos':
        grouped = periodo.groupby('periodo')['order_id'].nunique().reset_index()
        grouped.columns = ['periodo', 'valor']
    elif kpi == 'ticket_medio':
        grouped = periodo.groupby('periodo').agg({'receita_bruta': 'sum', 'order_id': 'nunique'}).reset_index()
        grouped['valor'] = grouped['receita_bruta'] / grouped['order_id']
        grouped = grouped[['periodo', 'valor']]
    elif kpi == 'margem_contribuicao':
        grouped = periodo[periodo['status_pagamento'] == 'Aprovado'].groupby('periodo')['margem_contribuicao'].sum().reset_index()
        grouped.columns = ['periodo', 'valor']
    elif kpi == 'conversao':
        grouped = periodo.groupby('periodo').agg({
            'order_id': ['count', lambda x: (x == x.drop_duplicates()).sum()]
        }).reset_index()
        grouped.columns = ['periodo', 'total', 'aprovados']
        grouped['valor'] = (grouped['aprovados'] / grouped['total'] * 100)
        grouped = grouped[['periodo', 'valor']]
    else:
        grouped = periodo.groupby('periodo')['receita_bruta'].sum().reset_index()
        grouped.columns = ['periodo', 'valor']
    
    grouped['periodo'] = grouped['periodo'].astype(str)
    return grouped.to_dict('records')


def get_top_products(vendas, start_date, end_date, limit=10):
    """Retorna produtos mais vendidos no período"""
    periodo = vendas[(vendas['data_pedido'] >= start_date) & (vendas['data_pedido'] <= end_date)]
    
    top = periodo.groupby(['sku_id', 'produto', 'categoria']).agg({
        'quantidade': 'sum',
        'receita_bruta': 'sum',
        'margem_contribuicao': 'sum'
    }).reset_index()
    
    top = top.nlargest(limit, 'receita_bruta')
    top.columns = ['sku_id', 'produto', 'categoria', 'quantidade', 'receita_bruta', 'margem']
    
    return top.to_dict('records')


def generate_insights(current_kpis, previous_kpis, period_label):
    """Gera insights baseados em comparação temporal"""
    insights = []
    
    # Comparar receita
    if current_kpis.get('receita_bruta') and previous_kpis.get('receita_bruta'):
        var_receita = ((current_kpis['receita_bruta'] - previous_kpis['receita_bruta']) / previous_kpis['receita_bruta']) * 100
        if var_receita > 10:
            insights.append({
                'tipo': 'positivo',
                'titulo': 'Receita em Alta',
                'descricao': f'Receita cresceu {var_receita:.1f}% vs período anterior. Aproveite o momentum com campanhas de upsell.',
                'prioridade': 'alta' if var_receita > 20 else 'media'
            })
        elif var_receita < -10:
            insights.append({
                'tipo': 'alerta',
                'titulo': 'Queda de Receita',
                'descricao': f'Receita caiu {abs(var_receita):.1f}% vs período anterior. Revise pricing e canais de aquisição.',
                'prioridade': 'alta'
            })
    
    # Comparar margem
    if current_kpis.get('margem_contribuicao') and previous_kpis.get('margem_contribuicao'):
        var_margem = ((current_kpis['margem_contribuicao'] - previous_kpis['margem_contribuicao']) / previous_kpis['margem_contribuicao']) * 100
        if var_margem < -5:
            insights.append({
                'tipo': 'alerta',
                'titulo': 'Margem Comprimida',
                'descricao': f'Margem caiu {abs(var_margem):.1f}%. Analise descontos excessivos e custos de frete.',
                'prioridade': 'alta'
            })
    
    # Comparar taxa de devolução
    if current_kpis.get('taxa_devolucao') and previous_kpis.get('taxa_devolucao'):
        var_devolucao = current_kpis['taxa_devolucao'] - previous_kpis['taxa_devolucao']
        if var_devolucao > 2:
            insights.append({
                'tipo': 'alerta',
                'titulo': 'Aumento em Devoluções',
                'descricao': f'Taxa de devolução subiu {var_devolucao:.1f}pp. Investigue qualidade e descrições de produto.',
                'prioridade': 'media'
            })
    
    # Comparar CAC
    if current_kpis.get('cac') and previous_kpis.get('cac'):
        var_cac = ((current_kpis['cac'] - previous_kpis['cac']) / previous_kpis['cac']) * 100
        if var_cac > 15:
            insights.append({
                'tipo': 'alerta',
                'titulo': 'CAC Elevado',
                'descricao': f'CAC aumentou {var_cac:.1f}%. Otimize campanhas e foque em retenção.',
                'prioridade': 'alta'
            })
    
    # Comparar churn
    if current_kpis.get('churn') and previous_kpis.get('churn'):
        var_churn = current_kpis['churn'] - previous_kpis['churn']
        if var_churn > 5:
            insights.append({
                'tipo': 'alerta',
                'titulo': 'Churn Acelerando',
                'descricao': f'Churn aumentou {var_churn:.1f}pp. Implemente programa de fidelidade e re-engajamento.',
                'prioridade': 'alta'
            })
    
    # Insight positivo de ROAS
    if current_kpis.get('roas') and previous_kpis.get('roas'):
        var_roas = ((current_kpis['roas'] - previous_kpis['roas']) / previous_kpis['roas']) * 100
        if var_roas > 10:
            insights.append({
                'tipo': 'positivo',
                'titulo': 'ROAS Melhorando',
                'descricao': f'ROAS cresceu {var_roas:.1f}%. Escalar investimentos nos canais performáticos.',
                'prioridade': 'media'
            })
    
    # Se não houver insights críticos, adicionar insight padrão
    if not insights:
        insights.append({
            'tipo': 'info',
            'titulo': 'Operação Estável',
            'descricao': 'KPIs dentro da normalidade. Foco em otimização contínua e testes A/B.',
            'prioridade': 'baixa'
        })
    
    # Ordenar por prioridade
    priority_order = {'alta': 0, 'media': 1, 'baixa': 2}
    insights.sort(key=lambda x: priority_order.get(x['prioridade'], 3))
    
    return insights


@app.route('/')
def index():
    """Renderiza o dashboard"""
    return render_template('index.html')


@app.route('/api/data-overview')
def get_data_overview():
    """Retorna visão geral dos dados disponíveis"""
    data = load_data()
    vendas = data['vendas']
    
    min_date, max_date = get_valid_date_range(vendas)
    
    return jsonify({
        'min_date': min_date.strftime('%Y-%m-%d'),
        'max_date': max_date.strftime('%Y-%m-%d'),
        'total_vendas': len(vendas),
        'data_lake_status': 'online'
    })


@app.route('/api/dashboard')
def get_dashboard_data():
    """Endpoint principal do dashboard"""
    data = load_data()
    vendas = data['vendas']
    clientes = data['clientes']
    marketing_df = data['marketing']
    atendimento_df = data['atendimento']
    estoque = data['estoque']
    
    # Parâmetros
    period_type = request.args.get('period', 'dia')
    kpi_selected = request.args.get('kpi', 'receita_bruta')
    use_latest = request.args.get('latest', 'false').lower() == 'true'
    
    # Determinar período
    min_date, max_date = get_valid_date_range(vendas)
    
    if use_latest:
        # Período mais recente disponível (últimos 7 dias com dados)
        end_date = max_date
        start_date = max_date - timedelta(days=6)
        data_gap_warning = f"Dados mais recentes: {start_date.strftime('%d/%m')} a {end_date.strftime('%d/%m/%Y')}"
        
        # Período anterior para comparação
        prev_end_date = start_date - timedelta(days=1)
        prev_start_date = prev_end_date - timedelta(days=6)
    else:
        # Últimos 30 dias completos até a data máxima
        end_date = max_date
        start_date = max_date - timedelta(days=29)
        data_gap_warning = None
        
        # Período anterior para comparação (30 dias antes)
        prev_end_date = start_date - timedelta(days=1)
        prev_start_date = prev_end_date - timedelta(days=29)
    
    # Calcular KPIs do período atual
    comercial = calculate_comercial_kpis(vendas, start_date, end_date)
    margem = calculate_margem_kpis(vendas, start_date, end_date)
    marketing = calculate_marketing_kpis(marketing_df, start_date, end_date)
    cliente = calculate_cliente_kpis(clientes, vendas, start_date, end_date)
    operacoes = calculate_operacoes_kpis(vendas, estoque, start_date, end_date)
    atendimento = calculate_atendimento_kpis(atendimento_df, start_date, end_date)
    produtividade = calculate_produtividade_kpis(vendas, atendimento_df, start_date, end_date)
    impacto = calculate_impacto_kpis(vendas, marketing_df, start_date, end_date)
    
    # Calcular KPIs do período anterior
    comercial_prev = calculate_comercial_kpis(vendas, prev_start_date, prev_end_date)
    margem_prev = calculate_margem_kpis(vendas, prev_start_date, prev_end_date)
    marketing_prev = calculate_marketing_kpis(marketing_df, prev_start_date, prev_end_date)
    cliente_prev = calculate_cliente_kpis(clientes, vendas, prev_start_date, prev_end_date)
    operacoes_prev = calculate_operacoes_kpis(vendas, estoque, prev_start_date, prev_end_date)
    
    # Juntar todos os KPIs
    current_kpis = {**comercial, **margem, **marketing, **cliente, **operacoes, **atendimento, **produtividade, **impacto}
    previous_kpis = {**comercial_prev, **margem_prev, **marketing_prev, **cliente_prev, **operacoes_prev}
    
    # Gerar insights
    insights = generate_insights(current_kpis, previous_kpis, period_type)
    
    # Dados para gráfico temporal
    chart_data = get_time_series_data(vendas, kpi_selected, period_type, start_date, end_date)
    
    # Top produtos
    top_products = get_top_products(vendas, start_date, end_date)
    
    return jsonify({
        'periodo': {
            'inicio': start_date.strftime('%Y-%m-%d'),
            'fim': end_date.strftime('%Y-%m-%d'),
            'tipo': period_type,
            'data_gap_warning': data_gap_warning
        },
        'kpis': {
            'comercial': comercial,
            'margem': margem,
            'marketing': marketing,
            'cliente': cliente,
            'operacoes': operacoes,
            'atendimento': atendimento,
            'produtividade': produtividade,
            'impacto': impacto
        },
        'chart': {
            'kpi': kpi_selected,
            'data': chart_data
        },
        'top_produtos': top_products,
        'insights': insights
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
