import pandas as pd
from flask import Flask, jsonify, request, render_template
from datetime import datetime, timedelta
import os
import warnings
warnings.filterwarnings('ignore')

app = Flask(__name__)

# Caminho dos dados
DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data')

# Cache de dados carregados
_data_cache = {}

def load_csv(filename):
    """Carrega CSV com cache"""
    if filename not in _data_cache:
        filepath = os.path.join(DATA_PATH, filename)
        _data_cache[filename] = pd.read_csv(filepath)
    return _data_cache[filename].copy()

def get_data_info():
    """Retorna informacoes sobre os dados disponiveis"""
    vendas = load_csv('vendas.csv')
    vendas['data_pedido'] = pd.to_datetime(vendas['data_pedido'])
    
    atendimento = load_csv('atendimento.csv')
    atendimento['data_abertura'] = pd.to_datetime(atendimento['data_abertura'])
    
    min_vendas = vendas['data_pedido'].min()
    max_atend = atendimento['data_abertura'].max()
    
    latest_valid = datetime(2024, 1, 26)
    
    return {
        'latest_date': latest_valid.strftime('%Y-%m-%d'),
        'min_date': min_vendas.strftime('%Y-%m-%d'),
        'max_atendimento': max_atend.strftime('%Y-%m-%d'),
        'data_gap_days': (datetime.now() - latest_valid).days,
        'warning': 'Dados de vendas tem lacuna temporal significativa. Ultimos dados validos: 26/01/2024'
    }

def calculate_all_kpis(end_date_str, days):
    """Calcula todos os KPIs de forma simples e direta"""
    
    vendas = load_csv('vendas.csv')
    clientes = load_csv('clientes.csv')
    marketing = load_csv('marketing.csv')
    estoque = load_csv('estoque.csv')
    atendimento = load_csv('atendimento.csv')
    
    vendas['data_pedido'] = pd.to_datetime(vendas['data_pedido'])
    atendimento['data_abertura'] = pd.to_datetime(atendimento['data_abertura'])
    marketing['data_inicio'] = pd.to_datetime(marketing['data_inicio'])
    marketing['data_fim'] = pd.to_datetime(marketing['data_fim'])
    
    max_valid_date = pd.Timestamp('2024-01-26')
    vendas = vendas[vendas['data_pedido'] <= max_valid_date].copy()
    
    end_date = pd.Timestamp(end_date_str)
    start_date = end_date - timedelta(days=int(days))
    
    mask_vendas = (vendas['data_pedido'] >= start_date) & (vendas['data_pedido'] <= end_date)
    vendas_p = vendas[mask_vendas]
    
    receita_bruta = vendas_p['receita_bruta'].sum()
    pedidos = vendas_p['order_id'].nunique()
    ticket_medio = receita_bruta / pedidos if pedidos > 0 else 0
    
    mask_mkt = (marketing['data_inicio'] <= end_date) & (marketing['data_fim'] >= start_date)
    mkt_p = marketing[mask_mkt]
    total_cliques = mkt_p['cliques'].sum() if len(mkt_p) > 0 else 1
    conversao = (pedidos / total_cliques * 100) if total_cliques > 0 else 0
    
    receita_liquida = vendas_p['receita_liquida'].sum()
    custo_prod = vendas_p['custo_produto'].sum()
    custo_frete = vendas_p['custo_frete'].sum()
    margem_contribuicao = receita_liquida - custo_prod - custo_frete
    desconto_medio = vendas_p['desconto_reais'].mean() if len(vendas_p) > 0 else 0
    frete_medio = custo_frete / len(vendas_p) if len(vendas_p) > 0 else 0
    rentabilidade = (margem_contribuicao / receita_liquida * 100) if receita_liquida > 0 else 0
    
    investimento = mkt_p['investimento_reais'].sum() if len(mkt_p) > 0 else 0
    receita_mkt = mkt_p['receita_gerada'].sum() if len(mkt_p) > 0 else 0
    roas = (receita_mkt / investimento) if investimento > 0 else 0
    total_conversoes_mkt = mkt_p['conversoes'].sum() if len(mkt_p) > 0 else 1
    cac = investimento / total_conversoes_mkt if total_conversoes_mkt > 0 else 0
    
    roas_canal = mkt_p.groupby('canal')['roas'].mean() if len(mkt_p) > 0 else pd.Series()
    melhor_canal = roas_canal.idxmax() if len(roas_canal) > 0 else 'N/A'
    melhor_roas = roas_canal.max() if len(roas_canal) > 0 else 0
    
    clientes_compra = set(vendas_p['customer_id'].unique())
    clientes_p = clientes[clientes['customer_id'].isin(clientes_compra)]
    
    recompra = (clientes_p['total_pedidos_historico'] > 1).sum() / len(clientes_p) * 100 if len(clientes_p) > 0 else 0
    ltv_medio = clientes_p['ltv_acumulado'].mean() if len(clientes_p) > 0 else 0
    churn = (clientes_p['segmento_rfm'] == 'Churn').sum() / len(clientes_p) * 100 if len(clientes_p) > 0 else 0
    
    segmento_count = clientes_p['segmento_rfm'].value_counts() if len(clientes_p) > 0 else pd.Series()
    top_segmento = segmento_count.index[0] if len(segmento_count) > 0 else 'N/A'
    
    total_itens = len(vendas_p)
    devolvidos = vendas_p['devolvido'].sum()
    taxa_devolucao = (devolvidos / total_itens * 100) if total_itens > 0 else 0
    
    ruptura = (estoque['estoque_disponivel'] < estoque['ponto_pedido']).sum() / len(estoque) * 100 if len(estoque) > 0 else 0
    
    qtd_vendida = vendas_p['quantidade'].sum()
    estoque_medio = estoque['estoque_disponivel'].mean() if len(estoque) > 0 else 1
    giro_estoque = qtd_vendida / estoque_medio if estoque_medio > 0 else 0
    
    lead_time = vendas_p['tempo_entrega_real'].mean() if 'tempo_entrega_real' in vendas_p.columns and len(vendas_p) > 0 else 0
    
    atend_p = atendimento[(atendimento['data_abertura'] >= start_date) & 
                           (atendimento['data_abertura'] <= end_date)].copy()
    
    volume_tickets = len(atend_p)
    
    if len(atend_p) > 0:
        atend_p['data_fechamento'] = pd.to_datetime(atend_p['data_fechamento'], errors='coerce')
        tempo_res = (atend_p['data_fechamento'] - atend_p['data_abertura']).dt.total_seconds() / 3600
        sla = (tempo_res <= 24).sum() / len(atend_p) * 100
        csat = atend_p['nota_csat'].mean() if 'nota_csat' in atend_p.columns else 0
        custo_total = atend_p['custo_operacional_ticket'].sum() if 'custo_operacional_ticket' in atend_p.columns else 0
    else:
        sla = 0
        csat = 0
        custo_total = 0
    
    custo_por_ticket = custo_total / volume_tickets if volume_tickets > 0 else 0
    
    horas_economizadas = volume_tickets * 0.5
    automacao_potencial = 65
    retrabalho = (atend_p['status_atendimento'] == 'Reaberto').sum() / len(atend_p) * 100 if len(atend_p) > 0 else 0
    tempo_resposta = atend_p['tempo_primeira_resposta_minutos'].mean() if len(atend_p) > 0 and 'tempo_primeira_resposta_minutos' in atend_p.columns else 0
    
    ebitda_potencial = margem_contribuicao * 0.15
    economia_estimada = custo_total * (automacao_potencial / 100)
    receita_protegida = receita_bruta * (1 - taxa_devolucao / 100)
    payback = investimento / ebitda_potencial if ebitda_potencial > 0 else 0
    
    top_produtos = vendas_p.groupby('produto')['quantidade'].sum().nlargest(10).to_dict()
    
    vendas_diarias = vendas_p.groupby(vendas_p['data_pedido'].dt.date)['receita_bruta'].sum()
    margem_diaria = vendas_p.groupby(vendas_p['data_pedido'].dt.date).apply(
        lambda x: x['receita_liquida'].sum() - x['custo_produto'].sum() - x['custo_frete'].sum()
    )
    
    serie_receita = [{'data': str(k), 'valor': round(v, 2)} for k, v in vendas_diarias.to_dict().items()]
    serie_margem = [{'data': str(k), 'valor': round(v, 2)} for k, v in margem_diaria.to_dict().items()]
    
    roas_por_canal = mkt_p.groupby('canal')['roas'].mean().to_dict() if len(mkt_p) > 0 else {}
    segmentos = clientes_p['segmento_rfm'].value_counts().to_dict() if len(clientes_p) > 0 else {}
    receita_por_canal = vendas_p.groupby('canal')['receita_bruta'].sum().to_dict()
    
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
                'melhor_canal': str(melhor_canal),
                'melhor_roas': round(float(melhor_roas), 2)
            },
            'cliente': {
                'recompra': round(recompra, 2),
                'ltv': round(ltv_medio, 2),
                'churn': round(churn, 2),
                'top_segmento': str(top_segmento)
            },
            'operacoes': {
                'taxa_devolucao': round(taxa_devolucao, 2),
                'ruptura': round(ruptura, 2),
                'giro_estoque': round(giro_estoque, 4),
                'lead_time': round(lead_time, 2)
            },
            'atendimento': {
                'volume_tickets': int(volume_tickets),
                'sla': round(sla, 2),
                'csat': round(csat, 2),
                'custo_por_ticket': round(custo_por_ticket, 2)
            },
            'produtividade': {
                'horas_economizadas': round(horas_economizadas, 2),
                'automacao_potencial': automacao_potencial,
                'retrabalho': round(retrabalho, 2),
                'tempo_resposta': round(tempo_resposta, 2)
            },
            'impacto': {
                'ebitda_potencial': round(ebitda_potencial, 2),
                'economia_estimada': round(economia_estimada, 2),
                'receita_protegida': round(receita_protegida, 2),
                'payback': round(payback, 2)
            }
        },
        'serie_temporal': {
            'receita': serie_receita,
            'margem': serie_margem
        },
        'top_produtos': [{'produto': k, 'quantidade': int(v)} for k, v in top_produtos.items()],
        'roas_canal': [{'canal': k, 'roas': round(float(v), 2)} for k, v in roas_por_canal.items()],
        'segmentos': [{'segmento': k, 'count': int(v)} for k, v in segmentos.items()],
        'receita_canal': [{'canal': k, 'receita': round(float(v), 2)} for k, v in receita_por_canal.items()],
        'periodo_info': {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'days': int(days)
        }
    }

def generate_insights(current, previous):
    """Gera insights baseados em comparacao de periodos"""
    insights = []
    
    rec_atual = current['comercial']['receita_bruta']
    rec_prev = previous['comercial']['receita_bruta']
    var_rec = ((rec_atual - rec_prev) / rec_prev * 100) if rec_prev > 0 else 0
    
    if var_rec < -5:
        insights.append({
            'prioridade': 'ALTA',
            'area': 'Comercial',
            'problema': f'Receita caiu {abs(var_rec):.1f}% vs periodo anterior',
            'acao': 'Revisar estrategia de precos e promocoes; intensificar campanhas nos canais de maior conversao',
            'impacto': f'R$ {abs(rec_atual - rec_prev):,.2f} em receita perdida'
        })
    
    margem_atual = current['margem']['margem_contribuicao']
    margem_prev = previous['margem']['margem_contribuicao']
    var_margem = ((margem_atual - margem_prev) / margem_prev * 100) if margem_prev > 0 else 0
    
    if var_margem < -5:
        insights.append({
            'prioridade': 'ALTA',
            'area': 'Margem',
            'problema': f'Margem de contribuicao reduziu {abs(var_margem):.1f}%',
            'acao': 'Negociar custos com fornecedores; revisar politica de descontos e fretes',
            'impacto': f'R$ {abs(margem_atual - margem_prev):,.2f} em margem perdida'
        })
    
    vol_atual = current['atendimento']['volume_tickets']
    vol_prev = previous['atendimento']['volume_tickets']
    csat_atual = current['atendimento']['csat']
    sla_atual = current['atendimento']['sla']
    
    if vol_atual > 0 and (vol_atual > vol_prev * 1.1 or csat_atual < 4.0 or sla_atual < 80):
        insights.append({
            'prioridade': 'CRITICA',
            'area': 'Atendimento',
            'problema': f'Volume: {vol_atual} tickets | CSAT: {csat_atual:.1f}/5 | SLA: {sla_atual:.1f}%',
            'acao': 'Expandir equipe imediatamente; implementar chatbot para questoes repetitivas; criar base de autoatendimento',
            'impacto': f'Potencial de reduzir {int(vol_atual * 0.3)} tickets com automacao | Economia: R$ {current["impacto"]["economia_estimada"]:,.2f}'
        })
    
    devolucao = current['operacoes']['taxa_devolucao']
    if devolucao > 3:
        insights.append({
            'prioridade': 'MEDIA',
            'area': 'Operacoes',
            'problema': f'Taxa de devolucao em {devolucao:.1f}%',
            'acao': 'Investigar motivos de devolucao; melhorar descricao de produtos; revisar controle de qualidade',
            'impacto': f'R$ {current["comercial"]["receita_bruta"] * devolucao / 100:,.2f} em devolucoes'
        })
    
    roas_atual = current['marketing']['roas']
    if roas_atual < 3:
        insights.append({
            'prioridade': 'MEDIA',
            'area': 'Marketing',
            'problema': f'ROAS medio de {roas_atual:.2f}',
            'acao': f'Realocar budget para canal {current["marketing"]["melhor_canal"]} (ROAS: {current["marketing"]["melhor_roas"]:.2f})',
            'impacto': f'Potencial de +{((3.0 - roas_atual) * 100):.0f}% em eficiencia'
        })
    
    churn = current['cliente']['churn']
    if churn > 15:
        insights.append({
            'prioridade': 'ALTA',
            'area': 'Cliente',
            'problema': f'{churn:.1f}% da base em risco de churn',
            'acao': 'Criar campanha de reativacao; oferecer beneficios para segmento em risco',
            'impacto': f'R$ {current["cliente"]["ltv"] * churn / 100 * 10:,.2f} em LTV em risco'
        })
    
    ordem = {'CRITICA': 0, 'ALTA': 1, 'MEDIA': 2, 'BAIXA': 3}
    insights.sort(key=lambda x: ordem.get(x['prioridade'], 4))
    
    return insights[:5]

@app.route('/api/dates')
def api_dates():
    """Retorna informacoes sobre datas disponiveis"""
    return jsonify(get_data_info())

@app.route('/api/kpis')
def api_kpis():
    """Retorna KPIs para o periodo selecionado"""
    end_date = request.args.get('end_date', '2024-01-26')
    days = request.args.get('days', '30')
    recent = request.args.get('recent', 'false').lower() == 'true'
    
    data = calculate_all_kpis(end_date, days)
    
    end_date_dt = pd.Timestamp(end_date)
    prev_end = end_date_dt - timedelta(days=int(days))
    prev_data = calculate_all_kpis(prev_end.strftime('%Y-%m-%d'), days)
    
    data['insights'] = generate_insights(data['kpis'], prev_data['kpis'])
    data['data_warning'] = get_data_info()['warning']
    
    return jsonify(data)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
