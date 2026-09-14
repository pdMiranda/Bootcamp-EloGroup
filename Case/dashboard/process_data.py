import json
from pathlib import Path

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
DATA_ROOT = BASE_DIR.parent / "data"
OUTPUT_PATH = BASE_DIR / "dashboard_data.json"
CUTOFF = pd.Timestamp("2024-01-26 23:59:59")


def safe_float(value):
    if pd.isna(value) or np.isinf(value):
        return 0.0
    return float(value)


def safe_int(value):
    if pd.isna(value) or np.isinf(value):
        return 0
    return int(value)


def load_data():
    return {
        "vendas": pd.read_csv(DATA_ROOT / "vendas.csv", parse_dates=["data_pedido"]),
        "clientes": pd.read_csv(DATA_ROOT / "clientes.csv", parse_dates=["data_cadastro", "data_nascimento"]),
        "estoque": pd.read_csv(DATA_ROOT / "estoque.csv", parse_dates=["data_ultima_entrada"]),
        "marketing": pd.read_csv(DATA_ROOT / "marketing.csv", parse_dates=["data_inicio", "data_fim"]),
        "atendimento": pd.read_csv(DATA_ROOT / "atendimento.csv", parse_dates=["data_abertura", "data_fechamento"]),
    }


def aggregate_period(source, date_column, period):
    frame = source[source[date_column].notna()].copy()
    if period == "semana":
        frame[period] = frame[date_column].dt.strftime("%Y-W%W")
    elif period == "mes":
        frame[period] = frame[date_column].dt.strftime("%Y-%m")
    else:
        frame[period] = frame[date_column].dt.strftime("%Y")
    return frame


def temporal_series(vendas, marketing, atendimento):
    result = {}
    for period in ("semana", "mes", "ano"):
        sales = aggregate_period(vendas, "data_pedido", period)
        ads = aggregate_period(marketing, "data_inicio", period)
        support = aggregate_period(atendimento, "data_abertura", period)
        sales_agg = sales.groupby(period).agg(
            receita_bruta=("receita_bruta", "sum"),
            margem_contribuicao=("margem_contribuicao", "sum"),
            pedidos=("order_id", "nunique"),
        )
        sales_agg["ticket_medio"] = np.where(sales_agg["pedidos"] > 0, sales_agg["receita_bruta"] / sales_agg["pedidos"], 0)
        ads_agg = ads.groupby(period).agg(
            investimento_ads=("investimento_reais", "sum"),
            conversoes=("conversoes", "sum"),
            receita_ads=("receita_gerada", "sum"),
        )
        ads_agg["cac"] = np.where(ads_agg["conversoes"] > 0, ads_agg["investimento_ads"] / ads_agg["conversoes"], 0)
        ads_agg["roas"] = np.where(ads_agg["investimento_ads"] > 0, ads_agg["receita_ads"] / ads_agg["investimento_ads"], 0)
        support_agg = support.groupby(period).agg(
            volume_tickets=("ticket_id", "count"),
            csat_medio=("nota_csat", "mean"),
        )
        combined = sales_agg.join(ads_agg, how="outer").join(support_agg, how="outer").fillna(0).reset_index()
        combined = combined.rename(columns={period: "periodo"})
        result[period] = []
        for row in combined.to_dict("records"):
            normalized = {}
            for key, value in row.items():
                if key in {"pedidos", "conversoes", "volume_tickets"}:
                    normalized[key] = safe_int(value)
                elif isinstance(value, (int, float, np.integer, np.floating)):
                    normalized[key] = safe_float(value)
                else:
                    normalized[key] = value
            result[period].append(normalized)
    return result

def chanel_rfm(vendas, clientes, marketing):
    vendas = vendas.merge(clientes[["customer_id", "segmento_rfm"]], on="customer_id", how="inner")

    sales = vendas.groupby("canal").agg(
        receita=("receita_liquida", "sum"),
        receita_bruta=("receita_bruta", "sum"),
        margem_vendas=("margem_contribuicao", "sum"),
        pedidos=("order_id", "nunique"),
        pedidos_unico=("quantidade", lambda values: (values == 1).sum()),
        clientes_totais=("customer_id", "nunique"),
        segmento_predominante=("segmento_rfm", lambda x: x.mode()[0] if not x.empty else ""),
    )
    # Cálculo do Ticket Médio por canal
    sales["ticket_medio"] = np.where(sales["pedidos"] > 0, sales["receita_bruta"] / sales["pedidos"], 0.0)

    rfm_counts = (
        vendas.groupby(["canal", "segmento_rfm"])["customer_id"]
        .nunique()
        .unstack(fill_value=0)
    )

    ads = marketing.groupby("canal").agg(
        investimento=("investimento_reais", "sum"),
        conversoes_ads=("conversoes", "sum"),
        receita_ads=("receita_gerada", "sum"),
    )

    result = sales.join(rfm_counts).join(ads, how="outer").fillna(0).reset_index()
    result["margem_liquida_real"] = result["receita_ads"] - result["investimento"]
    result["roi_margem"] = np.where(result["investimento"] > 0, result["margem_liquida_real"] / result["investimento"], 0)
    result["pct_item_unico"] = np.where(result["pedidos"] > 0, result["pedidos_unico"] / result["pedidos"], 0)

    records = result.to_dict("records")
    for r in records:
        for k, v in r.items():
            if isinstance(v, (np.integer, int)):
                r[k] = safe_int(v)
            elif isinstance(v, (np.floating, float)):
                r[k] = safe_float(v)

    return records

def shipping_analysis(vendas):
    frete = vendas.groupby("canal").agg(
        pedidos=("order_id", "nunique"),
        receita_bruta=("receita_bruta", "sum"),
        custo_frete_total=("custo_frete", "sum"),
        frete_medio=("custo_frete", "mean"),
        pedidos_margem_neg=("margem_contribuicao", lambda values: (values < 0).sum()),
        pedidos_frete_gratis=("custo_frete", lambda values: (values == 0).sum()),
    )

    frete["ticket_medio"] = np.where(frete["pedidos"] > 0, frete["receita_bruta"] / frete["pedidos"], 0.0)
    frete["peso_frete_pct"] = np.where(frete["receita_bruta"] > 0, (frete["custo_frete_total"] / frete["receita_bruta"]) * 100, 0.0)
    frete["pct_pedidos_margem_neg"] = np.where(frete["pedidos"] > 0, (frete["pedidos_margem_neg"] / frete["pedidos"]) * 100, 0.0)

    result = frete.reset_index()
    records = result.to_dict("records")
    for r in records:
        for k, v in r.items():
            if isinstance(v, (np.integer, int)):
                r[k] = safe_int(v)
            elif isinstance(v, (np.floating, float)):
                r[k] = safe_float(round(v, 2))

    return records

def channel_analysis(vendas, marketing):
    sales = vendas.groupby("canal").agg(
        receita=("receita_liquida", "sum"),
        receita_bruta=("receita_bruta", "sum"),
        margem_vendas=("margem_contribuicao", "sum"),
        pedidos=("order_id", "nunique"),
        pedidos_unico=("quantidade", lambda values: (values == 1).sum()),
    )
    ads = marketing.groupby("canal").agg(
        investimento=("investimento_reais", "sum"),
        conversoes_ads=("conversoes", "sum"),
        receita_ads=("receita_gerada", "sum"),
    )
    result = sales.join(ads, how="outer").fillna(0).reset_index()
    result["margem_liquida_real"] = result["receita_ads"] - result["investimento"]
    result["roi_margem"] = np.where(result["investimento"] > 0, result["margem_liquida_real"] / result["investimento"], 0)
    result["pct_item_unico"] = np.where(result["pedidos"] > 0, result["pedidos_unico"] / result["pedidos"], 0)
    return result.to_dict("records")


def stock_and_bundles(vendas, estoque):
    produtos = (
        vendas.groupby(["sku_id", "produto"])
        .agg(
            faturamento=("receita_liquida", "sum"),
            margem=("margem_contribuicao", "sum"),
            receita_bruta=("receita_bruta", "sum"),
            unidades=("quantidade", "sum"),
        )
        .reset_index()
    )
    produtos = produtos[produtos["receita_bruta"] > 0].copy()
    produtos["rentabilidade"] = produtos["margem"] / produtos["receita_bruta"]
    produtos = (
        produtos.sort_values(["rentabilidade", "faturamento"], ascending=[False, False])
        .merge(estoque[["sku_id", "estoque_disponivel", "status_disponibilidade"]], on="sku_id", how="left")
        .rename(columns={"status_disponibilidade": "status_estoque"})
    )
    moda_excesso = estoque[(estoque["categoria"] == "Moda") & (estoque["estoque_disponivel"] > 1000)]
    companion = estoque[estoque["categoria"].isin(["Beleza", "Lifestyle"])].nlargest(5, "preco_venda_sugerido")
    bundles = []
    for _, fashion in moda_excesso.nlargest(5, "estoque_disponivel").iterrows():
        if companion.empty:
            continue
        product = companion.iloc[0]
        bundles.append({
            "sku_moda": fashion["sku_id"],
            "produto_moda": fashion["nome_produto"],
            "estoque_moda": safe_int(fashion["estoque_disponivel"]),
            "sku_companion": product["sku_id"],
            "produto_companion": product["nome_produto"],
            "categoria_companion": product["categoria"],
            "racional": "Bundle cross-category para elevar a densidade do carrinho",
        })
    excess = moda_excesso[["sku_id", "nome_produto", "estoque_disponivel"]].to_dict("records")
    return produtos.to_dict("records"), excess, bundles


def build_kpis(vendas, clientes, estoque, marketing, atendimento):
    receita = vendas["receita_bruta"].sum()
    pedidos = vendas["order_id"].nunique()
    aprovados = vendas.loc[vendas["status_pagamento"] == "Aprovado", "order_id"].nunique()
    wismo = atendimento[atendimento["categoria_problema"] == "Onde está meu pedido?"]
    sales_quantity = vendas["quantidade"].sum()
    stock_quantity = estoque["estoque_fisico"].sum()
    resolved = (atendimento["status_atendimento"] == "Resolvido").sum()
    sku_profitability = (
        vendas.groupby(["sku_id", "produto"])
        .agg(receita_bruta=("receita_bruta", "sum"), margem_contribuicao=("margem_contribuicao", "sum"))
        .reset_index()
    )
    sku_profitability["rentabilidade"] = np.where(
        sku_profitability["receita_bruta"] > 0,
        sku_profitability["margem_contribuicao"] / sku_profitability["receita_bruta"],
        0,
    )
    sku_profitability = sku_profitability[sku_profitability["receita_bruta"] > 0]
    best_skus = sku_profitability.nlargest(5, "rentabilidade")
    worst_skus = sku_profitability.nsmallest(5, "rentabilidade")
    sku_profitability = pd.concat([best_skus, worst_skus])
    segments = clientes["segmento_rfm"].value_counts().rename_axis("segmento").reset_index(name="clientes")
    positive_sentiment = (atendimento["nota_csat"] >= 4).mean()
    return {
        "comercial": {
            "receita_bruta": safe_float(receita),
            "pedidos_aprovados": safe_int(aprovados),
            "ticket_medio": safe_float(receita / pedidos) if pedidos else 0.0,
            "taxa_conversao": safe_float(marketing["conversoes"].sum() / marketing["cliques"].sum()) if marketing["cliques"].sum() else 0.0,
        },
        "margem": {
            "margem_contribuicao": safe_float(vendas["margem_contribuicao"].sum()),
            "margem_pct": safe_float(vendas["margem_contribuicao"].sum() / receita) if receita else 0.0,
            "desconto_medio_pct": safe_float(vendas["desconto_reais"].sum() / receita) if receita else 0.0,
            "frete_medio": safe_float(vendas["custo_frete"].mean()),
            "rentabilidade_por_sku": [
                {
                    "sku_id": row["sku_id"],
                    "produto": row["produto"],
                    "receita_bruta": safe_float(row["receita_bruta"]),
                    "margem_contribuicao": safe_float(row["margem_contribuicao"]),
                    "rentabilidade": safe_float(row["rentabilidade"]),
                }
                for row in sku_profitability.to_dict("records")
            ],
        },
        "marketing": {
            "cac_ponderado": safe_float(marketing["investimento_reais"].sum() / marketing["conversoes"].sum()) if marketing["conversoes"].sum() else 0.0,
            "roas_consolidado": safe_float(marketing["receita_gerada"].sum() / marketing["investimento_reais"].sum()) if marketing["investimento_reais"].sum() else 0.0,
            "conversoes_totais": safe_int(marketing["conversoes"].sum()),
        },
        "clientes": {
            "ltv_medio": safe_float(clientes["ltv_acumulado"].mean()),
            "ltv_risco": safe_float(clientes.loc[clientes["segmento_rfm"] == "Em Risco", "ltv_acumulado"].sum()),
            "recompra_pct": safe_float((clientes["total_pedidos_historico"] > 1).mean()),
            "churn_pct": safe_float(clientes["segmento_rfm"].isin(["Em Risco", "Hibernando"]).mean()),
            "segmentos": segments.to_dict("records"),
        },
        "operacoes": {
            "taxa_devolucao": safe_float(vendas["devolvido"].mean()) if len(vendas) else 0.0,
            "ruptura_pct": safe_float((estoque["status_disponibilidade"] == "Ruptura").mean()),
            "giro_estoque": safe_float(sales_quantity / stock_quantity) if stock_quantity else 0.0,
            "lead_time_medio": safe_float(estoque["lead_time_reposicao"].mean()),
        },
        "atendimento": {
            "volume_total": safe_int(len(atendimento)),
            "sla_pct": safe_float(resolved / len(atendimento)) if len(atendimento) else 0.0,
            "csat_medio": safe_float(atendimento["nota_csat"].mean()),
            "sentimento_positivo_pct": safe_float(positive_sentiment),
            "custo_medio_ticket": safe_float(atendimento["custo_operacional_ticket"].mean()),
        },
        "produtividade": {
            "horas_poupadas_chatbot": safe_float((wismo["canal_entrada"] == "ChatBot").sum() * 0.25),
            "potencial_automacao_wismo_pct": safe_float(len(wismo) / len(atendimento)) if len(atendimento) else 0.0,
        },
    }


def build_mode(data):
    vendas = data["vendas"]
    marketing = data["marketing"][data["marketing"]["data_inicio"] <= CUTOFF]
    atendimento = data["atendimento"][data["atendimento"]["data_abertura"] <= CUTOFF]
    negative = vendas[vendas["margem_contribuicao"] < 0]
    h3 = negative.groupby("categoria").agg(
        receita_bruta=("receita_bruta", "sum"), custo_frete=("custo_frete", "sum"), desconto=("desconto_reais", "sum")
    ).reset_index()
    h3["peso_frete_pct"] = np.where(h3["receita_bruta"] > 0, h3["custo_frete"] / h3["receita_bruta"], 0)
    h3["peso_desconto_pct"] = np.where(h3["receita_bruta"] > 0, h3["desconto"] / h3["receita_bruta"], 0)
    produtos, excess, bundles = stock_and_bundles(vendas, data["estoque"])
    wismo = atendimento[atendimento["categoria_problema"] == "Onde está meu pedido?"]
    devolvidos = data["vendas"][data["vendas"]["devolvido"].fillna(False)]
    impact_actions = [
        {"nome": "Automação WISMO", "valor": 127728.00},
        {"nome": "Realocação Marketing", "valor": 246855.00},
        {"nome": "Redução Devoluções", "valor": 304637.00},
        {"nome": "Reposição Rupturas", "valor": 75557.00},
    ]
    impact_total = sum(action["valor"] for action in impact_actions)
    return {
        "kpis": build_kpis(vendas, data["clientes"], data["estoque"], marketing, atendimento),
        "temporal": temporal_series(vendas, marketing, atendimento),
        "canais": channel_analysis(vendas, marketing),
        "analise_frete": shipping_analysis(vendas),
        "canais_rfm": chanel_rfm(vendas, data["clientes"], marketing),
        "hipoteses": {
            "margem_negativa_h3": h3.to_dict("records"),
            "pedidos_margem_negativa": safe_int(len(negative)),
            "sobre_estoque_h4": excess,
            "bundles_sugeridos": bundles,
            "atendimento_h5_h6": {
                "taxa_devolucao_pct": safe_float(data["vendas"]["devolvido"].mean()),
                "margem_perdida": safe_float(data["vendas"].loc[data["vendas"]["devolvido"].fillna(False), "margem_contribuicao"].sum()),
                "wismo_qtd": safe_int(len(wismo)),
                "wismo_custo": safe_float(wismo.loc[wismo["canal_entrada"] != "ChatBot", "custo_operacional_ticket"].sum()),
            },
        },
        "impacto": {
            "recuperacao_ebitda": 754778.81,
            "economia_estimada": impact_total,
            "receita_protegida": safe_float(devolvidos["receita_bruta"].sum()),
            "payback_meses": 2.6,
            "acoes": impact_actions,
        },
        "produtos_ordenados": produtos,
        "rfm": data["clientes"]["segmento_rfm"].value_counts().rename_axis("segmento").reset_index(name="quantidade").to_dict("records"),
        "vendas_encerradas_em": "2024-01-26",
    }


def process_data():
    data = load_data()
    dashboard_data = {
        "meta": {"atualizado_em": pd.Timestamp.now().isoformat(), "fonte": "CSV + Pandas"},
        "modo_integrado": build_mode(data),
    }
    with OUTPUT_PATH.open("w", encoding="utf-8") as output:
        json.dump(dashboard_data, output, ensure_ascii=False, indent=2, allow_nan=False)


if __name__ == "__main__":
    process_data()
