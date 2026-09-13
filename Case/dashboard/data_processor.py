import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os

# Caminho dos dados
DATA_PATH = '../data/'

def load_data():
    """Carrega todos os datasets"""
    vendas = pd.read_csv(os.path.join(DATA_PATH, 'vendas.csv'), parse_dates=['data_pedido'])
    clientes = pd.read_csv(os.path.join(DATA_PATH, 'clientes.csv'))
    marketing = pd.read_csv(os.path.join(DATA_PATH, 'marketing.csv'), parse_dates=['data_inicio', 'data_fim'])
    atendimento = pd.read_csv(os.path.join(DATA_PATH, 'atendimento.csv'), parse_dates=['data_abertura'])
    estoque = pd.read_csv(os.path.join(DATA_PATH, 'estoque.csv'))
    return vendas, clientes, marketing, atendimento, estoque

def get_valid_date_range(vendas):
    """Determina a janela de dados válida baseada nas vendas (dados mais consistentes)"""
    min_date = vendas['data_pedido'].min()
    max_date = vendas['data_pedido'].max()
    return min_date, max_date

def filter_by_date_range(df, date_col, start_date, end_date):
    """Filtra dataframe por intervalo de datas"""
    return df[(df[date_col] >= start_date) & (df[date_col] <= end_date)]

def calculate_comercial_kpis(vendas, start_date, end_date):
    """Calcula KPIs comerciais"""
    periodo = filter_by_date_range(vendas, 'data_pedido', start_date, end_date)
    
    receita_bruta = periodo['receita_bruta'].sum()
    pedidos = periodo['order_id'].nunique()
    ticket_medio = receita_bruta / pedidos if pedidos > 0 else 0
    total_clientes = periodo['customer_id'].nunique()
    conversao = (pedidos / total_clientes * 100) if total_clientes > 0 else 0
    
    return {
        'receita_bruta': round(receita_bruta, 2),
        'pedidos': pedidos,
        'ticket_medio': round(ticket_medio, 2),
        'conversao': round(conversao, 2)
    }

def calculate_margem_kpis(vendas, start_date, end_date):
    """Calcula KPIs de margem"""
    periodo = filter_by_date_range(vendas, 'data_pedido', start_date, end_date)
    
    receita_liquida = periodo['receita_liquida'].sum()
    custo_total = periodo['custo_produto'].sum() + periodo['custo_frete'].sum()
    margem_contribuicao = periodo['margem_contribuicao'].sum()
    desconto_medio = periodo['desconto_reais'].mean()
    frete_medio = periodo['custo_frete'].mean()
    
    rentabilidade_por_sku = periodo.groupby('sku_id')['margem_contribuicao'].sum().nlargest(5).to_dict()
    rentabilidade_por_sku = {k: round(v, 2) for k, v in rentabilidade_por_sku.items()}
    
    return {
        'margem_contribuicao': round(margem_contribuicao, 2),
        'desconto_medio': round(desconto_medio, 2),
        'frete_medio': round(frete_medio, 2),
        'rentabilidade_por_sku': rentabilidade_por_sku
    }

def calculate_marketing_kpis(marketing, start_date, end_date):
    """Calcula KPIs de marketing"""
    # Filtra campanhas ativas no período
    periodo = marketing[
        (marketing['data_inicio'] <= end_date) & 
        (marketing['data_fim'] >= start_date)
    ]
    
    investimento_total = periodo['investimento_reais'].sum()
    conversoes = periodo['conversoes'].sum()
    receita_gerada = periodo['receita_gerada'].sum()
    
    cac = investimento_total / conversoes if conversoes > 0 else 0
    roas = receita_gerada / investimento_total if investimento_total > 0 else 0
    
    # Margem por canal
    margem_por_canal = periodo.groupby('canal')['roas'].mean().to_dict()
    margem_por_canal = {k: round(v, 2) for k, v in margem_por_canal.items()}
    
    return {
        'cac': round(cac, 2),
        'roas': round(roas, 2),
        'conversoes': int(conversoes),
        'margem_por_canal': margem_por_canal
    }

def calculate_cliente_kpis(clientes, vendas, start_date, end_date):
    """Calcula KPIs de cliente"""
    # Clientes ativos no período
    clientes_ativos = vendas[
        (vendas['data_pedido'] >= start_date) & 
        (vendas['data_pedido'] <= end_date)
    ]['customer_id'].unique()
    
    clientes_df = clientes[clientes['customer_id'].isin(clientes_ativos)]
    
    # Recompra (clientes com mais de 1 pedido no período)
    pedidos_por_cliente = vendas[
        (vendas['data_pedido'] >= start_date) & 
        (vendas['data_pedido'] <= end_date)
    ].groupby('customer_id')['order_id'].count()
    recompra = (pedidos_por_cliente > 1).sum() / len(pedidos_por_cliente) * 100 if len(pedidos_por_cliente) > 0 else 0
    
    # LTV médio
    ltv_medio = clientes_df['ltv_acumulado'].mean() if len(clientes_df) > 0 else 0
    
    # Churn (clientes com segmento "Churn")
    churn = (clientes_df['segmento_rfm'] == 'Churn').sum() / len(clientes_df) * 100 if len(clientes_df) > 0 else 0
    
    # Segmentos
    segmentos = clientes_df['segmento_rfm'].value_counts().to_dict()
    
    return {
        'recompra': round(recompra, 2),
        'ltv': round(ltv_medio, 2),
        'churn': round(churn, 2),
        'segmentos': segmentos
    }

def calculate_operacoes_kpis(vendas, estoque, start_date, end_date):
    """Calcula KPIs de operações"""
    periodo = filter_by_date_range(vendas, 'data_pedido', start_date, end_date)
    
    # Taxa de devolução
    total_pedidos = len(periodo)
    devolucoes = periodo['devolvido'].sum()
    taxa_devolucao = (devolucoes / total_pedidos * 100) if total_pedidos > 0 else 0
    
    # Ruptura (produtos sem estoque)
    ruptura = (estoque['estoque_disponivel'] <= 0).sum() / len(estoque) * 100 if len(estoque) > 0 else 0
    
    # Giro de estoque (simplificado)
    giro_estoque = periodo['quantidade'].sum() / estoque['estoque_disponivel'].sum() if estoque['estoque_disponivel'].sum() > 0 else 0
    
    # Lead time médio
    lead_time_medio = estoque['lead_time_reposicao'].mean()
    
    return {
        'taxa_devolucao': round(taxa_devolucao, 2),
        'ruptura': round(ruptura, 2),
        'giro_estoque': round(giro_estoque, 2),
        'lead_time': round(lead_time_medio, 1)
    }

def calculate_atendimento_kpis(atendimento, start_date, end_date):
    """Calcula KPIs de atendimento"""
    periodo = atendimento[
        (atendimento['data_abertura'] >= start_date) & 
        (atendimento['data_abertura'] <= end_date)
    ]
    
    volume_tickets = len(periodo)
    
    # SLA (tickets resolvidos dentro do esperado - simplificado)
    sla = (periodo['status_atendimento'] == 'Resolvido').sum() / len(periodo) * 100 if len(periodo) > 0 else 0
    
    # Sentimento (baseado na nota CSAT)
    sentimento = periodo['nota_csat'].mean() if len(periodo) > 0 else 0
    
    # Custo por ticket
    custo_por_ticket = periodo['custo_operacional_ticket'].mean() if len(periodo) > 0 else 0
    
    return {
        'volume_tickets': volume_tickets,
        'sla': round(sla, 2),
        'sentimento': round(sentimento, 1),
        'custo_por_ticket': round(custo_por_ticket, 2)
    }

def calculate_produtividade_kpis(vendas, atendimento, start_date, end_date):
    """Calcula KPIs de produtividade (estimativas)"""
    periodo_vendas = filter_by_date_range(vendas, 'data_pedido', start_date, end_date)
    periodo_atendimento = atendimento[
        (atendimento['data_abertura'] >= start_date) & 
        (atendimento['data_abertura'] <= end_date)
    ]
    
    # Estimativas baseadas em automação potencial
    horas_economizadas = len(periodo_vendas) * 0.05  # 3 minutos por pedido automatizado
    automacao_potencial = 65  # 65% dos processos podem ser automatizados
    retrabalho_reduzido = len(periodo_atendimento) * 0.15  # 15% de retrabalho evitado
    tempo_resposta_medio = periodo_atendimento['tempo_primeira_resposta_minutos'].mean() if len(periodo_atendimento) > 0 else 0
    
    return {
        'horas_economizadas': round(horas_economizadas, 1),
        'automacao_potencial': automacao_potencial,
        'retrabalho_reduzido': int(retrabalho_reduzido),
        'tempo_resposta': round(tempo_resposta_medio, 1)
    }

def calculate_impacto_kpis(vendas, marketing, start_date, end_date):
    """Calcula KPIs de impacto financeiro"""
    periodo_vendas = filter_by_date_range(vendas, 'data_pedido', start_date, end_date)
    periodo_marketing = marketing[
        (marketing['data_inicio'] <= end_date) & 
        (marketing['data_fim'] >= start_date)
    ]
    
    # EBITDA potencial (margem - custos operacionais estimados)
    margem_total = periodo_vendas['margem_contribuicao'].sum()
    ebitda_potencial = margem_total * 0.75  # Estimativa de 75% da margem
    
    # Economia estimada (otimização de processos)
    economia_estimada = margem_total * 0.15  # 15% de economia potencial
    
    # Receita protegida (evitando churn)
    receita_protegida = periodo_vendas['receita_liquida'].sum() * 0.9  # 90% retida
    
    # Payback (meses para retorno de investimento)
    investimento = periodo_marketing['investimento_reais'].sum()
    retorno = periodo_marketing['receita_gerada'].sum()
    payback = (investimento / retorno * 12) if retorno > 0 else 0
    
    return {
        'ebitda_potencial': round(ebitda_potencial, 2),
        'economia_estimada': round(economia_estimada, 2),
        'receita_protegida': round(receita_protegida, 2),
        'payback': round(payback, 1)
    }

def get_temporal_data(vendas, period='day'):
    """Prepara dados temporais para o gráfico principal"""
    if period == 'year':
        vendas['periodo'] = vendas['data_pedido'].dt.to_period('Y').astype(str)
    elif period == 'month':
        vendas['periodo'] = vendas['data_pedido'].dt.to_period('M').astype(str)
    elif period == 'week':
        vendas['periodo'] = vendas['data_pedido'].dt.to_period('W').astype(str)
    else:
        vendas['periodo'] = vendas['data_pedido'].dt.date.astype(str)
    
    temporal = vendas.groupby('periodo').agg({
        'receita_bruta': 'sum',
        'order_id': 'count',
        'margem_contribuicao': 'sum'
    }).reset_index()
    
    temporal.columns = ['periodo', 'receita_bruta', 'pedidos', 'margem_contribuicao']
    temporal = temporal.sort_values('periodo')
    
    return temporal.to_dict('records')

def get_top_products(vendas, start_date, end_date, top_n=10):
    """Obtém produtos mais vendidos no período"""
    periodo = filter_by_date_range(vendas, 'data_pedido', start_date, end_date)
    
    top_produtos = periodo.groupby('produto').agg({
        'quantidade': 'sum',
        'receita_bruta': 'sum',
        'margem_contribuicao': 'sum'
    }).reset_index()
    
    top_produtos = top_produtos.nlargest(top_n, 'receita_bruta')
    top_produtos['receita_bruta'] = top_produtos['receita_bruta'].round(2)
    top_produtos['margem_contribuicao'] = top_produtos['margem_contribuicao'].round(2)
    
    return top_produtos.to_dict('records')

def get_insights(comercial, margem, cliente, operacoes, atendimento):
    """Gera insights acionáveis para tomada de decisão"""
    insights = []
    
    # Insight comercial
    if comercial['conversao'] < 50:
        insights.append({
            'tipo': 'alerta',
            'area': 'Comercial',
            'mensagem': f"Taxa de conversão baixa ({comercial['conversao']}%). Oportunidade: melhorar jornada de compra.",
            'impacto': 'Alto',
            'acao': 'Otimizar checkout e reduzir atrito no funil de vendas'
        })
    
    # Insight de margem
    if margem['desconto_medio'] > 50:
        insights.append({
            'tipo': 'alerta',
            'area': 'Margem',
            'mensagem': f"Desconto médio elevado (R$ {margem['desconto_medio']}). Revisar política de descontos.",
            'impacto': 'Médio',
            'acao': 'Implementar limites de desconto por canal/vendedor'
        })
    
    # Insight de cliente
    if cliente['churn'] > 20:
        insights.append({
            'tipo': 'alerta',
            'area': 'Cliente',
            'mensagem': f"Churn alto ({cliente['churn']}%). Risco de perda de receita recorrente.",
            'impacto': 'Crítico',
            'acao': 'Criar programa de retenção e reengajamento'
        })
    
    # Insight de operações
    if operacoes['taxa_devolucao'] > 10:
        insights.append({
            'tipo': 'alerta',
            'area': 'Operações',
            'mensagem': f"Taxa de devolução elevada ({operacoes['taxa_devolucao']}%). Impacto direto na margem.",
            'impacto': 'Alto',
            'acao': 'Melhorar descrição de produtos e controle de qualidade'
        })
    
    # Insight de atendimento
    if atendimento['sla'] < 80:
        insights.append({
            'tipo': 'alerta',
            'area': 'Atendimento',
            'mensagem': f"SLA abaixo do ideal ({atendimento['sla']}%). Risco de insatisfação.",
            'impacto': 'Médio',
            'acao': 'Automatizar respostas frequentes e treinar equipe'
        })
    
    # Oportunidade positiva
    insights.append({
        'tipo': 'oportunidade',
        'area': 'Geral',
        'mensagem': f"EBITDA potencial de R$ {comercial['receita_bruta'] * 0.25:.2f} identificável através de otimizações.",
        'impacto': 'Alto',
        'acao': 'Priorizar iniciativas de eficiência operacional'
    })
    
    return insights

def main():
    # Carregar dados
    vendas, clientes, marketing, atendimento, estoque = load_data()
    
    # Determinar janela de dados válida (usando vendas como referência principal)
    min_date, max_date = get_valid_date_range(vendas)
    
    # Período de análise: últimos 30 dias até a data máxima disponível
    end_date = max_date
    start_date = max_date - timedelta(days=30)
    
    # Garantir que start_date não seja anterior ao mínimo
    if start_date < min_date:
        start_date = min_date
    
    print(f"Janela de análise: {start_date.date()} até {end_date.date()}")
    
    # Calcular todos os KPIs
    kpis = {
        'comercial': calculate_comercial_kpis(vendas, start_date, end_date),
        'margem': calculate_margem_kpis(vendas, start_date, end_date),
        'marketing': calculate_marketing_kpis(marketing, start_date, end_date),
        'cliente': calculate_cliente_kpis(clientes, vendas, start_date, end_date),
        'operacoes': calculate_operacoes_kpis(vendas, estoque, start_date, end_date),
        'atendimento': calculate_atendimento_kpis(atendimento, start_date, end_date),
        'produtividade': calculate_produtividade_kpis(vendas, atendimento, start_date, end_date),
        'impacto': calculate_impacto_kpis(vendas, marketing, start_date, end_date)
    }
    
    # Dados temporais
    temporal_day = get_temporal_data(vendas.copy(), 'day')
    temporal_week = get_temporal_data(vendas.copy(), 'week')
    temporal_month = get_temporal_data(vendas.copy(), 'month')
    
    # Top produtos
    top_produtos = get_top_products(vendas, start_date, end_date)
    
    # Insights
    insights = get_insights(
        kpis['comercial'],
        kpis['margem'],
        kpis['cliente'],
        kpis['operacoes'],
        kpis['atendimento']
    )
    
    # Preparar output JSON
    output = {
        'metadata': {
            'data_atualizacao': datetime.now().isoformat(),
            'janela_analise': {
                'inicio': str(start_date.date()),
                'fim': str(end_date.date()),
                'dias': 30
            },
            'janela_dados_completa': {
                'minimo': str(min_date.date()),
                'maximo': str(max_date.date())
            }
        },
        'kpis': kpis,
        'temporal': {
            'dia': temporal_day[-30:],  # Últimos 30 dias
            'semana': temporal_week[-12:],  # Últimas 12 semanas
            'mes': temporal_month[-12:]  # Últimos 12 meses
        },
        'top_produtos': top_produtos,
        'insights': insights
    }
    
    # Salvar JSON
    with open('dashboard_data.json', 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print("Dashboard data generated successfully!")
    print(f"Total records processed: {len(vendas)} vendas")

if __name__ == '__main__':
    main()
