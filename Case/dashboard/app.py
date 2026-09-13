import pandas as pd
from flask import Flask, jsonify, request, render_template
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# Caminho dos dados
DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data')

# Cache de dados carregados
_data_cache = {}

def load_csv(filename):
    """Carrega CSV com cache simples"""
    if filename not in _data_cache:
        filepath = os.path.join(DATA_PATH, filename)
        _data_cache[filename] = pd.read_csv(filepath)
    return _data_cache[filename]

def get_data_dates():
    """Retorna datas disponíveis nos dados"""
    vendas = load_csv('vendas.csv')
    vendas['data_pedido'] = pd.to_datetime(vendas['data_pedido'])
    
    atendimento = load_csv('atendimento.csv')
    atendimento['data_abertura'] = pd.to_datetime(atendimento['data_abertura'])
    
    max_vendas = vendas['data_pedido'].max()
    max_atendimento = atendimento['data_abertura'].max()
    
    # Data mais recente válida (26/01/2024 para vendas)
    latest_date = min(max_vendas, datetime(2024, 1, 26))
    
    return {
        'latest_date': latest_date.strftime('%Y-%m-%d'),
        'min_date': vendas['data_pedido'].min().strftime('%Y-%m-%d'),
        'data_gap_days': (datetime.now() - latest_date).days
    }

def filter_period(df, date_col, end_date, days):
    """Filtra dataframe por período"""
    start_date = end_date - timedelta(days=days)
    mask = (df[date_col] >= start_date) & (df[date_col] <= end_date)
    return df[mask].copy()

def calculate_kpis(end_date_str, days, use_recent=False):
    """Calcula todos os KPIs para o período"""
    
    # Carregar dados
    vendas = load_csv('vendas.csv').copy()
    clientes = load_csv('clientes.csv').copy()
    marketing = load_csv('marketing.csv').copy()
    estoque = load_csv('estoque.csv').copy()
    atendimento = load_csv('atendimento.csv').copy()
    
    # Converter datas
    vendas['data_pedido'] = pd.to_datetime(vendas['data_pedido'])
    atendimento['data_abertura'] = pd.to_datetime(atendimento['data_abertura'])
    
    # Determinar data final e período
    if use_recent:
        end_date = pd.to_datetime(end_date_str)
        # Período recente: últimos 7 dias disponíveis
        days = 7
    else:
        end_date = pd.to_datetime(end_date_str)
        days = days if days else 30
    
    start_date = end_date - timedelta(days=days)
    
    # Filtrar vendas no período
    mask_vendas = (vendas['data_pedido'] >= start_date) & (vendas['data_pedido'] <= end_date)
    vendas_periodo = vendas[mask_vendas]
    
    # === KPIs COMERCIAIS ===
    receita_bruta = vendas_periodo['receita_bruta'].sum()
    pedidos = vendas_periodo['order_id'].nunique()
    ticket_medio = receita_bruta / pedidos if pedidos > 0 else 0
    
    # Conversão: pedidos únicos / sessões estimadas (impressões marketing)
    marketing_periodo = marketing[(pd.to_datetime(marketing['data_inicio']) <= end_date) & 
                                   (pd.to_datetime(marketing['data_fim']) >= start_date)]
    impressoes = marketing_periodo['cliques'].sum() if len(marketing_periodo) > 0 else 1
    conversao = (pedidos / impressoes * 100) if impressoes > 0 else 0
    
    # === KPIs MARGEM ===
    receita_liquida = vendas_periodo['receita_liquida'].sum()
    custo_produto = vendas_periodo['custo_produto'].sum()
    custo_frete = vendas_periodo['custo_frete'].sum()
    margem_contribuicao = receita_liquida - custo_produto - custo_frete
    desconto_medio = (vendas_periodo['desconto_reais'].sum() / len(vendas_periodo)) if len(vendas_periodo) > 0 else 0
    frete_medio = custo_frete / len(vendas_periodo) if len(vendas_periodo) > 0 else 0
    rentabilidade = (margem_contribuicao / receita_liquida * 100) if receita_liquida > 0 else 0
    
    # === KPIs MARKETING ===
    investimento_total = marketing_periodo['investimento_reais'].sum()
    receita_marketing = marketing_periodo['receita_gerada'].sum()
    roas = (receita_marketing / investimento_total) if investimento_total > 0 else 0
    cac = investimento_total / marketing_periodo['conversoes'].sum() if marketing_periodo['conversoes'].sum() > 0 else 0
    
    # Canal com melhor ROAS
    roas_por_canal = marketing_periodo.groupby('canal')['roas'].mean()
    melhor_canal = roas_por_canal.idxmax() if len(roas_por_canal) > 0 else 'N/A'
    melhor_roas = roas_por_canal.max() if len(roas_por_canal) > 0 else 0
    
    # === KPIs CLIENTE ===
    clientes_compra = vendas_periodo['customer_id'].unique()
    clientes_df = clientes[clientes['customer_id'].isin(clientes_compra)]
    
    # Recompra: clientes com mais de 1 pedido no histórico
    recompra = (clientes_df['total_pedidos_historico'] > 1).sum() / len(clientes_df) * 100 if len(clientes_df) > 0 else 0
    ltv_medio = clientes_df['ltv_acumulado'].mean() if len(clientes_df) > 0 else 0
    
    # Churn: clientes no segmento Churn
    churn = (clientes_df['segmento_rfm'] == 'Churn').sum() / len(clientes_df) * 100 if len(clientes_df) > 0 else 0
    
    # Top segmento
    segmento_count = clientes_df['segmento_rfm'].value_counts()
    top_segmento = segmento_count.index[0] if len(segmento_count) > 0 else 'N/A'
    
    # === KPIs OPERAÇÕES ===
    total_pedidos = len(vendas_periodo)
    devolvidos = vendas_periodo['devolvido'].sum()
    taxa_devolucao = (devolvidos / total_pedidos * 100) if total_pedidos > 0 else 0
    
    # Ruptura: produtos com estoque_disponivel < ponto_pedido
    ruptura = (estoque['estoque_disponivel'] < estoque['ponto_pedido']).sum() / len(estoque) * 100
    
    # Giro de estoque: vendas / estoque médio (simplificado)
    giro_estoque = (vendas_periodo['quantidade'].sum() / estoque['estoque_disponivel'].mean()) if estoque['estoque_disponivel'].mean() > 0 else 0
    
    # Lead time médio
    lead_time_medio = vendas_periodo['tempo_entrega_real'].mean() if 'tempo_entrega_real' in vendas_periodo.columns else 0
    
    # === KPIs ATENDIMENTO ===
    tickets_periodo = atendimento[(atendimento['data_abertura'] >= start_date) & 
                                    (atendimento['data_abertura'] <= end_date)]
    volume_tickets = len(tickets_periodo)
    
    # SLA: tickets resolvidos dentro de 24h
    if len(tickets_periodo) > 0 and 'data_fechamento' in tickets_periodo.columns:
        tickets_periodo['data_fechamento'] = pd.to_datetime(tickets_periodo['data_fechamento'])
        tempo_resolucao = (tickets_periodo['data_fechamento'] - tickets_periodo['data_abertura']).dt.total_seconds() / 3600
        sla = (tempo_resolucao <= 24).sum() / len(tickets_periodo) * 100
    else:
        sla = 0
    
    # CSAT médio
    csat_medio = tickets_periodo['nota_csat'].mean() if 'nota_csat' in tickets_periodo.columns and len(tickets_periodo) > 0 else 0
    
    # Custo por ticket
    custo_ticket = tickets_periodo['custo_operacional_ticket'].sum() if 'custo_operacional_ticket' in tickets_periodo.columns else 0
    custo_por_ticket = custo_ticket / volume_tickets if volume_tickets > 0 else 0
    
    # === KPIs PRODUTIVIDADE ===
    horas_economizadas = volume_tickets * 0.5  # Estimativa: 30 min por ticket automatizado
    automacao_potencial = 65  # % estimado
    retrabalho = (tickets_periodo['status_atendimento'] == 'Reaberto').sum() / len(tickets_periodo) * 100 if len(tickets_periodo) > 0 else 0
    tempo_resposta_medio = tickets_periodo['tempo_primeira_resposta_minutos'].mean() if 'tempo_primeira_resposta_minutos' in tickets_periodo.columns and len(tickets_periodo) > 0 else 0
    
    # === KPIs IMPACTO ===
    ebitda_potencial = margem_contribuicao * 0.15  # 15% da margem como potencial
    economia_estimada = custo_ticket * (automacao_potencial / 100)
    receita_protegida = receita_bruta * (1 - taxa_devolucao / 100)
    payback = investimento_total / ebitda_potencial if ebitda_potencial > 0 else 0
    
    # === TOP PRODUTOS ===
    top_produtos = vendas_periodo.groupby('produto')['quantidade'].sum().nlargest(10).to_dict()
    
    # === DADOS TEMPORAIS PARA GRÁFICO ===
    vendas_diarias = vendas_periodo.groupby(vendas_periodo['data_pedido'].dt.date)['receita_bruta'].sum()
    margem_diaria = vendas_periodo.groupby(vendas_periodo['data_pedido'].dt.date).apply(
        lambda x: x['receita_liquida'].sum() - x['custo_produto'].sum() - x['custo_frete'].sum()
    )
    
    serie_receita = vendas_diarias.to_dict()
    serie_margem = margem_diaria.to_dict()
    
    # === ROAS POR CANAL ===
    roas_canal = marketing_periodo.groupby('canal')['roas'].mean().to_dict()
    
    # === SEGMENTOS ===
    segmentos = clientes_df['segmento_rfm'].value_counts().to_dict()
    
    # === RECEITA POR CANAL DE VENDA ===
    receita_canal = vendas_periodo.groupby('canal')['receita_bruta'].sum().to_dict()
    
    return {
        'kpis': {
            'comercial': {
                'receita_bruta': round(receita_bruta, 2),
                'pedidos': int(pedidos),
                'ticket_medio': round(ticket_medio, 2),
                'conversao': round(conversao, 4)
            },
            'margem': {
                'margem_contribuicao': round(margem_contribuicao, 2),
                'desconto_medio': round(desconto_medio, 2),
                'frete_medio': round(frete_medio, 2),
                'rentabilidade': round(rentabilidade, 2)
            },
            'marketing': {
                'cac': round(cac, 2),
                'roas': round(roas, 2),
                'melhor_canal': melhor_canal,
                'melhor_roas': round(melhor_roas, 2)
            },
            'cliente': {
                'recompra': round(recompra, 2),
                'ltv': round(ltv_medio, 2),
                'churn': round(churn, 2),
                'top_segmento': top_segmento
            },
            'operacoes': {
                'taxa_devolucao': round(taxa_devolucao, 2),
                'ruptura': round(ruptura, 2),
                'giro_estoque': round(giro_estoque, 2),
                'lead_time': round(lead_time_medio, 2)
            },
            'atendimento': {
                'volume_tickets': int(volume_tickets),
                'sla': round(sla, 2),
                'csat': round(csat_medio, 2),
                'custo_por_ticket': round(custo_por_ticket, 2)
            },
            'produtividade': {
                'horas_economizadas': round(horas_economizadas, 2),
                'automacao_potencial': automacao_potencial,
                'retrabalho': round(retrabalho, 2),
                'tempo_resposta': round(tempo_resposta_medio, 2)
            },
            'impacto': {
                'ebitda_potencial': round(ebitda_potencial, 2),
                'economia_estimada': round(economia_estimada, 2),
                'receita_protegida': round(receita_protegida, 2),
                'payback': round(payback, 2)
            }
        },
        'serie_temporal': {
            'receita': [{'data': str(k), 'valor': round(v, 2)} for k, v in serie_receita.items()],
            'margem': [{'data': str(k), 'valor': round(v, 2)} for k, v in serie_margem.items()]
        },
        'top_produtos': [{'produto': k, 'quantidade': int(v)} for k, v in top_produtos.items()],
        'roas_canal': [{'canal': k, 'roas': round(v, 2)} for k, v in roas_canal.items()],
        'segmentos': [{'segmento': k, 'count': int(v)} for k, v in segmentos.items()],
        'receita_canal': [{'canal': k, 'receita': round(v, 2)} for k, v in receita_canal.items()],
        'periodo_info': {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'days': days,
            'use_recent': use_recent
        }
    }

def generate_insights(current_kpis, prev_kpis):
    """Gera insights baseados em comparação temporal"""
    insights = []
    
    # Análise Comercial
    rec_atual = current_kpis['comercial']['receita_bruta']
    rec_anterior = prev_kpis['comercial']['receita_bruta']
    var_rec = ((rec_atual - rec_anterior) / rec_anterior * 100) if rec_anterior > 0 else 0
    
    if var_rec < -10:
        insights.append({
            'prioridade': 'ALTA',
            'area': 'Comercial',
            'problema': f'Receita caiu {abs(var_rec):.1f}% vs período anterior',
            'acao': 'Revisar estratégia de preços e promoções; intensificar campanhas nos canais de maior conversão',
            'impacto': f'R$ {abs(rec_atual - rec_anterior):,.2f} em receita perdida'
        })
    
    # Análise Margem
    margem_atual = current_kpis['margem']['margem_contribuicao']
    margem_anterior = prev_kpis['margem']['margem_contribuicao']
    var_margem = ((margem_atual - margem_anterior) / margem_anterior * 100) if margem_anterior > 0 else 0
    
    if var_margem < -5:
        insights.append({
            'prioridade': 'ALTA',
            'area': 'Margem',
            'problema': f'Margem de contribuição reduziu {abs(var_margem):.1f}%',
            'acao': 'Negociar custos com fornecedores; revisar política de descontos e fretes',
            'impacto': f'R$ {abs(margem_atual - margem_anterior):,.2f} em margem perdida'
        })
    
    # Análise Atendimento - CRÍTICO
    vol_atual = current_kpis['atendimento']['volume_tickets']
    vol_anterior = prev_kpis['atendimento']['volume_tickets']
    var_vol = ((vol_atual - vol_anterior) / vol_anterior * 100) if vol_anterior > 0 else 0
    
    csat_atual = current_kpis['atendimento']['csat']
    sla_atual = current_kpis['atendimento']['sla']
    
    if vol_atual > vol_anterior * 1.2 or csat_atual < 3.5:
        insights.append({
            'prioridade': 'CRÍTICA',
            'area': 'Atendimento',
            'problema': f'Volume de tickets aumentou {var_vol:.1f}% | CSAT: {csat_atual:.1f}/5 | SLA: {sla_atual:.1f}%',
            'acao': 'Expandir equipe de atendimento; implementar chatbot para questões repetitivas; criar base de autoatendimento',
            'impacto': f'Potencial de reduzir {vol_atual * 0.3:.0f} tickets com automação | Economia: R$ {current_kpis["impacto"]["economia_estimada"]:,.2f}'
        })
    
    # Análise Operações
    devolucao_atual = current_kpis['operacoes']['taxa_devolucao']
    if devolucao_atual > 5:
        insights.append({
            'prioridade': 'MÉDIA',
            'area': 'Operações',
            'problema': f'Taxa de devolução em {devolucao_atual:.1f}% (acima do benchmark de 5%)',
            'acao': 'Investigar motivos de devolução; melhorar descrição de produtos; revisar controle de qualidade',
            'impacto': f'R$ {current_kpis["comercial"]["receita_bruta"] * devolucao_atual / 100:,.2f} em devoluções'
        })
    
    # Análise Marketing
    roas_atual = current_kpis['marketing']['roas']
    if roas_atual < 2:
        insights.append({
            'prioridade': 'MÉDIA',
            'area': 'Marketing',
            'problema': f'ROAS médio de {roas_atual:.2f} abaixo do ideal (2.0+)',
            'acao': f'Realocar budget para canal {current_kpis["marketing"]["melhor_canal"]} (ROAS: {current_kpis["marketing"]["melhor_roas"]:.2f})',
            'impacto': f'Potencial de +{((2.0 - roas_atual) * current_kpis["marketing"]["cac"] * 100):.0f}% em eficiência'
        })
    
    # Análise Cliente
    churn_atual = current_kpis['cliente']['churn']
    if churn_atual > 20:
        insights.append({
            'prioridade': 'ALTA',
            'area': 'Cliente',
            'problema': f'{churn_atual:.1f}% da base em risco de churn',
            'acao': 'Criar campanha de reativação; oferecer benefícios para segmento em risco; melhorar pós-venda',
            'impacto': f'R$ {current_kpis["cliente"]["ltv"] * churn_atual / 100 * 100:,.2f} em LTV em risco'
        })
    
    # Ordenar por prioridade
    ordem_prioridade = {'CRÍTICA': 0, 'ALTA': 1, 'MÉDIA': 2, 'BAIXA': 3}
    insights.sort(key=lambda x: ordem_prioridade.get(x['prioridade'], 4))
    
    return insights[:5]  # Top 5 insights

@app.route('/api/dates')
def api_dates():
    """Retorna informações sobre datas disponíveis"""
    return jsonify(get_data_dates())

@app.route('/api/kpis')
def api_kpis():
    """Retorna KPIs para o período selecionado"""
    end_date = request.args.get('end_date', get_data_dates()['latest_date'])
    days = int(request.args.get('days', 30))
    use_recent = request.args.get('recent', 'false').lower() == 'true'
    
    kpis = calculate_kpis(end_date, days, use_recent)
    
    # Calcular período anterior para comparação
    end_date_dt = pd.to_datetime(end_date)
    prev_end = end_date_dt - timedelta(days=days)
    prev_start = prev_end - timedelta(days=days)
    
    kpis_prev = calculate_kpis(prev_end.strftime('%Y-%m-%d'), days, False)
    
    # Gerar insights
    kpis['insights'] = generate_insights(kpis['kpis'], kpis_prev['kpis'])
    
    return jsonify(kpis)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
