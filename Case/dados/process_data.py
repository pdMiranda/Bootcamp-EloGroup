import json
from pathlib import Path

import numpy as np
import pandas as pd

# Resolução de diretórios com suporte a múltiplos ambientes de execução
BASE_DIR = Path(__file__).resolve().parent


def get_data_root():
    candidates = [
        BASE_DIR.parent / "data",
        BASE_DIR / "data",
        BASE_DIR,
        Path("data"),
        Path("."),
    ]
    for c in candidates:
        if (c / "vendas.csv").exists():
            return c
    return BASE_DIR.parent / "data"


DATA_ROOT = get_data_root()
OUTPUT_PATH = BASE_DIR / "process_data.json"


def safe_float(value):
    if pd.isna(value) or np.isinf(value):
        return 0.0
    return float(value)


def safe_int(value):
    if pd.isna(value) or np.isinf(value):
        return 0
    return int(value)


def load_raw_data():
    return {
        "vendas": pd.read_csv(DATA_ROOT / "vendas.csv", parse_dates=["data_pedido"]),
        "clientes": pd.read_csv(DATA_ROOT / "clientes.csv", parse_dates=["data_cadastro", "data_nascimento"]),
        "estoque": pd.read_csv(DATA_ROOT / "estoque.csv", parse_dates=["data_ultima_entrada"]),
        "marketing": pd.read_csv(DATA_ROOT / "marketing.csv", parse_dates=["data_inicio", "data_fim"]),
        "atendimento": pd.read_csv(DATA_ROOT / "atendimento.csv", parse_dates=["data_abertura", "data_fechamento"]),
    }


def prepare_datasets(raw_data):
    vendas = raw_data["vendas"].dropna(subset=["data_pedido"]).copy()
    if vendas.empty:
        raise ValueError("A base vendas.csv não possui registros válidos com data_pedido.")

    # Janela temporal canônica ditada exclusivamente pelo histórico de vendas
    start_date = vendas["data_pedido"].min()
    end_date = vendas["data_pedido"].max()

    window_days = max((end_date - start_date).days + 1, 1)
    window_months = max(window_days / 30.4375, 1.0)
    window_years = max(window_days / 365.25, 1.0 / 12.0)

    # Filtragem restrita de todas as fontes de dados para a janela de vendas [start_date, end_date]
    vendas_filtered = vendas[(vendas["data_pedido"] >= start_date) & (vendas["data_pedido"] <= end_date)].copy()

    marketing = raw_data["marketing"].dropna(subset=["data_inicio"]).copy()
    marketing_filtered = marketing[
        (marketing["data_inicio"] >= start_date) & (marketing["data_inicio"] <= end_date)
    ].copy()

    atendimento = raw_data["atendimento"].dropna(subset=["data_abertura"]).copy()
    atendimento_filtered = atendimento[
        (atendimento["data_abertura"] >= start_date) & (atendimento["data_abertura"] <= end_date)
    ].copy()

    estoque = raw_data["estoque"].dropna(subset=["data_ultima_entrada"]).copy()
    estoque = estoque[
        (estoque["data_ultima_entrada"] >= start_date) & (estoque["data_ultima_entrada"] <= end_date)
    ].copy()

    clientes = raw_data["clientes"].dropna(subset=["data_cadastro"]).copy()
    clientes = clientes[
        (clientes["data_cadastro"] >= start_date) & (clientes["data_cadastro"] <= end_date)
    ].copy()

    return {
        "vendas": vendas_filtered,
        "marketing": marketing_filtered,
        "atendimento": atendimento_filtered,
        "estoque": estoque,
        "clientes": clientes,
        "start_date": start_date,
        "end_date": end_date,
        "window_days": window_days,
        "window_months": window_months,
        "window_years": window_years,
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
    vendas_proc = vendas.copy()
    is_devolvido = vendas_proc["devolvido"].fillna(False).astype(bool)

    vendas_proc["receita_devolvida"] = np.where(is_devolvido, vendas_proc["receita_liquida"], 0.0)
    vendas_proc["frete_reverso"] = np.where(is_devolvido, vendas_proc["custo_frete"], 0.0)
    vendas_proc["receita_perdida"] = vendas_proc["receita_devolvida"] + vendas_proc["frete_reverso"]
    vendas_proc["order_id_devolvido"] = np.where(is_devolvido, vendas_proc["order_id"], np.nan)

    for period in ("semana", "mes", "ano"):
        sales = aggregate_period(vendas_proc, "data_pedido", period)
        ads = aggregate_period(marketing, "data_inicio", period)
        support = aggregate_period(atendimento, "data_abertura", period)

        sales_agg = sales.groupby(period).agg(
            receita_bruta=("receita_bruta", "sum"),
            receita_liquida=("receita_liquida", "sum"),
            receita_perdida=("receita_perdida", "sum"),
            receita_devolvida=("receita_devolvida", "sum"),
            custo_frete_reverso=("frete_reverso", "sum"),
            margem_contribuicao=("margem_contribuicao", "sum"),
            pedidos=("order_id", "nunique"),
            pedidos_devolvidos=("order_id_devolvido", "nunique"),
        )
        sales_agg["ticket_medio"] = np.where(
            sales_agg["pedidos"] > 0, sales_agg["receita_bruta"] / sales_agg["pedidos"], 0.0
        )

        ads_agg = ads.groupby(period).agg(
            investimento_ads=("investimento_reais", "sum"),
            conversoes=("conversoes", "sum"),
            receita_ads=("receita_gerada", "sum"),
        )
        ads_agg["cac"] = np.where(ads_agg["conversoes"] > 0, ads_agg["investimento_ads"] / ads_agg["conversoes"], 0.0)
        ads_agg["roas"] = np.where(ads_agg["investimento_ads"] > 0, ads_agg["receita_ads"] / ads_agg["investimento_ads"], 0.0)

        support_agg = support.groupby(period).agg(
            volume_tickets=("ticket_id", "count"),
            csat_medio=("nota_csat", "mean"),
        )

        # Left join baseado estritamente nos períodos com histórico de vendas
        combined = sales_agg.join(ads_agg, how="left").join(support_agg, how="left").fillna(0.0).reset_index()
        combined = combined.rename(columns={period: "periodo"}).sort_values("periodo")

        result[period] = []
        for row in combined.to_dict("records"):
            normalized = {}
            for key, value in row.items():
                if key in {"pedidos", "pedidos_devolvidos", "conversoes", "volume_tickets"}:
                    normalized[key] = safe_int(value)
                elif isinstance(value, (int, float, np.integer, np.floating)):
                    normalized[key] = safe_float(value)
                else:
                    normalized[key] = value
            result[period].append(normalized)

    return result


def category_health_analysis(vendas, estoque, window_months):
    is_devolvido = vendas["devolvido"].fillna(False).astype(bool)
    vendas_proc = vendas.copy()
    vendas_proc["receita_devolvida"] = np.where(is_devolvido, vendas_proc["receita_liquida"], 0.0)
    vendas_proc["frete_reverso"] = np.where(is_devolvido, vendas_proc["custo_frete"], 0.0)
    vendas_proc["receita_perdida"] = vendas_proc["receita_devolvida"] + vendas_proc["frete_reverso"]

    v_cat = (
        vendas_proc.groupby("categoria")
        .agg(
            receita_bruta=("receita_bruta", "sum"),
            margem_contribuicao=("margem_contribuicao", "sum"),
            pedidos=("order_id", "nunique"),
            quantidade_vendida=("quantidade", "sum"),
            desconto_reais=("desconto_reais", "sum"),
            custo_frete=("custo_frete", "sum"),
            pedidos_margem_neg=("margem_contribuicao", lambda x: (x < 0).sum()),
            pedidos_devolvidos=("devolvido", lambda x: x.fillna(False).sum()),
            receita_perdida=("receita_perdida", "sum"),
            taxa_devolucao=("devolvido", "mean"),
        )
        .reset_index()
    )

    v_cat["margem_pct"] = np.where(v_cat["receita_bruta"] > 0, v_cat["margem_contribuicao"] / v_cat["receita_bruta"], 0.0)
    v_cat["desconto_pct"] = np.where(v_cat["receita_bruta"] > 0, v_cat["desconto_reais"] / v_cat["receita_bruta"], 0.0)
    v_cat["frete_pct"] = np.where(v_cat["receita_bruta"] > 0, v_cat["custo_frete"] / v_cat["receita_bruta"], 0.0)
    v_cat["pct_pedidos_margem_neg"] = np.where(v_cat["pedidos"] > 0, v_cat["pedidos_margem_neg"] / v_cat["pedidos"], 0.0)

    estoque_proc = estoque.copy()
    estoque_proc["valor_estoque_custo"] = estoque_proc["estoque_fisico"] * estoque_proc["custo_unitario"]
    estoque_proc["volume_total_m3"] = estoque_proc["estoque_fisico"] * estoque_proc["volume_m3"]

    e_cat = (
        estoque_proc.groupby("categoria")
        .agg(
            total_skus=("sku_id", "nunique"),
            estoque_fisico=("estoque_fisico", "sum"),
            valor_estoque_custo=("valor_estoque_custo", "sum"),
            volume_total_m3=("volume_total_m3", "sum"),
            skus_ruptura=("status_disponibilidade", lambda x: (x == "Ruptura").sum()),
            skus_critico=("status_disponibilidade", lambda x: (x == "Estoque Crítico").sum()),
            lead_time_medio=("lead_time_reposicao", "mean"),
        )
        .reset_index()
    )

    merged = v_cat.merge(e_cat, on="categoria", how="outer").fillna(0.0)

    # 1. Giro de Estoque na janela temporal de vendas
    merged["giro_estoque"] = np.where(merged["estoque_fisico"] > 0, merged["quantidade_vendida"] / merged["estoque_fisico"], 0.0)
    merged["skus_em_risco"] = merged["skus_ruptura"] + merged["skus_critico"]

    # 2. Venda mensal média baseada na duração real da janela de vendas
    merged["venda_mensal_media"] = np.where(window_months > 0, merged["quantidade_vendida"] / window_months, 0.0)

    # 3. Meses de cobertura de estoque
    merged["meses_cobertura"] = np.where(
        merged["venda_mensal_media"] > 0, merged["estoque_fisico"] / merged["venda_mensal_media"], 0.0
    )

    def definir_acao(row):
        if row["skus_ruptura"] > 10:
            return "Reposição prioritária (Perda ativa de vendas)"
        elif row["giro_estoque"] < 0.05:
            return "Ativar Bundles (Queima de excesso parado)"
        elif row["taxa_devolucao"] > 0.15:
            return "Investigar logística e medidas"
        return "Manter sortimento e cross-sell"

    merged["acao_recomendada"] = merged.apply(definir_acao, axis=1)

    records = merged.to_dict("records")
    for r in records:
        for k, v in r.items():
            if isinstance(v, (np.integer, int)):
                r[k] = safe_int(v)
            elif isinstance(v, (np.floating, float)):
                r[k] = safe_float(round(v, 4))
    return records


def chanel_rfm(vendas, clientes, marketing):
    vendas_efet = vendas[vendas["status_pagamento"] == "Aprovado"].copy()
    vendas_merged = vendas_efet.merge(clientes[["customer_id", "segmento_rfm"]], on="customer_id", how="inner")

    sales = vendas_merged.groupby("canal").agg(
        receita=("receita_liquida", "sum"),
        receita_bruta=("receita_bruta", "sum"),
        receita_liquida=("receita_liquida", "sum"),
        margem_vendas=("margem_contribuicao", "sum"),
        margem_contribuicao=("margem_contribuicao", "sum"),
        pedidos=("order_id", "nunique"),
        pedidos_unico=("quantidade", lambda values: (values == 1).sum()),
        clientes_totais=("customer_id", "nunique"),
        segmento_predominante=("segmento_rfm", lambda x: x.mode()[0] if not x.empty else ""),
    )
    sales["ticket_medio"] = np.where(sales["pedidos"] > 0, sales["receita_bruta"] / sales["pedidos"], 0.0)

    rfm_counts = (
        vendas_merged.groupby(["canal", "segmento_rfm"])["customer_id"]
        .nunique()
        .unstack(fill_value=0)
    )

    ads = marketing.groupby("canal").agg(
        investimento=("investimento_reais", "sum"),
        conversoes_ads=("conversoes", "sum"),
        receita_ads=("receita_gerada", "sum"),
    )

    result = sales.join(rfm_counts).join(ads, how="left").fillna(0.0).reset_index()
    result["margem_liquida_real"] = result["receita_liquida"]
    result["roi_margem"] = np.where(result["investimento"] > 0, result["margem_contribuicao"] / result["investimento"], 0.0)
    result["pct_item_unico"] = np.where(result["pedidos"] > 0, result["pedidos_unico"] / result["pedidos"], 0.0)

    records = result.to_dict("records")
    for r in records:
        for k, v in r.items():
            if isinstance(v, (np.integer, int)):
                r[k] = safe_int(v)
            elif isinstance(v, (np.floating, float)):
                r[k] = safe_float(round(v, 2))
    return records


def shipping_analysis(vendas):
    frete = vendas.groupby("categoria").agg(
        pedidos=("order_id", "nunique"),
        receita_bruta=("receita_bruta", "sum"),
        custo_frete_total=("custo_frete", "sum"),
        frete_medio=("custo_frete", "mean"),
        pedidos_margem_neg=("margem_contribuicao", lambda values: (values < 0).sum()),
        pedidos_frete_gratis=("custo_frete", lambda values: (values == 0).sum()),
    )
    frete["peso_frete_pct"] = np.where(frete["receita_bruta"] > 0, (frete["custo_frete_total"] / frete["receita_bruta"]) * 100, 0.0)
    frete["ticket_medio"] = np.where(frete["pedidos"] > 0, frete["receita_bruta"] / frete["pedidos"], 0.0)

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
    vendas_efet = vendas[vendas["status_pagamento"] == "Aprovado"].copy()
    sales = vendas_efet.groupby("canal").agg(
        receita=("receita_liquida", "sum"),
        receita_bruta=("receita_bruta", "sum"),
        receita_liquida=("receita_liquida", "sum"),
        margem_vendas=("margem_contribuicao", "sum"),
        margem_contribuicao=("margem_contribuicao", "sum"),
        pedidos=("order_id", "nunique"),
        pedidos_unico=("quantidade", lambda values: (values == 1).sum()),
    )
    ads = marketing.groupby("canal").agg(
        investimento=("investimento_reais", "sum"),
        conversoes_ads=("conversoes", "sum"),
        receita_ads=("receita_gerada", "sum"),
    )
    result = sales.join(ads, how="left").fillna(0.0).reset_index()
    result["margem_liquida_real"] = result["receita_liquida"]
    result["roi_margem"] = np.where(result["investimento"] > 0, result["margem_contribuicao"] / result["investimento"], 0.0)
    result["roas"] = np.where(result["investimento"] > 0, result["receita_bruta"] / result["investimento"], 0.0)
    result["cac"] = np.where(result["conversoes_ads"] > 0, result["investimento"] / result["conversoes_ads"], 0.0)
    result["pct_item_unico"] = np.where(result["pedidos"] > 0, result["pedidos_unico"] / result["pedidos"], 0.0)

    records = result.to_dict("records")
    for r in records:
        for k, v in r.items():
            if isinstance(v, (np.integer, int)):
                r[k] = safe_int(v)
            elif isinstance(v, (np.floating, float)):
                r[k] = safe_float(round(v, 2))
    return records


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
    produtos["estoque_disponivel"] = produtos["estoque_disponivel"].fillna(0)
    produtos["status_estoque"] = produtos["status_estoque"].fillna("Sem registro na janela")
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
        0.0,
    )
    sku_profitability = sku_profitability[sku_profitability["receita_bruta"] > 0]
    best_skus = sku_profitability.nlargest(5, "rentabilidade")
    worst_skus = sku_profitability.nsmallest(5, "rentabilidade")
    sku_profitability = pd.concat([best_skus, worst_skus])

    # Filtrar clientes presentes no histórico de vendas analisado
    customer_ids_vendas = set(vendas["customer_id"].unique())
    clientes_ativos = clientes[clientes["customer_id"].isin(customer_ids_vendas)]
    segments = clientes_ativos["segmento_rfm"].value_counts().rename_axis("segmento").reset_index(name="clientes")
    positive_sentiment = (atendimento["nota_csat"] >= 4).mean() if len(atendimento) else 0.0

    # Giro de Estoque = Unidades vendidas na janela / Estoque Físico
    giro_estoque = sales_quantity / stock_quantity if stock_quantity > 0 else 0.0

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
            "roas_consolidado": safe_float(vendas.loc[vendas["status_pagamento"] == "Aprovado", "receita_bruta"].sum() / marketing["investimento_reais"].sum()) if marketing["investimento_reais"].sum() else 0.0,
            "conversoes_totais": safe_int(marketing["conversoes"].sum()),
        },
        "clientes": {
            "ltv_medio": safe_float(clientes_ativos["ltv_acumulado"].mean()),
            "ltv_risco": safe_float(clientes_ativos.loc[clientes_ativos["segmento_rfm"] == "Em Risco", "ltv_acumulado"].sum()),
            "recompra_pct": safe_float((clientes_ativos["total_pedidos_historico"] > 1).mean()),
            "churn_pct": safe_float(clientes_ativos["segmento_rfm"].isin(["Em Risco", "Hibernando"]).mean()),
            "segmentos": segments.to_dict("records"),
        },
        "operacoes": {
            "taxa_devolucao": safe_float(vendas["devolvido"].mean()) if len(vendas) else 0.0,
            "ruptura_pct": safe_float((estoque["status_disponibilidade"] == "Ruptura").mean()),
            "giro_estoque": safe_float(giro_estoque),
            "lead_time_medio": safe_float(estoque["lead_time_reposicao"].mean()),
        },
        "atendimento": {
            "volume_total": safe_int(len(atendimento)),
            "sla_pct": safe_float(resolved / len(atendimento)) if len(atendimento) else 0.0,
            "csat_medio": safe_float(atendimento["nota_csat"].mean()) if len(atendimento) else 0.0,
            "sentimento_positivo_pct": safe_float(positive_sentiment),
            "custo_medio_ticket": safe_float(atendimento["custo_operacional_ticket"].mean()) if len(atendimento) else 0.0,
        },
        "produtividade": {
            "horas_poupadas_chatbot": safe_float((wismo["canal_entrada"] == "ChatBot").sum() * 0.25),
            "potencial_automacao_wismo_pct": safe_float(len(wismo) / len(atendimento)) if len(atendimento) else 0.0,
        },
    }


def build_mode(ctx):
    vendas = ctx["vendas"]
    marketing = ctx["marketing"]
    atendimento = ctx["atendimento"]
    estoque = ctx["estoque"]
    clientes = ctx["clientes"]

    negative = vendas[vendas["margem_contribuicao"] < 0]
    h3 = negative.groupby("categoria").agg(
        receita_bruta=("receita_bruta", "sum"), custo_frete=("custo_frete", "sum"), desconto=("desconto_reais", "sum")
    ).reset_index()
    h3["peso_frete_pct"] = np.where(h3["receita_bruta"] > 0, h3["custo_frete"] / h3["receita_bruta"], 0.0)
    h3["peso_desconto_pct"] = np.where(h3["receita_bruta"] > 0, h3["desconto"] / h3["receita_bruta"], 0.0)

    produtos, excess, bundles = stock_and_bundles(vendas, estoque)
    wismo = atendimento[atendimento["categoria_problema"] == "Onde está meu pedido?"]
    devolvidos = vendas[vendas["devolvido"].fillna(False)]

    wismo_saving = len(wismo) * 0.75 * (12.0 - 1.5)
    frete_critico = vendas[
        (vendas["quantidade"] == 1)
        & (vendas["receita_bruta"] < 199)
        & (vendas["custo_frete"] > vendas["margem_contribuicao"])
    ]
    marketing_reallocation = marketing["investimento_reais"].sum() * 0.30 * 0.05
    bundle_capital = estoque.loc[
        (estoque["categoria"] == "Moda") & (estoque["estoque_disponivel"] > 1000),
        "estoque_disponivel",
    ].mul(
        estoque.loc[
            (estoque["categoria"] == "Moda") & (estoque["estoque_disponivel"] > 1000),
            "custo_unitario",
        ]
    ).sum()
    returned_margin = vendas.loc[vendas["devolvido"].fillna(False), "margem_contribuicao"].sum()
    frete_saving = frete_critico["custo_frete"].sum()
    bundle_monthly_release = bundle_capital * 0.20 / 3
    returns_saving = returned_margin * 0.10
    impact_actions = [
        {
            "nome": "Automação WISMO",
            "valor": safe_float(wismo_saving),
            "investimento": 30000.0,
            "beneficio_mensal": safe_float(wismo_saving / ctx["window_months"]),
            "payback_meses": safe_float(30000 / (wismo_saving / ctx["window_months"])) if wismo_saving else 0.0,
        },
        {
            "nome": "Política de Frete",
            "valor": safe_float(frete_saving),
            "investimento": 12000.0,
            "beneficio_mensal": safe_float(frete_saving / ctx["window_months"]),
            "payback_meses": safe_float(12000 / (frete_saving / ctx["window_months"])) if frete_saving else 0.0,
        },
        {
            "nome": "Realocação Marketing",
            "valor": safe_float(marketing_reallocation),
            "investimento": 25000.0,
            "beneficio_mensal": safe_float(marketing_reallocation / ctx["window_months"]),
            "payback_meses": safe_float(25000 / (marketing_reallocation / ctx["window_months"])) if marketing_reallocation else 0.0,
        },
        {
            "nome": "Capital em Bundles",
            "valor": safe_float(bundle_capital),
            "investimento": 18000.0,
            "beneficio_mensal": safe_float(bundle_monthly_release),
            "payback_meses": safe_float(18000 / bundle_monthly_release) if bundle_monthly_release else 0.0,
        },
        {
            "nome": "Redução Devoluções",
            "valor": safe_float(returns_saving),
            "investimento": 45000.0,
            "beneficio_mensal": safe_float(returns_saving / ctx["window_months"]),
            "payback_meses": safe_float(45000 / (returns_saving / ctx["window_months"])) if returns_saving else 0.0,
        },
    ]
    impact_total = sum(action["valor"] for action in impact_actions)

    return {
        "kpis": build_kpis(vendas, clientes, estoque, marketing, atendimento),
        "temporal": temporal_series(vendas, marketing, atendimento),
        "canais": channel_analysis(vendas, marketing),
        "analise_frete": shipping_analysis(vendas),
        "canais_rfm": chanel_rfm(vendas, clientes, marketing),
        "saude_categorias": category_health_analysis(vendas, estoque, ctx["window_months"]),
        "hipoteses": {
            "margem_negativa_h3": h3.to_dict("records"),
            "pedidos_margem_negativa": safe_int(len(negative)),
            "sobre_estoque_h4": excess,
            "bundles_sugeridos": bundles,
            "atendimento_h5_h6": {
                "taxa_devolucao_pct": safe_float(vendas["devolvido"].mean()) if len(vendas) else 0.0,
                "margem_perdida": safe_float(vendas.loc[vendas["devolvido"].fillna(False), "margem_contribuicao"].sum()),
                "wismo_qtd": safe_int(len(wismo)),
                "wismo_custo": safe_float(wismo.loc[wismo["canal_entrada"] != "ChatBot", "custo_operacional_ticket"].sum()),
            },
        },
        "impacto": {
            "recuperacao_ebitda": impact_total,
            "economia_estimada": impact_total,
            "receita_protegida": safe_float(devolvidos["receita_bruta"].sum()),
            "payback_meses": impact_actions[0]["payback_meses"],
            "acoes": impact_actions,
        },
        "produtos_ordenados": produtos,
        "rfm": clientes["segmento_rfm"].value_counts().rename_axis("segmento").reset_index(name="quantidade").to_dict("records"),
        "vendas_iniciadas_em": ctx["start_date"].strftime("%Y-%m-%d"),
        "vendas_encerradas_em": ctx["end_date"].strftime("%Y-%m-%d"),
        "janela_dias": ctx["window_days"],
        "janela_meses": safe_float(round(ctx["window_months"], 2)),
    }


def build_periodic_reports(ctx):
    vendas = ctx["vendas"].copy()
    marketing = ctx["marketing"].copy()
    atendimento = ctx["atendimento"].copy()

    is_dev = vendas["devolvido"].fillna(False).astype(bool)
    vendas["receita_devolvida"] = np.where(is_dev, vendas["receita_liquida"], 0.0)
    vendas["frete_reverso"] = np.where(is_dev, vendas["custo_frete"], 0.0)
    vendas["receita_perdida"] = vendas["receita_devolvida"] + vendas["frete_reverso"]

    reports = {}
    for period_type, dt_col in [("mes", "%Y-%m"), ("semana", "%Y-W%W")]:
        vendas["p"] = vendas["data_pedido"].dt.strftime(dt_col)
        marketing["p"] = marketing["data_inicio"].dt.strftime(dt_col)
        atendimento["p"] = atendimento["data_abertura"].dt.strftime(dt_col)

        periods_sorted = sorted(vendas["p"].dropna().unique())

        s_agg = vendas.groupby("p").agg(
            receita_bruta=("receita_bruta", "sum"),
            receita_liquida=("receita_liquida", "sum"),
            desconto_reais=("desconto_reais", "sum"),
            custo_frete=("custo_frete", "sum"),
            custo_produto=("custo_produto", "sum"),
            margem_contribuicao=("margem_contribuicao", "sum"),
            pedidos=("order_id", "nunique"),
            pedidos_devolvidos=("devolvido", lambda x: x.fillna(False).sum()),
            receita_perdida=("receita_perdida", "sum"),
        )
        s_agg["ticket_medio"] = np.where(s_agg["pedidos"] > 0, s_agg["receita_bruta"] / s_agg["pedidos"], 0.0)
        s_agg["margem_pct"] = np.where(s_agg["receita_bruta"] > 0, s_agg["margem_contribuicao"] / s_agg["receita_bruta"], 0.0)
        s_agg["taxa_devolucao"] = np.where(s_agg["pedidos"] > 0, s_agg["pedidos_devolvidos"] / s_agg["pedidos"], 0.0)

        m_agg = marketing.groupby("p").agg(
            investimento=("investimento_reais", "sum"),
            conversoes=("conversoes", "sum"),
            receita_ads=("receita_gerada", "sum"),
        )
        m_agg["cac"] = np.where(m_agg["conversoes"] > 0, m_agg["investimento"] / m_agg["conversoes"], 0.0)
        m_agg["roas"] = np.where(m_agg["investimento"] > 0, m_agg["receita_ads"] / m_agg["investimento"], 0.0)

        a_agg = atendimento.groupby("p").agg(
            tickets=("ticket_id", "count"),
            csat_medio=("nota_csat", "mean"),
            tempo_resposta_min=("tempo_primeira_resposta_minutos", "mean"),
        )

        comb = s_agg.join(m_agg, how="left").join(a_agg, how="left").fillna(0.0)
        period_data = {}

        for i, p_cur in enumerate(periods_sorted):
            cur = comb.loc[p_cur] if p_cur in comb.index else None
            if cur is None:
                continue
            prev = comb.loc[periods_sorted[i - 1]] if i > 0 and periods_sorted[i - 1] in comb.index else None

            def delta(k, is_pts=False):
                if prev is None:
                    return 0.0
                c_val = float(cur.get(k, 0.0))
                p_val = float(prev.get(k, 0.0))
                if is_pts:
                    return round(c_val - p_val, 4)
                return round((c_val - p_val) / abs(p_val), 4) if p_val != 0 else 0.0

            v_p = vendas[vendas["p"] == p_cur]
            cat_p = v_p.groupby("categoria").agg(
                receita_bruta=("receita_bruta", "sum"),
                margem_contribuicao=("margem_contribuicao", "sum"),
                quantidade=("quantidade", "sum"),
                pedidos=("order_id", "nunique"),
            ).reset_index()
            cat_p["margem_pct"] = np.where(cat_p["receita_bruta"] > 0, cat_p["margem_contribuicao"] / cat_p["receita_bruta"], 0.0)
            cat_list = cat_p.sort_values("receita_bruta", ascending=False).to_dict("records")
            for r in cat_list:
                for k, val in r.items():
                    if isinstance(val, (float, np.floating)):
                        r[k] = round(float(val), 2)

            m_p = marketing[marketing["p"] == p_cur]
            v_p_chan = v_p[v_p["status_pagamento"] == "Aprovado"].groupby("canal").agg(receita_bruta=("receita_bruta", "sum")).reset_index()
            chan_p = m_p.groupby("canal").agg(
                investimento=("investimento_reais", "sum"),
                receita_ads=("receita_gerada", "sum"),
                conversoes=("conversoes", "sum"),
            ).reset_index()
            chan_merged = pd.merge(v_p_chan, chan_p, on="canal", how="outer").fillna(0.0)
            chan_merged["roas"] = np.where(chan_merged["investimento"] > 0, chan_merged["receita_bruta"] / chan_merged["investimento"], 0.0)
            chan_merged["cac"] = np.where(chan_merged["conversoes"] > 0, chan_merged["investimento"] / chan_merged["conversoes"], 0.0)
            chan_list = chan_merged.to_dict("records")
            for r in chan_list:
                for k, val in r.items():
                    if isinstance(val, (float, np.floating)):
                        r[k] = round(float(val), 2)

            top_skus = v_p.groupby(["sku_id", "produto"]).agg(
                receita_bruta=("receita_bruta", "sum"),
                margem_contribuicao=("margem_contribuicao", "sum"),
                quantidade=("quantidade", "sum"),
            ).reset_index()
            top_skus["margem_pct"] = np.where(top_skus["receita_bruta"] > 0, top_skus["margem_contribuicao"] / top_skus["receita_bruta"], 0.0)
            best_rev = top_skus.sort_values("receita_bruta", ascending=False).head(5).to_dict("records")
            worst_margin = top_skus.sort_values("margem_pct", ascending=True).head(5).to_dict("records")
            for lst in [best_rev, worst_margin]:
                for r in lst:
                    for k, val in r.items():
                        if isinstance(val, (float, np.floating)):
                            r[k] = round(float(val), 2)

            period_data[p_cur] = {
                "periodo": p_cur,
                "periodo_anterior": periods_sorted[i - 1] if i > 0 else None,
                "kpis": {
                    "receita_bruta": {"val": round(float(cur["receita_bruta"]), 2), "delta_pct": delta("receita_bruta")},
                    "receita_liquida": {"val": round(float(cur["receita_liquida"]), 2), "delta_pct": delta("receita_liquida")},
                    "margem_contribuicao": {"val": round(float(cur["margem_contribuicao"]), 2), "delta_pct": delta("margem_contribuicao")},
                    "margem_pct": {"val": round(float(cur["margem_pct"]), 4), "delta_pts": delta("margem_pct", is_pts=True)},
                    "pedidos": {"val": int(cur["pedidos"]), "delta_pct": delta("pedidos")},
                    "ticket_medio": {"val": round(float(cur["ticket_medio"]), 2), "delta_pct": delta("ticket_medio")},
                    "investimento_marketing": {"val": round(float(cur["investimento"]), 2), "delta_pct": delta("investimento")},
                    "cac": {"val": round(float(cur["cac"]), 2), "delta_pct": delta("cac")},
                    "roas": {"val": round(float(cur["roas"]), 2), "delta_pct": delta("roas")},
                    "taxa_devolucao": {"val": round(float(cur["taxa_devolucao"]), 4), "delta_pts": delta("taxa_devolucao", is_pts=True)},
                    "receita_perdida": {"val": round(float(cur["receita_perdida"]), 2), "delta_pct": delta("receita_perdida")},
                    "volume_tickets": {"val": int(cur["tickets"]), "delta_pct": delta("tickets")},
                    "csat_medio": {"val": round(float(cur["csat_medio"]), 2), "delta_pts": delta("csat_medio", is_pts=True)},
                },
                "dre_operacional": {
                    "receita_bruta": round(float(cur["receita_bruta"]), 2),
                    "descontos": round(float(cur["desconto_reais"]), 2),
                    "receita_liquida": round(float(cur["receita_liquida"]), 2),
                    "custo_mercadoria": round(float(cur["custo_produto"]), 2),
                    "custo_frete": round(float(cur["custo_frete"]), 2),
                    "perda_devolucoes": round(float(cur["receita_perdida"]), 2),
                    "margem_contribuicao": round(float(cur["margem_contribuicao"]), 2),
                    "margem_contribuicao_pct": round(float(cur["margem_pct"]), 4),
                },
                "categorias": cat_list,
                "canais": chan_list,
                "destaques_skus": {
                    "top_receita": best_rev,
                    "menor_margem": worst_margin,
                },
            }

        reports[period_type] = {
            "periodos_disponiveis": periods_sorted,
            "dados": period_data,
        }

    return reports


def process_data():
    raw_data = load_raw_data()
    ctx = prepare_datasets(raw_data)

    dashboard_data = {
        "meta": {
            "atualizado_em": pd.Timestamp.now().isoformat(),
            "fonte": "CSV + Pandas",
            "janela_vendas_inicio": ctx["start_date"].isoformat(),
            "janela_vendas_fim": ctx["end_date"].isoformat(),
            "dias_totais": ctx["window_days"],
        },
        "modo_integrado": build_mode(ctx),
        "relatorios": build_periodic_reports(ctx),
    }

    with OUTPUT_PATH.open("w", encoding="utf-8") as output:
        json.dump(dashboard_data, output, ensure_ascii=False, indent=2, allow_nan=False)

    print(f"[OK] Dados sincronizados com sucesso na janela de vendas ({ctx['start_date'].strftime('%Y-%m-%d')} a {ctx['end_date'].strftime('%Y-%m-%d')}): {OUTPUT_PATH}")


if __name__ == "__main__":
    process_data()