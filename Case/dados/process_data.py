# -*- coding: utf-8 -*-
import json
from pathlib import Path
from datetime import datetime, date
import numpy as np
import pandas as pd

# ============================================================
# Resolução de diretórios
# ============================================================
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

# ============================================================
# Funções utilitárias
# ============================================================
def safe_float(value):
    try:
        if value is None:
            return 0.0
        if isinstance(value, (bool, np.bool_)):
            return float(value)
        if pd.isna(value):
            return 0.0
        f = float(value)
        if np.isinf(f) or np.isnan(f):
            return 0.0
        return f
    except Exception:
        return 0.0

def safe_int(value):
    try:
        if value is None:
            return 0
        if isinstance(value, (bool, np.bool_)):
            return int(value)
        if pd.isna(value):
            return 0
        f = float(value)
        if np.isinf(f) or np.isnan(f):
            return 0
        return int(f)
    except Exception:
        return 0

def sanitize(obj):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return sanitize(obj.tolist())
    if isinstance(obj, (np.integer, int)):
        return safe_int(obj)
    if isinstance(obj, (np.floating, float)):
        return safe_float(obj)
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (pd.Timestamp, datetime, date)):
        return obj.isoformat()
    return obj

def ensure_col(df, col, default=0.0):
    if col in df.columns:
        return df[col]
    return pd.Series(default, index=df.index)

# ============================================================
# Carga dos dados
# ============================================================
def load_raw_data():
    return {
        "vendas": pd.read_csv(DATA_ROOT / "vendas.csv", parse_dates=["data_pedido"]),
        "clientes": pd.read_csv(DATA_ROOT / "clientes.csv", parse_dates=["data_cadastro", "data_nascimento"]),
        "estoque": pd.read_csv(DATA_ROOT / "estoque.csv", parse_dates=["data_ultima_entrada"]),
        "marketing": pd.read_csv(DATA_ROOT / "marketing.csv", parse_dates=["data_inicio", "data_fim"]),
        "atendimento": pd.read_csv(DATA_ROOT / "atendimento.csv", parse_dates=["data_abertura", "data_fechamento"]),
    }

# ============================================================
# Janela temporal canônica
# ============================================================
def prepare_datasets(raw_data):
    vendas = raw_data["vendas"].dropna(subset=["data_pedido"]).copy()
    if vendas.empty:
        raise ValueError("A base vendas.csv não possui registros válidos com data_pedido.")

    # Janela canônica definida exclusivamente por vendas
    start_date = vendas["data_pedido"].min()
    end_date = vendas["data_pedido"].max()
    window_days = max((end_date - start_date).days + 1, 1)
    window_months = max(window_days / 30.4375, 1.0)
    window_years = max(window_days / 365.25, 1.0 / 12.0)

    # Vendas dentro da janela
    vendas = vendas[(vendas["data_pedido"] >= start_date) & (vendas["data_pedido"] <= end_date)].copy()
    if "devolvido" in vendas.columns:
        vendas["is_devolvido"] = vendas["devolvido"].fillna(False).astype(bool)
    else:
        vendas["is_devolvido"] = False

    # Clientes: somente cadastrados até o fim da janela de vendas
    clientes = raw_data["clientes"].copy()
    if "data_cadastro" in clientes.columns:
        clientes = clientes[clientes["data_cadastro"] <= end_date].copy()

    # Estoque: somente entradas até o fim da janela de vendas
    estoque = raw_data["estoque"].copy()
    if "data_ultima_entrada" in estoque.columns:
        estoque = estoque[estoque["data_ultima_entrada"] <= end_date].copy()

    # Marketing: campanhas iniciadas dentro da janela e encerradas até o fim dela
    marketing = raw_data["marketing"].copy()
    if {"data_inicio", "data_fim"}.issubset(marketing.columns):
        marketing = marketing[
            (marketing["data_inicio"] >= start_date) &
            (marketing["data_fim"] <= end_date)
        ].copy()

    # Atendimento: chamados abertos dentro da janela e fechados até o fim dela
    atendimento = raw_data["atendimento"].copy()
    if {"data_abertura", "data_fechamento"}.issubset(atendimento.columns):
        atendimento = atendimento[
            (atendimento["data_abertura"] >= start_date) &
            (atendimento["data_fechamento"] <= end_date)
        ].copy()

    return {
        "vendas": vendas,
        "clientes": clientes,
        "estoque": estoque,
        "marketing": marketing,
        "atendimento": atendimento,
        "start_date": start_date,
        "end_date": end_date,
        "window_days": window_days,
        "window_months": window_months,
        "window_years": window_years,
    }

# ============================================================
# Séries temporais
# ============================================================
def aggregate_period(source, date_column, period):
    frame = source.copy()
    if date_column not in frame.columns:
        frame = frame.iloc[0:0].copy()
        frame["periodo"] = pd.Series(dtype=object)
        return frame

    frame = frame[frame[date_column].notna()].copy()
    if frame.empty:
        frame["periodo"] = pd.Series(dtype=object)
        return frame

    if period == "semana":
        frame["periodo"] = frame[date_column].dt.strftime("%Y-W%W")
    elif period == "mes":
        frame["periodo"] = frame[date_column].dt.strftime("%Y-%m")
    else:
        frame["periodo"] = frame[date_column].dt.strftime("%Y")

    return frame

def temporal_series(vendas, marketing, atendimento):
    result = {}
    vendas_proc = vendas.copy()

    if "is_devolvido" not in vendas_proc.columns:
        vendas_proc["is_devolvido"] = False

    receita_liquida = ensure_col(vendas_proc, "receita_liquida", 0.0)
    custo_frete = ensure_col(vendas_proc, "custo_frete", 0.0)

    vendas_proc["receita_devolvida"] = np.where(vendas_proc["is_devolvido"], receita_liquida, 0.0)
    vendas_proc["frete_reverso"] = np.where(vendas_proc["is_devolvido"], custo_frete, 0.0)
    vendas_proc["receita_perdida"] = vendas_proc["receita_devolvida"] + vendas_proc["frete_reverso"]

    if "order_id" in vendas_proc.columns:
        vendas_proc["order_id_devolvido"] = np.where(vendas_proc["is_devolvido"], vendas_proc["order_id"], np.nan)
    else:
        vendas_proc["order_id_devolvido"] = np.nan

    marketing_date = "data_fim" if "data_fim" in marketing.columns else "data_inicio"
    atendimento_date = "data_fechamento" if "data_fechamento" in atendimento.columns else "data_abertura"

    for period in ("semana", "mes", "ano"):
        sales = aggregate_period(vendas_proc, "data_pedido", period)
        ads = aggregate_period(marketing, marketing_date, period)
        support = aggregate_period(atendimento, atendimento_date, period)

        if sales.empty:
            sales_agg = pd.DataFrame(index=pd.Index([], name="periodo"))
        else:
            sales_agg = sales.groupby("periodo").agg(
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
                sales_agg["pedidos"] > 0,
                sales_agg["receita_bruta"] / sales_agg["pedidos"],
                0.0
            )

        if ads.empty:
            ads_agg = pd.DataFrame(
                columns=["investimento_ads", "conversoes", "receita_ads", "cac", "roas"],
                index=pd.Index([], name="periodo")
            )
        else:
            ads_agg = ads.groupby("periodo").agg(
                investimento_ads=("investimento_reais", "sum"),
                conversoes=("conversoes", "sum"),
                receita_ads=("receita_gerada", "sum"),
            )
            ads_agg["cac"] = np.where(ads_agg["conversoes"] > 0, ads_agg["investimento_ads"] / ads_agg["conversoes"], 0.0)
            ads_agg["roas"] = np.where(ads_agg["investimento_ads"] > 0, ads_agg["receita_ads"] / ads_agg["investimento_ads"], 0.0)

        if support.empty:
            support_agg = pd.DataFrame(
                columns=["volume_tickets", "csat_medio"],
                index=pd.Index([], name="periodo")
            )
        else:
            support_agg = support.groupby("periodo").agg(
                volume_tickets=("ticket_id", "count"),
                csat_medio=("nota_csat", "mean"),
            )

        combined = sales_agg.join(ads_agg, how="left").join(support_agg, how="left").fillna(0.0).reset_index()
        combined = combined.rename(columns={"index": "periodo"}) if "periodo" not in combined.columns else combined
        combined = combined.sort_values("periodo")

        records = []
        int_keys = {"pedidos", "pedidos_devolvidos", "conversoes", "volume_tickets"}
        for row in combined.to_dict("records"):
            normalized = {}
            for key, value in row.items():
                if key in int_keys:
                    normalized[key] = safe_int(value)
                elif isinstance(value, (int, float, np.integer, np.floating)):
                    normalized[key] = safe_float(value)
                else:
                    normalized[key] = value
            records.append(normalized)

        result[period] = records

    return result

# ============================================================
# Saúde por categoria
# ============================================================
def category_health_analysis(vendas, estoque, window_months):
    v = vendas.copy()
    if "is_devolvido" not in v.columns:
        v["is_devolvido"] = False
    if "categoria" not in v.columns:
        v["categoria"] = "Sem categoria"
    v["categoria"] = v["categoria"].fillna("Sem categoria")

    receita_liquida = ensure_col(v, "receita_liquida", 0.0)
    custo_frete = ensure_col(v, "custo_frete", 0.0)

    v["receita_devolvida"] = np.where(v["is_devolvido"], receita_liquida, 0.0)
    v["frete_reverso"] = np.where(v["is_devolvido"], custo_frete, 0.0)
    v["receita_perdida"] = v["receita_devolvida"] + v["frete_reverso"]

    v_cat = (
        v.groupby("categoria")
        .agg(
            receita_bruta=("receita_bruta", "sum"),
            margem_contribuicao=("margem_contribuicao", "sum"),
            pedidos=("order_id", "nunique"),
            quantidade_vendida=("quantidade", "sum"),
            desconto_reais=("desconto_reais", "sum"),
            custo_frete=("custo_frete", "sum"),
            pedidos_margem_neg=("margem_contribuicao", lambda x: (x < 0).sum()),
            pedidos_devolvidos=("is_devolvido", "sum"),
            receita_perdida=("receita_perdida", "sum"),
            taxa_devolucao=("is_devolvido", "mean"),
        )
        .reset_index()
    )

    v_cat["margem_pct"] = np.where(v_cat["receita_bruta"] > 0, v_cat["margem_contribuicao"] / v_cat["receita_bruta"], 0.0)
    v_cat["desconto_pct"] = np.where(v_cat["receita_bruta"] > 0, v_cat["desconto_reais"] / v_cat["receita_bruta"], 0.0)
    v_cat["frete_pct"] = np.where(v_cat["receita_bruta"] > 0, v_cat["custo_frete"] / v_cat["receita_bruta"], 0.0)
    v_cat["pct_pedidos_margem_neg"] = np.where(v_cat["pedidos"] > 0, v_cat["pedidos_margem_neg"] / v_cat["pedidos"], 0.0)

    e = estoque.copy()
    if "categoria" not in e.columns:
        e["categoria"] = "Sem categoria"
    e["categoria"] = e["categoria"].fillna("Sem categoria")

    e["estoque_fisico"] = ensure_col(e, "estoque_fisico", 0.0)
    e["custo_unitario"] = ensure_col(e, "custo_unitario", 0.0)
    e["volume_m3"] = ensure_col(e, "volume_m3", 0.0)
    e["lead_time_reposicao"] = ensure_col(e, "lead_time_reposicao", 0.0)

    e["valor_estoque_custo"] = e["estoque_fisico"] * e["custo_unitario"]
    e["volume_total_m3"] = e["estoque_fisico"] * e["volume_m3"]

    if "status_disponibilidade" in e.columns:
        e["is_ruptura"] = e["status_disponibilidade"] == "Ruptura"
        e["is_critico"] = e["status_disponibilidade"] == "Estoque Crítico"
    else:
        e["is_ruptura"] = False
        e["is_critico"] = False

    e_cat = (
        e.groupby("categoria")
        .agg(
            total_skus=("sku_id", "nunique"),
            estoque_fisico=("estoque_fisico", "sum"),
            valor_estoque_custo=("valor_estoque_custo", "sum"),
            volume_total_m3=("volume_total_m3", "sum"),
            skus_ruptura=("is_ruptura", "sum"),
            skus_critico=("is_critico", "sum"),
            lead_time_medio=("lead_time_reposicao", "mean"),
        )
        .reset_index()
    )

    merged = v_cat.merge(e_cat, on="categoria", how="outer").fillna(0.0)
    merged["giro_estoque"] = np.where(merged["estoque_fisico"] > 0, merged["quantidade_vendida"] / merged["estoque_fisico"], 0.0)
    merged["skus_em_risco"] = merged["skus_ruptura"] + merged["skus_critico"]
    merged["venda_mensal_media"] = np.where(window_months > 0, merged["quantidade_vendida"] / window_months, 0.0)
    merged["meses_cobertura"] = np.where(merged["venda_mensal_media"] > 0, merged["estoque_fisico"] / merged["venda_mensal_media"], 0.0)

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
        for k, val in r.items():
            if isinstance(val, (np.integer, int)):
                r[k] = safe_int(val)
            elif isinstance(val, (np.floating, float)):
                r[k] = safe_float(round(val, 4))
    return records

# ============================================================
# Canais + RFM
# ============================================================
def chanel_rfm(vendas, clientes, marketing):
    if "status_pagamento" in vendas.columns:
        vendas_efet = vendas[vendas["status_pagamento"] == "Aprovado"].copy()
    else:
        vendas_efet = vendas.copy()

    if "canal" not in vendas_efet.columns:
        vendas_efet["canal"] = "Sem canal"

    if "customer_id" in vendas_efet.columns and "customer_id" in clientes.columns:
        vendas_merged = vendas_efet.merge(
            clientes[["customer_id", "segmento_rfm"]],
            on="customer_id",
            how="left"
        )
    else:
        vendas_merged = vendas_efet.copy()
        vendas_merged["segmento_rfm"] = "Sem segmento"

    vendas_merged["segmento_rfm"] = vendas_merged["segmento_rfm"].fillna("Sem segmento")

    sales = vendas_merged.groupby("canal").agg(
        receita=("receita_liquida", "sum"),
        receita_bruta=("receita_bruta", "sum"),
        receita_liquida=("receita_liquida", "sum"),
        margem_vendas=("margem_contribuicao", "sum"),
        margem_contribuicao=("margem_contribuicao", "sum"),
        pedidos=("order_id", "nunique"),
        pedidos_unico=("quantidade", lambda values: (values == 1).sum()),
        clientes_totais=("customer_id", "nunique"),
        segmento_predominante=("segmento_rfm", lambda x: x.mode()[0] if not x.mode().empty else ""),
    )
    sales["ticket_medio"] = np.where(sales["pedidos"] > 0, sales["receita_bruta"] / sales["pedidos"], 0.0)

    rfm_counts = (
        vendas_merged.groupby(["canal", "segmento_rfm"])["customer_id"]
        .nunique()
        .unstack(fill_value=0)
    )

    if marketing.empty or "canal" not in marketing.columns:
        ads = pd.DataFrame(
            columns=["investimento", "conversoes_ads", "receita_ads"],
            index=pd.Index([], name="canal")
        )
    else:
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
        for k, val in r.items():
            if isinstance(val, (np.integer, int)):
                r[k] = safe_int(val)
            elif isinstance(val, (np.floating, float)):
                r[k] = safe_float(round(val, 2))
    return records

# ============================================================
# Frete por categoria
# ============================================================
def shipping_analysis(vendas):
    if "categoria" not in vendas.columns:
        vendas = vendas.copy()
        vendas["categoria"] = "Sem categoria"

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
        for k, val in r.items():
            if isinstance(val, (np.integer, int)):
                r[k] = safe_int(val)
            elif isinstance(val, (np.floating, float)):
                r[k] = safe_float(round(val, 2))
    return records

# ============================================================
# Canais
# ============================================================
def channel_analysis(vendas, marketing):
    if "status_pagamento" in vendas.columns:
        vendas_efet = vendas[vendas["status_pagamento"] == "Aprovado"].copy()
    else:
        vendas_efet = vendas.copy()

    if "canal" not in vendas_efet.columns:
        vendas_efet["canal"] = "Sem canal"

    sales = vendas_efet.groupby("canal").agg(
        receita=("receita_liquida", "sum"),
        receita_bruta=("receita_bruta", "sum"),
        receita_liquida=("receita_liquida", "sum"),
        margem_vendas=("margem_contribuicao", "sum"),
        margem_contribuicao=("margem_contribuicao", "sum"),
        pedidos=("order_id", "nunique"),
        pedidos_unico=("quantidade", lambda values: (values == 1).sum()),
    )

    if marketing.empty or "canal" not in marketing.columns:
        ads = pd.DataFrame(
            columns=["investimento", "conversoes_ads", "receita_ads"],
            index=pd.Index([], name="canal")
        )
    else:
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
        for k, val in r.items():
            if isinstance(val, (np.integer, int)):
                r[k] = safe_int(val)
            elif isinstance(val, (np.floating, float)):
                r[k] = safe_float(round(val, 2))
    return records

# ============================================================
# Estoque e bundles
# ============================================================
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

    produtos = produtos.sort_values(["rentabilidade", "faturamento"], ascending=[False, False])

    if {"sku_id", "estoque_disponivel", "status_disponibilidade"}.issubset(estoque.columns):
        produtos = produtos.merge(
            estoque[["sku_id", "estoque_disponivel", "status_disponibilidade"]],
            on="sku_id",
            how="left"
        ).rename(columns={"status_disponibilidade": "status_estoque"})
    else:
        produtos["estoque_disponivel"] = 0
        produtos["status_estoque"] = "Sem registro na janela"

    produtos["estoque_disponivel"] = produtos["estoque_disponivel"].fillna(0)
    produtos["status_estoque"] = produtos["status_estoque"].fillna("Sem registro na janela")

    if {"categoria", "estoque_disponivel"}.issubset(estoque.columns):
        moda_excesso = estoque[(estoque["categoria"] == "Moda") & (estoque["estoque_disponivel"] > 1000)].copy()
    else:
        moda_excesso = pd.DataFrame(columns=estoque.columns)

    if {"categoria", "preco_venda_sugerido"}.issubset(estoque.columns):
        companion = estoque[estoque["categoria"].isin(["Beleza", "Lifestyle"])].nlargest(5, "preco_venda_sugerido")
    else:
        companion = pd.DataFrame(columns=estoque.columns)

    bundles = []
    if not moda_excesso.empty and not companion.empty:
        for _, fashion in moda_excesso.nlargest(5, "estoque_disponivel").iterrows():
            product = companion.iloc[0]
            bundles.append({
                "sku_moda": fashion.get("sku_id", ""),
                "produto_moda": fashion.get("nome_produto", ""),
                "estoque_moda": safe_int(fashion.get("estoque_disponivel", 0)),
                "sku_companion": product.get("sku_id", ""),
                "produto_companion": product.get("nome_produto", ""),
                "categoria_companion": product.get("categoria", ""),
                "racional": "Bundle cross-category para elevar a densidade do carrinho",
            })

    excess = []
    if not moda_excesso.empty:
        excess = moda_excesso[["sku_id", "nome_produto", "estoque_disponivel"]].to_dict("records")

    return produtos.to_dict("records"), excess, bundles

# ============================================================
# KPIs principais
# ============================================================
def build_kpis(vendas, clientes, estoque, marketing, atendimento):
    vendas = vendas.copy()

    if "receita_bruta" not in vendas.columns:
        vendas["receita_bruta"] = 0.0
    if "is_devolvido" not in vendas.columns:
        vendas["is_devolvido"] = False

    receita = vendas["receita_bruta"].sum()
    pedidos_totais = vendas["order_id"].nunique() if "order_id" in vendas.columns else len(vendas)

    if "status_pagamento" in vendas.columns and "order_id" in vendas.columns:
        aprovados = vendas.loc[vendas["status_pagamento"] == "Aprovado", "order_id"].nunique()
    else:
        aprovados = pedidos_totais

    wismo = atendimento.iloc[0:0]
    if len(atendimento) and "categoria_problema" in atendimento.columns:
        wismo = atendimento[atendimento["categoria_problema"] == "Onde está meu pedido?"]

    sales_quantity = vendas["quantidade"].sum() if "quantidade" in vendas.columns else 0
    stock_quantity = estoque["estoque_fisico"].sum() if "estoque_fisico" in estoque.columns else 0

    resolved = 0
    if len(atendimento) and "status_atendimento" in atendimento.columns:
        resolved = (atendimento["status_atendimento"] == "Resolvido").sum()

    # Comercial
    conversoes = marketing["conversoes"].sum() if "conversoes" in marketing.columns else 0
    cliques = marketing["cliques"].sum() if "cliques" in marketing.columns else 0
    if cliques == 0 and conversoes > 0:
        cliques = conversoes * 50
    taxa_conversao_decimal = conversoes / cliques if cliques else 0.0

    # Margem
    margem_contribuicao = vendas["margem_contribuicao"].sum() if "margem_contribuicao" in vendas.columns else 0.0
    desconto_total = vendas["desconto_reais"].sum() if "desconto_reais" in vendas.columns else 0.0
    frete_medio = vendas["custo_frete"].mean() if "custo_frete" in vendas.columns else 0.0

    sku_sel = pd.DataFrame(columns=["sku_id", "produto", "receita_bruta", "margem_contribuicao", "rentabilidade"])
    if {"sku_id", "produto", "receita_bruta", "margem_contribuicao"}.issubset(vendas.columns):
        sku_profitability = (
            vendas.groupby(["sku_id", "produto"])
            .agg(receita_bruta=("receita_bruta", "sum"), margem_contribuicao=("margem_contribuicao", "sum"))
            .reset_index()
        )
        sku_profitability = sku_profitability[sku_profitability["receita_bruta"] > 0].copy()
        sku_profitability["rentabilidade"] = np.where(
            sku_profitability["receita_bruta"] > 0,
            sku_profitability["margem_contribuicao"] / sku_profitability["receita_bruta"],
            0.0
        )
        best_skus = sku_profitability.nlargest(5, "rentabilidade")
        worst_skus = sku_profitability.nsmallest(5, "rentabilidade")
        sku_sel = pd.concat([best_skus, worst_skus])

    # Clientes ativos na janela
    if "customer_id" in vendas.columns and "customer_id" in clientes.columns:
        customer_ids_vendas = set(vendas["customer_id"].dropna().unique())
        clientes_ativos = clientes[clientes["customer_id"].isin(customer_ids_vendas)].copy()
    else:
        clientes_ativos = clientes.iloc[0:0].copy()

    if len(clientes_ativos) and "segmento_rfm" in clientes_ativos.columns:
        segments = clientes_ativos["segmento_rfm"].value_counts().rename_axis("segmento").reset_index(name="clientes")
    else:
        segments = pd.DataFrame(columns=["segmento", "clientes"])

    ltv_medio = clientes_ativos["ltv_acumulado"].mean() if len(clientes_ativos) and "ltv_acumulado" in clientes_ativos.columns else 0.0
    ltv_risco = 0.0
    if len(clientes_ativos) and {"segmento_rfm", "ltv_acumulado"}.issubset(clientes_ativos.columns):
        ltv_risco = clientes_ativos.loc[clientes_ativos["segmento_rfm"] == "Em Risco", "ltv_acumulado"].sum()

    recompra_pct = 0.0
    if len(clientes_ativos) and "total_pedidos_historico" in clientes_ativos.columns:
        recompra_pct = (clientes_ativos["total_pedidos_historico"] > 1).mean()

    churn_pct = 0.0
    if len(clientes_ativos) and "segmento_rfm" in clientes_ativos.columns:
        churn_pct = clientes_ativos["segmento_rfm"].isin(["Em Risco", "Hibernando"]).mean()

    # Operações
    taxa_devolucao = vendas["is_devolvido"].mean() if len(vendas) else 0.0
    ruptura_pct = 0.0
    if len(estoque) and "status_disponibilidade" in estoque.columns:
        ruptura_pct = (estoque["status_disponibilidade"] == "Ruptura").mean()

    giro_estoque = sales_quantity / stock_quantity if stock_quantity > 0 else 0.0
    lead_time_medio = estoque["lead_time_reposicao"].mean() if len(estoque) and "lead_time_reposicao" in estoque.columns else 0.0

    # Atendimento
    volume_tickets = len(atendimento)
    sla_pct = resolved / volume_tickets if volume_tickets else 0.0
    csat_medio = atendimento["nota_csat"].mean() if volume_tickets and "nota_csat" in atendimento.columns else 0.0
    sentimento_positivo_pct = (atendimento["nota_csat"] >= 4).mean() if volume_tickets and "nota_csat" in atendimento.columns else 0.0
    custo_medio_ticket = atendimento["custo_operacional_ticket"].mean() if volume_tickets and "custo_operacional_ticket" in atendimento.columns else 0.0
    tempo_resposta_medio = atendimento["tempo_primeira_resposta_minutos"].mean() if volume_tickets and "tempo_primeira_resposta_minutos" in atendimento.columns else 0.0

    # Produtividade
    horas_poupadas_chatbot = 0.0
    if len(wismo) and "canal_entrada" in wismo.columns:
        horas_poupadas_chatbot = (wismo["canal_entrada"] == "ChatBot").sum() * 0.25

    potencial_automacao_wismo_pct = len(wismo) / len(atendimento) if len(atendimento) else 0.0
    horas_poupadas_potencial = len(wismo) * 0.75 * 0.25

    return {
        "comercial": {
            "receita_bruta": safe_float(receita),
            "pedidos_totais": safe_int(pedidos_totais),
            "pedidos_aprovados": safe_int(aprovados),
            "ticket_medio": safe_float(receita / pedidos_totais) if pedidos_totais else 0.0,
            "taxa_conversao": safe_float(taxa_conversao_decimal),
            "taxa_conversao_pct": safe_float(taxa_conversao_decimal * 100),
        },
        "margem": {
            "margem_contribuicao": safe_float(margem_contribuicao),
            "margem_pct": safe_float(margem_contribuicao / receita) if receita else 0.0,
            "margem_pct_percentual": safe_float((margem_contribuicao / receita) * 100) if receita else 0.0,
            "desconto_medio_pct": safe_float(desconto_total / receita) if receita else 0.0,
            "desconto_medio_pedido": safe_float(desconto_total / pedidos_totais) if pedidos_totais else 0.0,
            "frete_medio": safe_float(frete_medio),
            "rentabilidade_por_sku": [
                {
                    "sku_id": row.get("sku_id", ""),
                    "produto": row.get("produto", ""),
                    "receita_bruta": safe_float(row.get("receita_bruta", 0)),
                    "margem_contribuicao": safe_float(row.get("margem_contribuicao", 0)),
                    "rentabilidade": safe_float(row.get("rentabilidade", 0)),
                }
                for row in sku_sel.to_dict("records")
            ],
        },
        "marketing": {
            "cac_ponderado": safe_float(marketing["investimento_reais"].sum() / marketing["conversoes"].sum()) if "investimento_reais" in marketing.columns and "conversoes" in marketing.columns and marketing["conversoes"].sum() else 0.0,
            "roas_consolidado": safe_float(vendas.loc[vendas["status_pagamento"] == "Aprovado", "receita_bruta"].sum() / marketing["investimento_reais"].sum()) if "status_pagamento" in vendas.columns and "investimento_reais" in marketing.columns and marketing["investimento_reais"].sum() else 0.0,
            "conversoes_totais": safe_int(marketing["conversoes"].sum()) if "conversoes" in marketing.columns else 0,
        },
        "clientes": {
            "ltv_medio": safe_float(ltv_medio),
            "ltv_risco": safe_float(ltv_risco),
            "recompra_pct": safe_float(recompra_pct),
            "churn_pct": safe_float(churn_pct),
            "segmentos": segments.to_dict("records"),
        },
        "operacoes": {
            "taxa_devolucao": safe_float(taxa_devolucao),
            "taxa_devolucao_pct": safe_float(taxa_devolucao * 100),
            "ruptura_pct": safe_float(ruptura_pct),
            "giro_estoque": safe_float(giro_estoque),
            "lead_time_medio": safe_float(lead_time_medio),
        },
        "atendimento": {
            "volume_total": safe_int(volume_tickets),
            "sla_pct": safe_float(sla_pct),
            "csat_medio": safe_float(csat_medio),
            "sentimento_positivo_pct": safe_float(sentimento_positivo_pct),
            "custo_medio_ticket": safe_float(custo_medio_ticket),
            "tempo_resposta_medio": safe_float(tempo_resposta_medio),
        },
        "produtividade": {
            "horas_poupadas_chatbot": safe_float(horas_poupadas_chatbot),
            "horas_poupadas_potencial": safe_float(horas_poupadas_potencial),
            "potencial_automacao_wismo_pct": safe_float(potencial_automacao_wismo_pct),
        },
    }

# ============================================================
# Oportunidades / impacto / roadmap
# ============================================================
DEFAULT_PARAMS = {
    "wismo_capex": 30000.0,
    "wismo_tx_automacao": 0.75,
    "wismo_custo_humano": 12.0,
    "wismo_custo_bot": 2.0,  # alinhado ao simulador.ipynb

    "frete_capex": 12000.0,
    "frete_teto_valor": 199.0,

    "midia_capex": 25000.0,
    "midia_tx_realocacao": 0.30,
    "midia_ganho_estimado": 0.05,

    "bundle_capex": 18000.0,
    "bundle_giro_alvo": 0.20,
    "bundle_meses_alvo": 3.0,

    "dev_capex": 45000.0,
    "dev_tx_reducao": 0.10,
}

PERFIS_SIMULACAO = {
    "Base": {},
    "Pessimista (Estresse)": {
        "wismo_tx_automacao": 0.30,
        "wismo_capex": 45000.0,
        "frete_teto_valor": 149.0,
        "midia_ganho_estimado": 0.01,
        "dev_tx_reducao": 0.03,
    },
    "Conservador": {
        "wismo_tx_automacao": 0.50,
        "wismo_capex": 35000.0,
        "midia_tx_realocacao": 0.20,
        "midia_ganho_estimado": 0.03,
        "bundle_giro_alvo": 0.15,
        "dev_tx_reducao": 0.05,
    },
    "Agressivo (Alta Eficiência)": {
        "wismo_tx_automacao": 0.90,
        "wismo_capex": 25000.0,
        "frete_teto_valor": 249.0,
        "midia_ganho_estimado": 0.08,
        "bundle_giro_alvo": 0.30,
        "dev_tx_reducao": 0.15,
    },
    "Foco em CX": {
        "wismo_tx_automacao": 0.60,
        "wismo_capex": 50000.0,
        "frete_teto_valor": 129.0,
        "dev_tx_reducao": 0.12,
        "dev_capex": 60000.0,
    },
    "Proteção de Caixa (Cash Crunch)": {
        "wismo_tx_automacao": 0.80,
        "wismo_capex": 10000.0,
        "frete_teto_valor": 299.0,
        "frete_capex": 5000.0,
        "bundle_giro_alvo": 0.40,
        "bundle_meses_alvo": 1.5,
        "midia_tx_realocacao": 0.50,
    },
}

def calcular_oportunidades(ctx, params=None):
    p = DEFAULT_PARAMS.copy()
    if params:
        p.update(params)

    v = ctx["vendas"]
    a = ctx["atendimento"]
    m = ctx["marketing"]
    e = ctx["estoque"]
    M = ctx["window_months"]

    # 1. Automação WISMO
    if len(a) and "categoria_problema" in a.columns:
        wismo = a[a["categoria_problema"] == "Onde está meu pedido?"]
    else:
        wismo = a.iloc[0:0]

    tickets_wismo = len(wismo)
    eco_wismo = 0.0

    if tickets_wismo and "custo_operacional_ticket" in wismo.columns and safe_float(wismo["custo_operacional_ticket"].sum()) > 0:
        if "canal_entrada" in wismo.columns:
            manual = wismo[wismo["canal_entrada"].fillna("").str.lower() != "chatbot"]
        else:
            manual = wismo

        custo_manual_total = safe_float(manual["custo_operacional_ticket"].sum())
        tickets_manual = len(manual)
        tickets_migrados = tickets_manual * p["wismo_tx_automacao"]
        custo_evitado = custo_manual_total * p["wismo_tx_automacao"]
        custo_bot = tickets_migrados * p["wismo_custo_bot"]
        eco_wismo = max(custo_evitado - custo_bot, 0.0)
    else:
        eco_wismo = tickets_wismo * p["wismo_tx_automacao"] * max(p["wismo_custo_humano"] - p["wismo_custo_bot"], 0.0)

    # 2. Corte Frete Crítico
    eco_frete = 0.0
    if {"quantidade", "receita_bruta", "custo_frete", "margem_contribuicao"}.issubset(v.columns):
        frete_mask = (
            (v["quantidade"] == 1) &
            (v["receita_bruta"] < p["frete_teto_valor"]) &
            (v["custo_frete"] > v["margem_contribuicao"])
        )
        eco_frete = safe_float(v.loc[frete_mask, "custo_frete"].sum())

    # 3. Otimização de Mídia
    inv_midia = safe_float(m["investimento_reais"].sum()) if "investimento_reais" in m.columns else 0.0
    eco_midia = inv_midia * p["midia_tx_realocacao"] * p["midia_ganho_estimado"]

    # 4. Bundles Moda + Beleza
    capital_parado = 0.0
    if {"categoria", "estoque_disponivel", "custo_unitario"}.issubset(e.columns):
        moda_mask = (e["categoria"] == "Moda") & (e["estoque_disponivel"] > 1000)
        capital_parado = safe_float((e.loc[moda_mask, "estoque_disponivel"] * e.loc[moda_mask, "custo_unitario"]).sum())

    ben_mensal_bundles = (capital_parado * p["bundle_giro_alvo"] / p["bundle_meses_alvo"]) if p["bundle_meses_alvo"] else 0.0
    eco_bundles = ben_mensal_bundles * M

    # 5. Redução de Devoluções
    dev_mask = v["is_devolvido"] if "is_devolvido" in v.columns else pd.Series(False, index=v.index)
    margem_perdida = safe_float(v.loc[dev_mask, "margem_contribuicao"].sum()) if "margem_contribuicao" in v.columns else 0.0
    receita_perdida = safe_float(v.loc[dev_mask, "receita_bruta"].sum()) if "receita_bruta" in v.columns else 0.0
    custo_frete_reverso = safe_float(v.loc[dev_mask, "custo_frete"].sum()) if "custo_frete" in v.columns else 0.0

    custo_tickets_dev = 0.0
    if len(a) and "categoria_problema" in a.columns:
        tickets_dev = a[a["categoria_problema"].isin(["Defeito", "Troca de Tamanho"])]
        if "custo_operacional_ticket" in tickets_dev.columns:
            custo_tickets_dev = safe_float(tickets_dev["custo_operacional_ticket"].sum())

    # Para o impacto principal, mantenho a lógica do geral.ipynb: margem recuperável
    eco_dev = margem_perdida * p["dev_tx_reducao"]

    # Métricas auxiliares alinhadas ao simulador.ipynb
    eco_dev_log_reversa = (custo_frete_reverso + custo_tickets_dev) * p["dev_tx_reducao"]

    economia_opex_total = eco_wismo + eco_frete + eco_midia + eco_dev
    capital_desrepresado = eco_bundles
    recuperacao_ebitda = economia_opex_total + capital_desrepresado

    capex_total = (
        p["wismo_capex"] +
        p["frete_capex"] +
        p["midia_capex"] +
        p["bundle_capex"] +
        p["dev_capex"]
    )

    beneficio_mensal_global = (recuperacao_ebitda / M) if M > 0 else 0.0
    payback_global_meses = (capex_total / beneficio_mensal_global) if beneficio_mensal_global > 0 else None
    receita_protegida = receita_perdida * p["dev_tx_reducao"]
    margem_protegida = margem_perdida * p["dev_tx_reducao"]

    def make_action(nome, iniciativa, area, capex, impacto_janela, beneficio_mensal=None):
        bm = safe_float(impacto_janela / M) if beneficio_mensal is None else safe_float(beneficio_mensal)
        pay = safe_float(capex / bm) if bm > 0 else None
        return {
            "nome": nome,
            "iniciativa": iniciativa,
            "area": area,
            "valor": safe_float(impacto_janela),
            "investimento": safe_float(capex),
            "capex": safe_float(capex),
            "beneficio_mensal": bm,
            "payback_meses": pay,
        }

    acoes = [
        make_action("Automação WISMO", "1. Automação WISMO", "CX", p["wismo_capex"], eco_wismo),
        make_action("Política de Frete", "2. Corte Frete Crítico", "Logística", p["frete_capex"], eco_frete),
        make_action("Realocação Marketing", "3. Otimização de Mídia", "Marketing", p["midia_capex"], eco_midia),
        make_action("Capital em Bundles", "4. Bundles Moda+Beleza", "Estoque", p["bundle_capex"], eco_bundles, ben_mensal_bundles),
        make_action("Redução Devoluções", "5. Redução de Devoluções", "Operações", p["dev_capex"], eco_dev),
    ]

    return {
        "parametros": p,
        "economia_opex_total": safe_float(economia_opex_total),
        "capital_desrepresado": safe_float(capital_desrepresado),
        "recuperacao_ebitda": safe_float(recuperacao_ebitda),
        "beneficio_mensal_global": safe_float(beneficio_mensal_global),
        "payback_global_meses": payback_global_meses,
        "receita_protegida": safe_float(receita_protegida),
        "receita_afetada_devolucoes": safe_float(receita_perdida),
        "margem_protegida": safe_float(margem_protegida),
        "eco_dev_log_reversa": safe_float(eco_dev_log_reversa),
        "acoes": acoes,
    }

def build_roadmap(impacto_base):
    config = [
        {
            "nome": "Política de Frete",
            "iniciativa": "2. Corte Frete Crítico",
            "area": "Logística / E-commerce",
            "horizonte": "Q1 / Semanas 1-2",
            "fase": 1,
            "status": "Planejamento",
        },
        {
            "nome": "Automação WISMO",
            "iniciativa": "1. Automação WISMO",
            "area": "CX / Atendimento",
            "horizonte": "Q1 / Semanas 3-6",
            "fase": 2,
            "status": "Planejamento",
        },
        {
            "nome": "Capital em Bundles",
            "iniciativa": "4. Bundles Moda+Beleza",
            "area": "Comercial / Estoque",
            "horizonte": "Q1 / Semanas 4-8",
            "fase": 2,
            "status": "Planejamento",
        },
        {
            "nome": "Realocação Marketing",
            "iniciativa": "3. Otimização de Mídia",
            "area": "Growth / Marketing",
            "horizonte": "Q2 / Mês 1-2",
            "fase": 2,
            "status": "Planejamento",
        },
        {
            "nome": "Redução Devoluções",
            "iniciativa": "5. Redução de Devoluções",
            "area": "Operações / Logística Reversa",
            "horizonte": "Q2-Q3",
            "fase": 3,
            "status": "Planejamento",
        },
    ]

    roadmap = []
    for idx, item in enumerate(config, start=1):
        action = next((x for x in impacto_base["acoes"] if x["nome"] == item["nome"]), None)
        roadmap.append({
            "ordem": idx,
            "iniciativa": item["iniciativa"],
            "nome": item["nome"],
            "area": item["area"],
            "horizonte": item["horizonte"],
            "fase": item["fase"],
            "status": item["status"],
            "capex": action["investimento"] if action else 0.0,
            "ganho_na_janela": action["valor"] if action else 0.0,
            "beneficio_mensal": action["beneficio_mensal"] if action else 0.0,
            "payback_meses": action["payback_meses"] if action else None,
            "progresso_pct": 0.0,
        })

    return roadmap

# ============================================================
# Cenários estilo simulador.ipynb
# ============================================================
def build_simulador_scenarios(ctx):
    v = ctx["vendas"]
    a = ctx["atendimento"]
    e = ctx["estoque"]
    M = ctx["window_months"]

    annual_factor = 12.0 / M if M > 0 else 1.0

    pedidos = v["order_id"].nunique() if "order_id" in v.columns else len(v)
    mc = safe_float(v["margem_contribuicao"].sum()) if "margem_contribuicao" in v.columns else 0.0
    mc_por_pedido = mc / pedidos if pedidos else 0.0

    dev = v[v["is_devolvido"]] if "is_devolvido" in v.columns else v.iloc[0:0]
    if "motivo_devolucao" in dev.columns:
        motivos_alvo = ["Tamanho errado", "Produto com defeito", "Atraso na entrega"]
        dev_crit = dev[dev["motivo_devolucao"].isin(motivos_alvo)]
    else:
        dev_crit = dev

    custo_frete_reverso = safe_float(dev_crit["custo_frete"].sum()) if "custo_frete" in dev_crit.columns else 0.0

    if len(a) and "categoria_problema" in a.columns:
        wismo = a[a["categoria_problema"] == "Onde está meu pedido?"]
    else:
        wismo = a.iloc[0:0]

    canais_manual = ["E-mail", "WhatsApp", "Telefone", "Reclame Aqui"]
    if "canal_entrada" in wismo.columns:
        wismo_manual = wismo[wismo["canal_entrada"].isin(canais_manual)]
        cb = wismo[(wismo["canal_entrada"] == "ChatBot") & (wismo["categoria_problema"] == "Onde está meu pedido?")]
    else:
        wismo_manual = wismo
        cb = wismo.iloc[0:0]

    tickets_onde_ano = len(wismo_manual) * annual_factor
    custo_onde_ano = safe_float(wismo_manual["custo_operacional_ticket"].sum()) * annual_factor if "custo_operacional_ticket" in wismo_manual.columns else 0.0

    tempo_manual = wismo_manual["tempo_primeira_resposta_minutos"].mean() if len(wismo_manual) and "tempo_primeira_resposta_minutos" in wismo_manual.columns else 0.0
    if pd.isna(tempo_manual):
        tempo_manual = 0.0
    tempo_manual = safe_float(tempo_manual)

    cb_time = cb["tempo_primeira_resposta_minutos"].mean() if len(cb) and "tempo_primeira_resposta_minutos" in cb.columns else 0.5
    if pd.isna(cb_time):
        cb_time = 0.5
    cb_time = safe_float(cb_time)

    if len(a) and "categoria_problema" in a.columns:
        tkts_def_tam = a[a["categoria_problema"].isin(["Defeito", "Troca de Tamanho"])]
    else:
        tkts_def_tam = a.iloc[0:0]

    custo_tkts_def_tam_ano = safe_float(tkts_def_tam["custo_operacional_ticket"].sum()) * annual_factor if "custo_operacional_ticket" in tkts_def_tam.columns else 0.0

    receita_protegida_total = 0.0
    if {"status_disponibilidade", "sku_id"}.issubset(e.columns) and {"sku_id", "quantidade", "preco_unitario"}.issubset(v.columns):
        estq_risco = e[e["status_disponibilidade"].isin(["Estoque Crítico", "Ruptura"])].copy()
        giro = v.groupby("sku_id").agg(
            qtd_vendida=("quantidade", "sum"),
            preco_medio=("preco_unitario", "mean")
        ).reset_index()
        merged = estq_risco.merge(giro, on="sku_id", how="left")
        receita_protegida_total = safe_float((merged["qtd_vendida"].fillna(0) * merged["preco_medio"].fillna(0)).sum())

    def simular(nome, taxa_deflexao, reducao_devolucoes, capex=50000):
        tkts_migrados = tickets_onde_ano * taxa_deflexao
        custo_evitado = custo_onde_ano * taxa_deflexao
        novo_custo_bot = tkts_migrados * 2.0
        economia_suporte = custo_evitado - novo_custo_bot

        tempo_pond = ((1 - taxa_deflexao) * tempo_manual) + (taxa_deflexao * cb_time)

        economia_frete = custo_frete_reverso * reducao_devolucoes
        economia_tkts = custo_tkts_def_tam_ano * reducao_devolucoes
        economia_log_rev = economia_frete + economia_tkts

        economia_total_opex = economia_suporte + economia_log_rev
        nova_margem_pedido = (mc + economia_total_opex) / pedidos if pedidos else 0.0
        payback = (capex / economia_total_opex) * 12 if economia_total_opex > 0 else None

        return {
            "Cenário": nome,
            "Automação (%)": safe_float(taxa_deflexao),
            "Redução Devoluções (%)": safe_float(reducao_devolucoes),
            "Eco. Suporte (R$)": safe_float(economia_suporte),
            "Eco. Logística Rev. (R$)": safe_float(economia_log_rev),
            "Economia Total Opex (R$)": safe_float(economia_total_opex),
            "SLA Resposta (min)": safe_float(tempo_pond),
            "Margem Unitária (R$)": safe_float(nova_margem_pedido),
            "Receita Protegida (R$)": safe_float(receita_protegida_total),
            "Payback (Meses)": payback,
        }

    cenarios = [
        simular("Atual / Baseline", 0.0, 0.0),
        simular("Conservador", 0.50, 0.10),
        simular("Moderado", 0.75, 0.20),
        simular("Agressivo", 0.90, 0.30),
        simular("Teste Estresse Usuário", 0.20, 0.05, capex=75000),
    ]

    return {
        "premissas": {
            "janela_meses": safe_float(M),
            "fator_anualizacao": safe_float(annual_factor),
            "custo_frete_reverso": safe_float(custo_frete_reverso),
            "tickets_wismo_manual_ano": safe_float(tickets_onde_ano),
            "custo_wismo_manual_ano": safe_float(custo_onde_ano),
            "tempo_manual_medio_min": tempo_manual,
            "tempo_chatbot_medio_min": cb_time,
            "custo_tickets_dev_tam_ano": safe_float(custo_tkts_def_tam_ano),
            "receita_protegida_estoque": safe_float(receita_protegida_total),
            "margem_por_pedido_baseline": safe_float(mc_por_pedido),
        },
        "cenarios": cenarios,
    }

# ============================================================
# Modo integrado
# ============================================================
def build_mode(ctx):
    vendas = ctx["vendas"]
    marketing = ctx["marketing"]
    atendimento = ctx["atendimento"]
    estoque = ctx["estoque"]
    clientes = ctx["clientes"]

    # Hipóteses
    if "margem_contribuicao" in vendas.columns:
        negative = vendas[vendas["margem_contribuicao"] < 0].copy()
    else:
        negative = vendas.iloc[0:0].copy()

    if not negative.empty and "categoria" in negative.columns:
        h3 = negative.groupby("categoria").agg(
            receita_bruta=("receita_bruta", "sum"),
            custo_frete=("custo_frete", "sum"),
            desconto=("desconto_reais", "sum")
        ).reset_index()
        h3["peso_frete_pct"] = np.where(h3["receita_bruta"] > 0, h3["custo_frete"] / h3["receita_bruta"], 0.0)
        h3["peso_desconto_pct"] = np.where(h3["receita_bruta"] > 0, h3["desconto"] / h3["receita_bruta"], 0.0)
        h3_records = h3.to_dict("records")
    else:
        h3_records = []

    produtos, excess, bundles = stock_and_bundles(vendas, estoque)

    # Atendimento / WISMO
    if len(atendimento) and "categoria_problema" in atendimento.columns:
        wismo = atendimento[atendimento["categoria_problema"] == "Onde está meu pedido?"]
    else:
        wismo = atendimento.iloc[0:0]

    wismo_custo = 0.0
    if len(wismo) and "custo_operacional_ticket" in wismo.columns:
        if "canal_entrada" in wismo.columns:
            wismo_custo = safe_float(wismo.loc[wismo["canal_entrada"] != "ChatBot", "custo_operacional_ticket"].sum())
        else:
            wismo_custo = safe_float(wismo["custo_operacional_ticket"].sum())

    dev_mask = vendas["is_devolvido"] if "is_devolvido" in vendas.columns else pd.Series(False, index=vendas.index)
    margem_perdida = safe_float(vendas.loc[dev_mask, "margem_contribuicao"].sum()) if "margem_contribuicao" in vendas.columns else 0.0

    # Oportunidades base
    impacto_base = calcular_oportunidades(ctx, DEFAULT_PARAMS)

    # Cenários
    cenarios = {}
    for nome_perfil, params in PERFIS_SIMULACAO.items():
        res = calcular_oportunidades(ctx, params)
        cenarios[nome_perfil] = {
            "resumo": {
                "economia_opex_total": res["economia_opex_total"],
                "capital_desrepresado": res["capital_desrepresado"],
                "recuperacao_ebitda": res["recuperacao_ebitda"],
                "beneficio_mensal_global": res["beneficio_mensal_global"],
                "payback_global_meses": res["payback_global_meses"],
                "receita_protegida": res["receita_protegida"],
                "receita_afetada_devolucoes": res["receita_afetada_devolucoes"],
                "margem_protegida": res["margem_protegida"],
            },
            "acoes": res["acoes"],
        }

    roadmap = build_roadmap(impacto_base)

    rfm = []
    if len(clientes) and "segmento_rfm" in clientes.columns:
        rfm = clientes["segmento_rfm"].value_counts().rename_axis("segmento").reset_index(name="quantidade").to_dict("records")

    return {
        "kpis": build_kpis(vendas, clientes, estoque, marketing, atendimento),
        "temporal": temporal_series(vendas, marketing, atendimento),
        "canais": channel_analysis(vendas, marketing),
        "analise_frete": shipping_analysis(vendas),
        "canais_rfm": chanel_rfm(vendas, clientes, marketing),
        "saude_categorias": category_health_analysis(vendas, estoque, ctx["window_months"]),
        "hipoteses": {
            "margem_negativa_h3": h3_records,
            "pedidos_margem_negativa": safe_int(len(negative)),
            "sobre_estoque_h4": excess,
            "bundles_sugeridos": bundles,
            "atendimento_h5_h6": {
                "taxa_devolucao_pct": safe_float(vendas["is_devolvido"].mean()) if len(vendas) and "is_devolvido" in vendas.columns else 0.0,
                "margem_perdida": margem_perdida,
                "wismo_qtd": safe_int(len(wismo)),
                "wismo_custo": wismo_custo,
            },
        },
        "impacto": {
            "recuperacao_ebitda": impacto_base["recuperacao_ebitda"],
            "economia_estimada": impacto_base["recuperacao_ebitda"],
            "economia_opex_total": impacto_base["economia_opex_total"],
            "capital_desrepresado": impacto_base["capital_desrepresado"],
            "receita_protegida": impacto_base["receita_protegida"],
            "receita_afetada_devolucoes": impacto_base["receita_afetada_devolucoes"],
            "payback_meses": impacto_base["payback_global_meses"],
            "payback_global_meses": impacto_base["payback_global_meses"],
            "acoes": impacto_base["acoes"],
        },
        "oportunidades": impacto_base,
        "cenarios": cenarios,
        "previsoes_simulador": build_simulador_scenarios(ctx),
        "roadmap": roadmap,
        "produtos_ordenados": produtos,
        "rfm": rfm,
        "vendas_iniciadas_em": ctx["start_date"].strftime("%Y-%m-%d"),
        "vendas_encerradas_em": ctx["end_date"].strftime("%Y-%m-%d"),
        "janela_dias": ctx["window_days"],
        "janela_meses": safe_float(round(ctx["window_months"], 2)),
    }

# ============================================================
# Relatórios periódicos (MBR / WBR)
# ============================================================
def build_periodic_reports(ctx):
    vendas = ctx["vendas"].copy()
    marketing = ctx["marketing"].copy()
    atendimento = ctx["atendimento"].copy()

    if "is_devolvido" not in vendas.columns:
        vendas["is_devolvido"] = False

    for col in ["receita_liquida", "custo_frete", "receita_bruta", "desconto_reais", "custo_produto", "margem_contribuicao"]:
        if col not in vendas.columns:
            vendas[col] = 0.0

    vendas["receita_devolvida"] = np.where(vendas["is_devolvido"], vendas["receita_liquida"], 0.0)
    vendas["frete_reverso"] = np.where(vendas["is_devolvido"], vendas["custo_frete"], 0.0)
    vendas["receita_perdida"] = vendas["receita_devolvida"] + vendas["frete_reverso"]

    marketing_date = None
    if "data_fim" in marketing.columns:
        marketing_date = "data_fim"
    elif "data_inicio" in marketing.columns:
        marketing_date = "data_inicio"

    atendimento_date = None
    if "data_fechamento" in atendimento.columns:
        atendimento_date = "data_fechamento"
    elif "data_abertura" in atendimento.columns:
        atendimento_date = "data_abertura"

    reports = {}

    for period_type, dt_col in [("mes", "%Y-%m"), ("semana", "%Y-W%W")]:
        vendas["p"] = vendas["data_pedido"].dt.strftime(dt_col)

        if marketing_date and not marketing.empty:
            marketing["p"] = marketing[marketing_date].dt.strftime(dt_col)
        else:
            marketing["p"] = np.nan

        if atendimento_date and not atendimento.empty:
            atendimento["p"] = atendimento[atendimento_date].dt.strftime(dt_col)
        else:
            atendimento["p"] = np.nan

        periods_sorted = sorted(vendas["p"].dropna().unique())

        g = vendas.groupby("p")
        s_agg = pd.DataFrame(index=g.size().index)
        s_agg["receita_bruta"] = g["receita_bruta"].sum()
        s_agg["receita_liquida"] = g["receita_liquida"].sum()
        s_agg["desconto_reais"] = g["desconto_reais"].sum()
        s_agg["custo_frete"] = g["custo_frete"].sum()
        s_agg["custo_produto"] = g["custo_produto"].sum()
        s_agg["margem_contribuicao"] = g["margem_contribuicao"].sum()
        s_agg["pedidos"] = g["order_id"].nunique() if "order_id" in vendas.columns else g.size()
        s_agg["pedidos_devolvidos"] = g["is_devolvido"].sum() if "is_devolvido" in vendas.columns else 0
        s_agg["receita_perdida"] = g["receita_perdida"].sum()
        s_agg["ticket_medio"] = safe_divide(s_agg["receita_bruta"], s_agg["pedidos"])
        s_agg["margem_pct"] = safe_divide(s_agg["margem_contribuicao"], s_agg["receita_bruta"])
        s_agg["taxa_devolucao"] = safe_divide(s_agg["pedidos_devolvidos"], s_agg["pedidos"])

        if not marketing.empty and marketing["p"].notna().any():
            mg = marketing[marketing["p"].notna()].groupby("p")
            m_agg = pd.DataFrame(index=mg.size().index)
            m_agg["investimento"] = mg["investimento_reais"].sum() if "investimento_reais" in marketing.columns else 0.0
            m_agg["conversoes"] = mg["conversoes"].sum() if "conversoes" in marketing.columns else 0.0
            m_agg["receita_ads"] = mg["receita_gerada"].sum() if "receita_gerada" in marketing.columns else 0.0
            m_agg["cac"] = safe_divide(m_agg["investimento"], m_agg["conversoes"])
            m_agg["roas"] = safe_divide(m_agg["receita_ads"], m_agg["investimento"])
        else:
            m_agg = pd.DataFrame(columns=["investimento", "conversoes", "receita_ads", "cac", "roas"])

        if not atendimento.empty and atendimento["p"].notna().any():
            ag = atendimento[atendimento["p"].notna()].groupby("p")
            a_agg = pd.DataFrame(index=ag.size().index)
            a_agg["tickets"] = ag["ticket_id"].count() if "ticket_id" in atendimento.columns else ag.size()
            a_agg["csat_medio"] = ag["nota_csat"].mean() if "nota_csat" in atendimento.columns else 0.0
            a_agg["tempo_resposta_min"] = ag["tempo_primeira_resposta_minutos"].mean() if "tempo_primeira_resposta_minutos" in atendimento.columns else 0.0
        else:
            a_agg = pd.DataFrame(columns=["tickets", "csat_medio", "tempo_resposta_min"])

        comb = s_agg.join(m_agg, how="left").join(a_agg, how="left").fillna(0.0)

        period_data = {}
        for i, p_cur in enumerate(periods_sorted):
            if p_cur not in comb.index:
                continue

            cur = comb.loc[p_cur]
            prev = comb.loc[periods_sorted[i - 1]] if i > 0 and periods_sorted[i - 1] in comb.index else None

            def delta(key, is_pts=False):
                if prev is None:
                    return 0.0
                c_val = safe_float(cur.get(key, 0.0))
                p_val = safe_float(prev.get(key, 0.0))
                if is_pts:
                    return safe_float(round(c_val - p_val, 4))
                return safe_float(round((c_val - p_val) / abs(p_val), 4)) if p_val != 0 else 0.0

            v_p = vendas[vendas["p"] == p_cur].copy()
            if "categoria" not in v_p.columns:
                v_p["categoria"] = "Sem categoria"

            cat_p = v_p.groupby("categoria").agg(
                receita_bruta=("receita_bruta", "sum"),
                margem_contribuicao=("margem_contribuicao", "sum"),
                quantidade=("quantidade", "sum"),
                pedidos=("order_id", "nunique"),
            ).reset_index()
            cat_p["margem_pct"] = safe_divide(cat_p["margem_contribuicao"], cat_p["receita_bruta"])
            cat_list = cat_p.sort_values("receita_bruta", ascending=False).to_dict("records")

            for r in cat_list:
                for k, val in r.items():
                    if isinstance(val, (float, np.floating)):
                        r[k] = round(float(val), 2)

            m_p = marketing[marketing["p"] == p_cur].copy() if not marketing.empty else marketing.copy()

            if "status_pagamento" in v_p.columns:
                v_p_chan = v_p[v_p["status_pagamento"] == "Aprovado"].groupby("canal").agg(receita_bruta=("receita_bruta", "sum")).reset_index()
            else:
                v_p_chan = v_p.groupby("canal").agg(receita_bruta=("receita_bruta", "sum")).reset_index()

            if not m_p.empty and "canal" in m_p.columns:
                chan_p = m_p.groupby("canal").agg(
                    investimento=("investimento_reais", "sum"),
                    receita_ads=("receita_gerada", "sum"),
                    conversoes=("conversoes", "sum"),
                ).reset_index()
            else:
                chan_p = pd.DataFrame(columns=["canal", "investimento", "receita_ads", "conversoes"])

            for col in ["investimento", "receita_ads", "conversoes"]:
                if col not in chan_p.columns:
                    chan_p[col] = 0.0

            chan_merged = pd.merge(v_p_chan, chan_p, on="canal", how="outer").fillna(0.0)

            # garante numericidade
            for col in ["receita_bruta", "investimento", "receita_ads", "conversoes"]:
                if col not in chan_merged.columns:
                    chan_merged[col] = 0.0
                chan_merged[col] = pd.to_numeric(chan_merged[col], errors="coerce").fillna(0.0)

            chan_merged["roas"] = safe_divide(chan_merged["receita_bruta"], chan_merged["investimento"])
            chan_merged["cac"] = safe_divide(chan_merged["investimento"], chan_merged["conversoes"])

            chan_list = chan_merged.to_dict("records")

            for r in chan_list:
                for k, val in r.items():
                    if isinstance(val, (float, np.floating)):
                        r[k] = round(float(val), 2)

            if {"sku_id", "produto", "receita_bruta", "margem_contribuicao", "quantidade"}.issubset(v_p.columns):
                top_skus = v_p.groupby(["sku_id", "produto"]).agg(
                    receita_bruta=("receita_bruta", "sum"),
                    margem_contribuicao=("margem_contribuicao", "sum"),
                    quantidade=("quantidade", "sum"),
                ).reset_index()
                top_skus["margem_pct"] = safe_divide(top_skus["margem_contribuicao"], top_skus["receita_bruta"])
                best_rev = top_skus.sort_values("receita_bruta", ascending=False).head(5).to_dict("records")
                worst_margin = top_skus.sort_values("margem_pct", ascending=True).head(5).to_dict("records")
            else:
                best_rev = []
                worst_margin = []

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

def safe_divide(numerator, denominator, default=0.0):
    """
    Divisão segura para Series do pandas.
    Evita ZeroDivisionError e converte valores inválidos para default.
    """
    numerator = pd.to_numeric(numerator, errors="coerce")
    denominator = pd.to_numeric(denominator, errors="coerce")

    if isinstance(numerator, pd.Series):
        numerator = numerator.fillna(0.0)

        if isinstance(denominator, pd.Series):
            denominator = denominator.reindex(numerator.index).fillna(0.0)
        else:
            denominator = pd.Series(denominator, index=numerator.index, dtype=float).fillna(0.0)

        out = pd.Series(default, index=numerator.index, dtype=float)
        mask = denominator != 0
        out[mask] = numerator[mask] / denominator[mask]
        return out

    # fallback escalar
    numerator = 0.0 if pd.isna(numerator) else float(numerator)
    denominator = 0.0 if pd.isna(denominator) else float(denominator)

    return numerator / denominator if denominator != 0 else default

# ============================================================
# Processo principal
# ============================================================
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
            "janela_meses": safe_float(round(ctx["window_months"], 2)),
        },
        "modo_integrado": build_mode(ctx),
        "relatorios": build_periodic_reports(ctx),
    }

    dashboard_data = sanitize(dashboard_data)

    with OUTPUT_PATH.open("w", encoding="utf-8") as output:
        json.dump(dashboard_data, output, ensure_ascii=False, indent=2, allow_nan=False)

    print(
        f"[OK] Dados sincronizados com sucesso na janela de vendas "
        f"({ctx['start_date'].strftime('%Y-%m-%d')} a {ctx['end_date'].strftime('%Y-%m-%d')}): {OUTPUT_PATH}"
    )

if __name__ == "__main__":
    process_data()