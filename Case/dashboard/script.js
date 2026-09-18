function formatBRL(v) {
    if (v === null || v === undefined || isNaN(v)) return 'R$ 0,00';
    return Number(v).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

function formatNum(v) {
    if (v === null || v === undefined || isNaN(v)) return '0';
    return Number(v).toLocaleString('pt-BR');
}

function formatPct(v) {
    if (v === null || v === undefined || isNaN(v)) return '0,0%';
    const n = Number(v);
    const normalized = Math.abs(n) <= 1 ? n : n / 100;
    return normalized.toLocaleString('pt-BR', { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

function formatPts(v) {
    if (v === null || v === undefined || isNaN(v)) return '0,0 p.p.';
    const n = Number(v);
    const pts = Math.abs(n) <= 1 ? n * 100 : n;
    return `${pts.toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} p.p.`;
}

function formatBRLRigor(v) {
    if (v === null || v === undefined || isNaN(v)) return '—';
    return formatBRL(v);
}

function formatPaybackRigor(v) {
    if (v === null || v === undefined || isNaN(v) || !isFinite(v)) return '—';
    return `${Number(v).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} meses`;
}

function formatPctRigor(v) {
    if (v === null || v === undefined || isNaN(v)) return '—';
    const n = Number(v);
    const normalized = Math.abs(n) <= 1 ? n : n / 100;
    return formatPct(normalized);
}

function getPathRigor(obj, path, fallback = null) {
    if (!obj || !path) return fallback;
    return String(path).split('.').reduce((acc, key) => {
        if (acc == null) return fallback;
        return acc[key] !== undefined && acc[key] !== null ? acc[key] : fallback;
    }, obj);
}

function formatDateRigor(value) {
    if (!value) return '';
    const d = new Date(value);
    return isNaN(d) ? value : d.toLocaleDateString('pt-BR');
}

let dashboardData = null;
let charts = {};
let graficosOportunidades = {};
let selectedGranularity = 'mes';
let selectedArea = 'comercial';
let activeReportGranularity = 'mes';

const mapeamentoAcoes = {
    wismo: ['wismo', 'automação wismo', 'automacao wismo'],
    frete: ['frete', 'política de frete', 'politica de frete', 'corte frete'],
    marketing: ['marketing', 'mídia', 'midia', 'realocação marketing', 'otimização de mídia'],
    bundles: ['bundles', 'capital em bundles', 'moda+beleza', 'moda + beleza'],
    devolucoes: ['devoluções', 'devolucoes', 'redução devoluções', 'reducao devolucoes']
};

const kpiDictionary = {
    receita_bruta: { title: "Receita Bruta", desc: "Faturamento bruto total antes de deduções e devoluções.", formula: "∑ (Preço de Venda × Quantidade)" },
    margem_contribuicao: { title: "Margem de Contribuição", desc: "Sobra financeira das vendas após dedução de CMV, frete e devoluções.", formula: "Receita Líquida - (CMV + Frete + Devoluções)" },
    ebitda_potencial: { title: "Recuperação EBITDA", desc: "Ganho operacional direto projetado com as 4 alavancas prioritárias.", formula: "∑ (Economias + Redução de Sangrias)" },
    payback: { title: "Payback Médio", desc: "Meses necessários para que as economias geradas paguem o setup.", formula: "Investimento Total ÷ Economia Mensal" },
    pedidos_aprovados: { title: "Pedidos Aprovados", desc: "Volume de transações com pagamento confirmado.", formula: "Contagem distinta de order_id aprovados" },
    ticket_medio: { title: "Ticket Médio", desc: "Gasto médio por pedido aprovado.", formula: "Receita Bruta ÷ Pedidos Aprovados" },
    taxa_conversao: { title: "Taxa de Conversão", desc: "Percentual de cliques convertidos em compras.", formula: "(Conversões ÷ Cliques) × 100" },
    desconto_medio_pct: { title: "Desconto Médio Concedido", desc: "Impacto dos descontos sobre a receita de tabela.", formula: "(Descontos R$ ÷ Receita Bruta) × 100" },
    frete_medio: { title: "Custo Médio de Frete", desc: "Despesa média de transporte por entrega.", formula: "Frete Total ÷ Pedidos" },
    rentabilidade_por_sku: { title: "Rentabilidade por SKU", desc: "Margem percentual individual do produto.", formula: "Margem SKU ÷ Receita SKU" },
    cac_ponderado: { title: "CAC Ponderado", desc: "Custo médio de aquisição por cliente em mídia.", formula: "Investimento em Mídia ÷ Conversões" },
    roas_consolidado: { title: "ROAS Consolidado", desc: "Retorno em receita faturada por real investido em anúncios.", formula: "Receita Vendas Efetivadas ÷ Investimento Mídia" },
    conversoes_totais: { title: "Conversões em Mídia", desc: "Pedidos gerados por campanhas pagas.", formula: "∑ Conversões registradas" },
    recompra_pct: { title: "Taxa de Recompra", desc: "Clientes com 2 ou mais compras.", formula: "(Clientes > 1 Pedido ÷ Total Clientes) × 100" },
    ltv_medio: { title: "LTV Médio", desc: "Valor acumulado de compras por cliente na base.", formula: "Média de LTV individual" },
    churn_pct: { title: "Índice de Risco / Churn", desc: "Percentual de clientes em inatividade prolongada.", formula: "(Clientes em Risco ÷ Total Clientes) × 100" },
    taxa_devolucao: { title: "Taxa de Devolução", desc: "Percentual de pedidos com devolução ou estorno.", formula: "(Pedidos Devolvidos ÷ Total Pedidos) × 100" },
    ruptura_pct: { title: "Índice de Ruptura", desc: "Itens com saldo zerado no estoque físico.", formula: "(SKUs Zerados ÷ Total SKUs) × 100" },
    giro_estoque: { title: "Giro de Estoque", desc: "Velocidade de renovação do inventário na janela temporal das vendas.", formula: "Unidades Vendidas na janela ÷ Estoque Físico na janela" },
    lead_time_medio: { title: "Lead Time de Reposição", desc: "Dias decorridos entre o pedido de compra e entrega no armazém.", formula: "Média de dias de reposição" },
    volume_total: { title: "Volume de Chamados (SAC)", desc: "Total de tickets abertos no atendimento.", formula: "Contagem de tickets" },
    sla_pct: { title: "Aderência ao SLA", desc: "Chamados finalizados dentro da meta de CX.", formula: "(Tickets no Prazo ÷ Total) × 100" },
    sentimento_positivo_pct: { title: "Sentimento Positivo (CSAT)", desc: "Avaliações com nota 4 ou 5 estrelas.", formula: "(Notas 4 e 5 ÷ Total Avaliações) × 100" },
    custo_medio_ticket: { title: "Custo por Atendimento", desc: "Gasto operacional por chamado tratado.", formula: "Custo Central ÷ Volume Tickets" }
};

function makeTooltip(kpiKey) {
    const info = kpiDictionary[kpiKey];
    if (!info) return '';
    return `
    <span class="group relative inline-flex items-center align-middle cursor-help">
        <svg class="w-3.5 h-3.5 text-slate-400 group-hover:text-blue-600 transition" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-3a1 1 0 00-.867.5 1 1 0 11-1.731-1A3 3 0 0113 8a3.001 3.001 0 01-2 2.83V11a1 1 0 11-2 0v-1a1 1 0 011-1 1 1 0 100-2zm0 8a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
        <span class="invisible opacity-0 group-hover:visible group-hover:opacity-100 transition-all duration-200 absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 bg-slate-900 text-white text-xs rounded-xl shadow-2xl pointer-events-none z-50 text-left">
            <strong class="text-blue-300 block font-semibold mb-1 border-b border-slate-700 pb-1">${info.title}</strong>
            <span class="text-slate-200 block mb-2 leading-relaxed text-[11px]">${info.desc}</span>
            <span class="block text-[10px] text-emerald-300 font-mono bg-slate-800 p-1.5 rounded border border-slate-700"><strong>Fórmula:</strong> ${info.formula}</span>
        </span>
    </span>`;
}

// ================= CONTROLE DE NAVEGAÇÃO POR ABAS =================
function switchTab(tabId) {
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.add('hidden'));
    document.querySelectorAll('.tab-nav-btn').forEach(b => {
        b.classList.remove('text-blue-600', 'border-blue-600', 'bg-blue-50/70', 'shadow-xs', 'text-emerald-800', 'border-emerald-600', 'bg-emerald-50/70');
        b.classList.add('text-slate-600', 'border-transparent');
    });

    const activePanel = document.getElementById(`panel-${tabId}`);
    if (activePanel) activePanel.classList.remove('hidden');

    const activeBtn = document.getElementById(`nav-btn-${tabId}`);
    if (activeBtn) {
        activeBtn.classList.remove('text-slate-600', 'border-transparent');
        if (tabId === 'relatorio') {
            activeBtn.classList.add('text-emerald-800', 'border-emerald-600', 'bg-emerald-50/70', 'shadow-xs');
        } else {
            activeBtn.classList.add('text-blue-600', 'border-blue-600', 'bg-blue-50/70', 'shadow-xs');
        }
    }

    setTimeout(() => {
        if (tabId === 'diagnostico' && dashboardData) {
            renderArea(dashboardData.modo_integrado, selectedArea);
            if (charts.canal) charts.canal.resize();
            if (charts.canalRfm) charts.canalRfm.resize();
        } else if (tabId === 'overview') {
            if (charts.main) charts.main.resize();
            if (charts.rfm) charts.rfm.resize();
            if (charts.impacto) charts.impacto.resize();
        } else if (tabId === 'oportunidades') {
            Object.values(graficosOportunidades).forEach(c => { try { c.resize(); } catch(e){} });
        } else if (tabId === 'relatorio') {
            initReportSection();
            if (charts.reportCat) charts.reportCat.resize();
            if (charts.reportChan) charts.reportChan.resize();
        }
    }, 60);
}

function toggleAccordion(id) {
    const content = document.getElementById(`case-content-${id}`);
    const icon = document.getElementById(`case-icon-${id}`);
    if (!content) return;
    const isHidden = content.classList.contains('hidden');
    content.classList.toggle('hidden', !isHidden);
    if (icon) icon.classList.toggle('rotate-180', isHidden);

    if (isHidden) {
        const oppKey = id.replace('case-', '');
        setTimeout(() => {
            if (graficosOportunidades[oppKey]) {
                graficosOportunidades[oppKey].resize();
            }
        }, 50);
    }
}

let allExpanded = false;
function toggleAllAccordions() {
    allExpanded = !allExpanded;
    document.querySelectorAll('.accordion-content').forEach(c => c.classList.toggle('hidden', !allExpanded));
    document.querySelectorAll('[id^="case-icon-"]').forEach(icon => icon.classList.toggle('rotate-180', allExpanded));
    if (allExpanded) {
        setTimeout(() => {
            Object.values(graficosOportunidades).forEach(c => { try { c.resize(); } catch(e){} });
        }, 50);
    }
}

function toggleChatbotPopup() {
    const container = document.getElementById('chatbot-popup-container');
    const isHidden = container.classList.contains('hidden');
    if (isHidden) {
        container.classList.remove('hidden');
        setTimeout(() => { container.classList.remove('scale-95'); container.classList.add('scale-100'); }, 10);
    } else {
        container.classList.remove('scale-100');
        container.classList.add('scale-95');
        setTimeout(() => container.classList.add('hidden'), 150);
    }
}

// ================= ABA 2: RENDERIZADOR COMPLETO POR ÁREA =================
function renderArea(data, area) {
    const kpis = data.kpis;
    const impact = data.impacto;
    const areaTitles = {
        comercial: 'Comercial & Faturamento', margem: 'Margem & Custos Unitários', marketing: 'Marketing & Eficiência', 
        clientes: 'Base de Clientes & Retenção', operacoes: 'Operações & Logística', atendimento: 'Atendimento & CX', 
        impacto: 'Impacto Financeiro Consolidado'
    };

    const rows = {
        comercial: [
            ['receita_bruta', 'Receita bruta', formatBRL(kpis.comercial.receita_bruta)],
            ['pedidos_aprovados', 'Pedidos aprovados', formatNum(kpis.comercial.pedidos_aprovados)],
            ['ticket_medio', 'Ticket médio', formatBRL(kpis.comercial.ticket_medio)],
            ['taxa_conversao', 'Taxa de conversão', formatPctRigor(kpis.comercial.taxa_conversao_pct ?? kpis.comercial.taxa_conversao)]
        ],
        margem: [
            ['margem_contribuicao', 'Margem de contribuição', formatBRL(kpis.margem.margem_contribuicao)],
            ['desconto_medio_pct', 'Desconto médio concedido', formatPct(kpis.margem.desconto_medio_pct)],
            ['frete_medio', 'Custo médio de frete', formatBRL(kpis.margem.frete_medio)],
            ['rentabilidade_por_sku', 'SKU maior rentabilidade', kpis.margem.rentabilidade_por_sku.length ? `${kpis.margem.rentabilidade_por_sku[0].produto} (${formatPct(kpis.margem.rentabilidade_por_sku[0].rentabilidade)})` : 'Sem dados']
        ],
        marketing: [
            ['cac_ponderado', 'CAC Ponderado', formatBRL(kpis.marketing.cac_ponderado)],
            ['roas_consolidado', 'ROAS Consolidado', (kpis.marketing.roas_consolidado || 0).toFixed(2) + 'x'],
            ['conversoes_totais', 'Conversões em mídia', formatNum(kpis.marketing.conversoes_totais)],
            ['receita_bruta', 'Receita de vendas aprovadas', formatBRL(data.canais.reduce((s, c) => s + (c.receita_bruta || 0), 0))]
        ],
        clientes: [
            ['recompra_pct', 'Taxa de recompra', formatPct(kpis.clientes.recompra_pct)],
            ['ltv_medio', 'LTV Médio por cliente', formatBRL(kpis.clientes.ltv_medio)],
            ['churn_pct', 'Risco de churn da base', formatPct(kpis.clientes.churn_pct)],
            ['recompra_pct', 'Segmentos mapeados', formatNum(kpis.clientes.segmentos.length)]
        ],
        operacoes: [
            ['taxa_devolucao', 'Taxa de devolução', formatPct(kpis.operacoes.taxa_devolucao)],
            ['ruptura_pct', 'Ruptura de estoque', formatPct(kpis.operacoes.ruptura_pct)],
            ['giro_estoque', 'Giro médio de estoque', (kpis.operacoes.giro_estoque || 0).toFixed(2) + 'x'],
            ['lead_time_medio', 'Lead time de reposição', `${(kpis.operacoes.lead_time_medio || 0).toFixed(1)} dias`]
        ],
        atendimento: [
            ['volume_total', 'Volume de tickets', formatNum(kpis.atendimento.volume_total)],
            ['sla_pct', 'Aderência ao SLA', formatPct(kpis.atendimento.sla_pct)],
            ['sentimento_positivo_pct', 'Sentimento positivo (CSAT)', formatPct(kpis.atendimento.sentimento_positivo_pct)],
            ['custo_medio_ticket', 'Custo médio por ticket', formatBRL(kpis.atendimento.custo_medio_ticket)]
        ],
        impacto: [
            ['ebitda_potencial', 'EBITDA Potencial', formatBRL(impact.recuperacao_ebitda)],
            ['ebitda_potencial', 'Economia estimada', formatBRL(impact.economia_estimada)],
            ['receita_bruta', 'Receita protegida', formatBRL(impact.receita_protegida)],
            ['payback', 'Payback médio', formatPaybackRigor(impact.payback_global_meses ?? impact.payback_meses)]
        ]
    }[area] || [];

    document.getElementById('area-chart-title').textContent = areaTitles[area] || 'Área';
    document.getElementById('kpi-container').innerHTML = rows.map(([kpiKey, label, value]) => `
        <div class="flex items-center justify-between gap-4 py-3.5 hover:bg-slate-50/80 px-2 rounded-lg transition-colors">
            <span class="text-xs md:text-sm text-slate-600 flex items-center gap-1.5 font-medium">
                ${label}
                ${makeTooltip(kpiKey)}
            </span>
            <strong class="font-mono text-xs md:text-sm text-slate-900 text-right">${value}</strong>
        </div>`).join('');

    if (charts.area) charts.area.destroy();
    
    const chartData = {
        comercial: { 
            labels: ['Receita (R$k)', 'Pedidos (un/10)', 'Ticket (R$)', 'Conversão (%)'], 
            values: [kpis.comercial.receita_bruta / 1000, kpis.comercial.pedidos_aprovados / 10, kpis.comercial.ticket_medio, kpis.comercial.taxa_conversao * 100], 
            color: '#2563eb'
        },
        margem: { 
            labels: kpis.margem.rentabilidade_por_sku.map(sku => sku.produto.substring(0, 18)), 
            values: kpis.margem.rentabilidade_por_sku.map(sku => sku.rentabilidade * 100), 
            color: '#059669'
        },
        marketing: { 
            labels: data.canais.map(c => c.canal), 
            values: data.canais.map(c => c.margem_liquida_real), 
            color: '#d97706'
        },
        clientes: {
            labels: kpis.clientes.segmentos.map(s => s.segmento),
            values: kpis.clientes.segmentos.map(s => s.clientes),
            color: '#db2777'
        },
        operacoes: {
            labels: ['Devolução (%)', 'Ruptura (%)', 'Giro Estoque (x100)', 'Lead Time (dias)'],
            values: [kpis.operacoes.taxa_devolucao * 100, kpis.operacoes.ruptura_pct * 100, kpis.operacoes.giro_estoque * 100, kpis.operacoes.lead_time_medio],
            color: '#7c3aed'
        },
        atendimento: {
            labels: ['Tickets (/100)', 'SLA (%)', 'CSAT Positivo (%)', 'Custo/Ticket (R$)'],
            values: [kpis.atendimento.volume_total / 100, kpis.atendimento.sla_pct * 100, kpis.atendimento.sentimento_positivo_pct * 100, kpis.atendimento.custo_medio_ticket],
            color: '#0891b2'
        },
        impacto: { 
            labels: impact.acoes.map(a => a.nome), 
            values: impact.acoes.map(a => a.valor), 
            color: '#dc2626'
        }
    }[area] || { labels: [], values: [], color: '#2563eb' };

    charts.area = new Chart(document.getElementById('areaChart').getContext('2d'), {
        type: 'bar',
        data: {
            labels: chartData.labels,
            datasets: [{
                data: chartData.values,
                backgroundColor: chartData.color,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true } }
        }
    });
}

// ================= ABA 3: PROJEÇÕES & SELEÇÃO DE CENÁRIOS POR OPORTUNIDADE =================
function popularSeletoresCenariosOportunidades(data) {
    const cenarios = getPathRigor(data, 'modo_integrado.cenarios', {});
    const nomes = Object.keys(cenarios);
    if (!nomes.length) return;

    const oppKeys = ['wismo', 'frete', 'marketing', 'bundles', 'devolucoes'];
    oppKeys.forEach(key => {
        const select = document.getElementById(`select-cenario-${key}`);
        if (!select) return;

        select.innerHTML = nomes.map(nome => 
            `<option value="${nome}" ${nome === 'Base' ? 'selected' : ''}>${nome}</option>`
        ).join('');

        alterarCenarioOportunidade(key, 'Base');
    });
}

function alterarCenarioOportunidade(oppKey, cenarioNome) {
    if (!dashboardData) return;
    const cenarios = getPathRigor(dashboardData, 'modo_integrado.cenarios', {});
    const targetCenario = cenarios[cenarioNome] || cenarios['Base'];
    if (!targetCenario) return;

    const patterns = mapeamentoAcoes[oppKey] || [];
    const action = targetCenario.acoes.find(a => {
        const name = (a.nome || a.iniciativa || '').toLowerCase();
        return patterns.some(p => name.includes(p.toLowerCase()));
    });
    if (!action) return;

    const capex = action.investimento ?? action.capex ?? 0;
    const beneficioMensal = action.beneficio_mensal ?? 0;
    const valorJanela = action.valor ?? 0;
    const payback = action.payback_meses;

    const capexEl = document.getElementById(`${oppKey}-capex`);
    if (capexEl) capexEl.textContent = formatBRLRigor(capex);

    const benEl = document.getElementById(`${oppKey}-beneficio`);
    if (benEl) benEl.textContent = `${formatBRLRigor(beneficioMensal)} / mês`;

    const valEl = document.getElementById(`${oppKey}-valor`);
    if (valEl) valEl.textContent = formatBRLRigor(valorJanela);

    const payEl = document.getElementById(`${oppKey}-payback`);
    if (payEl) payEl.textContent = formatPaybackRigor(payback);

    const badgeStatus = document.getElementById(`${oppKey}-badge-status`);
    if (badgeStatus) badgeStatus.textContent = `Payback: ${formatPaybackRigor(payback)}`;

    renderizarGraficoOportunidade(oppKey, capex, beneficioMensal, payback);
}

function renderizarGraficoOportunidade(oppKey, capex, beneficioMensal, payback) {
    const canvas = document.getElementById(`chart-opp-${oppKey}`);
    if (!canvas) return;

    if (graficosOportunidades[oppKey]) {
        try { graficosOportunidades[oppKey].destroy(); } catch(e){}
    }

    const meses = Array.from({ length: 13 }, (_, i) => `Mês ${i}`);

    // Inércia mensal com base nos diagnósticos reais do process_data.py
    const inerciaMensalMap = {
        wismo: 4336.57,      // Custo manual de tickets WISMO sem automação
        frete: 3914.14,      // Frete deficitário subsidiado em pedidos unitários
        marketing: 19200.0,  // Margem subótima em canais de baixo retorno
        bundles: 25000.0,    // Custo de oportunidade de capital parado no estoque
        devolucoes: 11857.30 // Margem operacional destruída por trocas e avarias
    };

    const inercia = inerciaMensalMap[oppKey] || (beneficioMensal * 0.8);

    // Curva 1: Status Quo (Inércia / Sem ação)
    const semAcao = meses.map((_, i) => -(inercia * i));

    // Curva 2: Com Iniciativa (Amortização de Capex + Lucro Líquido Acumulado)
    const comAcao = meses.map((_, i) => -capex + (beneficioMensal * i));

    const colorMap = {
        wismo: '#2563eb',
        frete: '#dc2626',
        marketing: '#059669',
        bundles: '#7c3aed',
        devolucoes: '#e11d48'
    };

    const corPrincipal = colorMap[oppKey] || '#2563eb';

    graficosOportunidades[oppKey] = new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: {
            labels: meses,
            datasets: [
                {
                    label: 'Status Quo (Inércia / Sem Ação)',
                    data: semAcao,
                    borderColor: '#94a3b8',
                    borderDash: [5, 5],
                    borderWidth: 2,
                    pointRadius: 2,
                    fill: false
                },
                {
                    label: 'Com Iniciativa (Fluxo Líquido Acumulado)',
                    data: comAcao,
                    borderColor: corPrincipal,
                    backgroundColor: `${corPrincipal}15`,
                    borderWidth: 2.5,
                    pointRadius: 3,
                    pointHoverRadius: 5,
                    fill: true
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { position: 'top', labels: { boxWidth: 12, font: { size: 10 } } },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: ${formatBRL(ctx.parsed.y)}`
                    }
                }
            },
            scales: {
                y: {
                    grid: { color: '#f1f5f9' },
                    ticks: { callback: (v) => formatBRL(v) }
                },
                x: {
                    grid: { display: false }
                }
            }
        }
    });
}

// ================= ABA 5: LÓGICA DO RELATÓRIO EXECUTIVO =================
function initReportSection() {
    populateReportPeriods();
}

function setReportGranularity(gran) {
    activeReportGranularity = gran;
    document.getElementById('rep-btn-gran-mes').className = gran === 'mes' 
        ? 'px-3 py-1.5 rounded-md bg-white text-emerald-800 shadow-xs transition font-bold'
        : 'px-3 py-1.5 rounded-md text-slate-600 hover:text-slate-900 transition font-medium';
    document.getElementById('rep-btn-gran-semana').className = gran === 'semana' 
        ? 'px-3 py-1.5 rounded-md bg-white text-emerald-800 shadow-xs transition font-bold'
        : 'px-3 py-1.5 rounded-md text-slate-600 hover:text-slate-900 transition font-medium';

    document.getElementById('rep-doc-title').textContent = gran === 'mes' ? 'Monthly Business Review (MBR)' : 'Weekly Business Review (WBR)';
    populateReportPeriods();
}

function populateReportPeriods() {
    if (!dashboardData || !dashboardData.relatorios) return;
    const granData = dashboardData.relatorios[activeReportGranularity];
    if (!granData) return;

    const select = document.getElementById('report-period-select');
    const periods = [...granData.periodos_disponiveis].reverse();

    select.innerHTML = periods.map(p => `<option value="${p}">${p}</option>`).join('');
    if (periods.length > 0) {
        renderReportSnapshot(periods[0]);
    }
}

function onReportPeriodChange(periodKey) {
    renderReportSnapshot(periodKey);
}

function renderReportBadge(val, isPoints = false, invertSentiment = false) {
    if (val === null || val === undefined || isNaN(val)) return `<span class="text-slate-400 font-normal">Base</span>`;
    if (val === 0) return `<span class="text-slate-500 font-normal">0.0% vs ant.</span>`;

    const isPositive = val > 0;
    const isGood = invertSentiment ? !isPositive : isPositive;
    const colorClass = isGood ? 'text-emerald-700 bg-emerald-50 border-emerald-200' : 'text-red-700 bg-red-50 border-red-200';
    const arrow = isPositive ? '▲' : '▼';
    const formatted = isPoints ? formatPts(Math.abs(val)) : ((Math.abs(val) * 100).toFixed(1) + '%');

    return `<span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] font-bold ${colorClass}">
        ${arrow} ${formatted} vs ant.
    </span>`;
}

function renderReportSnapshot(periodKey) {
    const periodData = dashboardData.relatorios[activeReportGranularity].dados[periodKey];
    if (!periodData) return;

    document.getElementById('rep-doc-cur-period').textContent = periodData.periodo;
    document.getElementById('rep-doc-prev-period').textContent = periodData.periodo_anterior || 'Início da série';

    const k = periodData.kpis;
    document.getElementById('rep-kpi-rec').textContent = formatBRL(k.receita_bruta.val);
    document.getElementById('rep-kpi-rec-delta').innerHTML = renderReportBadge(k.receita_bruta.delta_pct);

    document.getElementById('rep-kpi-mc').textContent = formatBRL(k.margem_contribuicao.val);
    document.getElementById('rep-kpi-mc-delta').innerHTML = renderReportBadge(k.margem_contribuicao.delta_pct);

    document.getElementById('rep-kpi-mcpct').textContent = formatPct(k.margem_pct.val);
    document.getElementById('rep-kpi-mcpct-delta').innerHTML = renderReportBadge(k.margem_pct.delta_pts, true);

    document.getElementById('rep-kpi-pedidos').textContent = formatNum(k.pedidos.val);
    document.getElementById('rep-kpi-pedidos-delta').innerHTML = renderReportBadge(k.pedidos.delta_pct);

    document.getElementById('rep-kpi-roas').textContent = `${(k.roas.val || 0).toFixed(2)}x · ${formatBRL(k.cac.val)}`;
    document.getElementById('rep-kpi-cac-delta').innerHTML = renderReportBadge(k.cac.delta_pct, false, true);

    document.getElementById('rep-kpi-csat').textContent = `${(k.csat_medio.val || 0).toFixed(2)} ★ · ${formatPct(k.taxa_devolucao.val)}`;
    document.getElementById('rep-kpi-dev-delta').innerHTML = renderReportBadge(k.taxa_devolucao.delta_pts, true, true);

    const dre = periodData.dre_operacional;
    const recBruta = dre.receita_bruta || 1;
    document.getElementById('rep-dre-tbody').innerHTML = `
        <tr class="font-bold text-slate-900 bg-slate-50/50">
            <td class="py-1.5">(=) Receita Bruta Faturada</td>
            <td class="py-1.5 text-right">${formatBRL(dre.receita_bruta)}</td>
            <td class="py-1.5 text-right text-slate-500">100.0%</td>
        </tr>
        <tr class="text-amber-700">
            <td class="py-1 pl-4">(-) Descontos Concedidos</td>
            <td class="py-1 text-right">- ${formatBRL(dre.descontos)}</td>
            <td class="py-1 text-right text-slate-500">- ${formatPct(dre.descontos / recBruta)}</td>
        </tr>
        <tr class="font-semibold text-slate-800">
            <td class="py-1.5">(=) Receita Líquida</td>
            <td class="py-1.5 text-right">${formatBRL(dre.receita_liquida)}</td>
            <td class="py-1.5 text-right text-slate-500">${formatPct(dre.receita_liquida / recBruta)}</td>
        </tr>
        <tr class="text-slate-600">
            <td class="py-1 pl-4">(-) Custo das Mercadorias Vendidas (CMV)</td>
            <td class="py-1 text-right">- ${formatBRL(dre.custo_mercadoria)}</td>
            <td class="py-1 text-right text-slate-500">- ${formatPct(dre.custo_mercadoria / recBruta)}</td>
        </tr>
        <tr class="text-slate-600">
            <td class="py-1 pl-4">(-) Custo de Frete de Entrega</td>
            <td class="py-1 text-right">- ${formatBRL(dre.custo_frete)}</td>
            <td class="py-1 text-right text-slate-500">- ${formatPct(dre.custo_frete / recBruta)}</td>
        </tr>
        <tr class="text-red-600">
            <td class="py-1 pl-4">(-) Perdas com Devoluções & Frete Reverso</td>
            <td class="py-1 text-right">- ${formatBRL(dre.perda_devolucoes)}</td>
            <td class="py-1 text-right text-slate-500">- ${formatPct(dre.perda_devolucoes / recBruta)}</td>
        </tr>
        <tr class="font-bold text-emerald-700 bg-emerald-50/60 border-t-2 border-emerald-200">
            <td class="py-2">(=) Margem de Contribuição Operacional</td>
            <td class="py-2 text-right text-sm">${formatBRL(dre.margem_contribuicao)}</td>
            <td class="py-2 text-right text-sm">${formatPct(dre.margem_contribuicao_pct)}</td>
        </tr>
    `;

    const cats = periodData.categorias || [];
    document.getElementById('rep-cat-tbody').innerHTML = cats.map(c => `
        <tr>
            <td class="py-1 font-semibold text-slate-800">${c.categoria}</td>
            <td class="py-1 text-right font-mono">${formatBRL(c.receita_bruta)}</td>
            <td class="py-1 text-right font-mono text-emerald-700 font-bold">${formatBRL(c.margem_contribuicao)}</td>
            <td class="py-1 text-right font-mono">${formatPct(c.margem_pct)}</td>
            <td class="py-1 text-center font-mono">${formatNum(c.quantidade)}</td>
        </tr>
    `).join('');

    const chans = periodData.canais || [];
    document.getElementById('rep-chan-tbody').innerHTML = chans.map(c => `
        <tr>
            <td class="py-1 font-semibold text-slate-800">${c.canal}</td>
            <td class="py-1 text-right font-mono">${formatBRL(c.investimento)}</td>
            <td class="py-1 text-right font-mono font-medium">${formatBRL(c.receita_bruta)}</td>
            <td class="py-1 text-center font-mono font-bold ${(c.roas || 0) < 1 ? 'text-red-600' : 'text-emerald-700'}">${(c.roas || 0).toFixed(2)}x</td>
            <td class="py-1 text-right font-mono">${formatBRL(c.cac)}</td>
        </tr>
    `).join('');

    const topSkus = periodData.destaques_skus.top_receita || [];
    const worstSkus = periodData.destaques_skus.menor_margem || [];

    document.getElementById('rep-top-skus-tbody').innerHTML = topSkus.map((s, idx) => `
        <tr class="hover:bg-slate-50">
            <td class="py-1 truncate max-w-[180px]" title="${s.produto}">
                <span class="text-slate-400 font-mono font-bold mr-1">${idx + 1}.</span> ${s.produto}
            </td>
            <td class="py-1 text-right font-mono font-bold text-slate-800">${formatBRL(s.receita_bruta)}</td>
            <td class="py-1 text-right font-mono text-emerald-700">${formatPct(s.margem_pct)}</td>
        </tr>
    `).join('');

    document.getElementById('rep-worst-skus-tbody').innerHTML = worstSkus.map((s, idx) => `
        <tr class="hover:bg-slate-50">
            <td class="py-1 truncate max-w-[180px]" title="${s.produto}">
                <span class="text-slate-400 font-mono font-bold mr-1">${idx + 1}.</span> ${s.produto}
            </td>
            <td class="py-1 text-right font-mono text-slate-800">${formatBRL(s.receita_bruta)}</td>
            <td class="py-1 text-right font-mono font-bold ${s.margem_pct < 0 ? 'text-red-600' : 'text-amber-700'}">${formatPct(s.margem_pct)}</td>
        </tr>
    `).join('');

    if (charts.reportCat) charts.reportCat.destroy();
    charts.reportCat = new Chart(document.getElementById('chartCatRep').getContext('2d'), {
        type: 'bar',
        data: {
            labels: cats.map(c => c.categoria),
            datasets: [
                { label: 'Receita', data: cats.map(c => c.receita_bruta), backgroundColor: '#3b82f6', borderRadius: 3 },
                { label: 'Margem', data: cats.map(c => c.margem_contribuicao), backgroundColor: '#10b981', borderRadius: 3 }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 10 } } } },
            scales: { y: { beginAtZero: true, ticks: { callback: (v) => 'R$ ' + (v / 1000).toFixed(0) + 'k' } } }
        }
    });

    if (charts.reportChan) charts.reportChan.destroy();
    charts.reportChan = new Chart(document.getElementById('chartChanRep').getContext('2d'), {
        type: 'bar',
        data: {
            labels: chans.map(c => c.canal),
            datasets: [
                { label: 'Investimento Mídia', data: chans.map(c => c.investimento), backgroundColor: '#f59e0b', borderRadius: 3 },
                { label: 'Receita Vendas Aprovadas', data: chans.map(c => c.receita_bruta), backgroundColor: '#2563eb', borderRadius: 3 }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 10 } } } },
            scales: { y: { beginAtZero: true, ticks: { callback: (v) => 'R$ ' + (v / 1000).toFixed(0) + 'k' } } }
        }
    });
}

// ================= INICIALIZAÇÃO GERAL DO DASHBOARD =================
async function init() {
    document.getElementById('tt-macro-rec').innerHTML = makeTooltip('receita_bruta');
    document.getElementById('tt-macro-margem').innerHTML = makeTooltip('margem_contribuicao');
    document.getElementById('tt-macro-ebitda').innerHTML = makeTooltip('ebitda_potencial');
    document.getElementById('tt-macro-payback').innerHTML = makeTooltip('payback');

    const candidatePaths = [
        '../dados/process_data.json',
        'dados/process_data.json',
        '/dados/process_data.json',
        '../../dados/process_data.json',
        'process_data.json',
        'dashboard_data.json'
    ];

    let response = null;
    for (const path of candidatePaths) {
        try {
            const r = await fetch(path);
            if (r.ok) { response = r; break; }
        } catch(e) {}
    }

    if (!response) {
        document.getElementById('panel-overview').innerHTML = `
            <div class="card p-6 border-l-4 border-red-500 bg-red-50 text-red-700">
                <h3 class="font-bold text-base mb-1">Aviso: Arquivo de dados não encontrado</h3>
                <p class="text-xs leading-relaxed">
                    Execute <code class="bg-red-200 px-1 py-0.5 rounded font-mono">python dados/process_data.py</code> na raiz para gerar o <code class="font-mono">process_data.json</code> e certifique-se de executar via servidor HTTP local.
                </p>
            </div>`;
        return;
    }

    dashboardData = await response.json();
    renderDashboard(selectedGranularity);
    renderRigorExtensions(dashboardData);
    popularSeletoresCenariosOportunidades(dashboardData);
}

function renderDashboard(granularity = selectedGranularity) {
    selectedGranularity = granularity;
    const data = dashboardData.modo_integrado;

    Object.values(charts).forEach(c => {
        try { c.destroy(); } catch(e) {}
    });
    charts = {};

    const kpiComercial = data.kpis.comercial;
    const kpiMargem = data.kpis.margem;
    const kpiImpacto = data.impacto;

    document.getElementById('exec-kpi-receita').textContent = formatBRL(kpiComercial.receita_bruta);
    document.getElementById('exec-kpi-pedidos').textContent = `${formatNum(kpiComercial.pedidos_aprovados)} pedidos faturados`;

    document.getElementById('exec-kpi-margem').textContent = formatBRL(kpiMargem.margem_contribuicao);
    document.getElementById('exec-kpi-margem-pct').textContent = `${formatPctRigor(kpiMargem.margem_pct_percentual ?? kpiMargem.margem_pct)} de retenção sobre faturamento`;

    document.getElementById('exec-kpi-ebitda').textContent = formatBRL(kpiImpacto.recuperacao_ebitda);
    document.getElementById('exec-kpi-payback').textContent = formatPaybackRigor(kpiImpacto.payback_global_meses ?? kpiImpacto.payback_meses);

    // Gráfico Temporal Principal
    const ctxMain = document.getElementById('mainChart').getContext('2d');
    const periods = data.temporal[granularity] || [];
    const labelsMain = periods.map(d => d.periodo);
    const secondary = document.getElementById('secondary_toggle').value;

    let mainDatasets = [];
    let mainScales = {};

    if (secondary === 'cac_roas') {
        mainDatasets = [
            { type: 'line', label: 'ROAS', data: periods.map(d => d.roas || 0), borderColor: '#10b981', backgroundColor: '#10b981', borderWidth: 2.5, tension: 0.3, pointRadius: 4, yAxisID: 'y_roas', order: 1 },
            { type: 'bar', label: 'CAC (R$)', data: periods.map(d => d.cac || 0), backgroundColor: '#ef4444', borderRadius: 4, yAxisID: 'y_cac', order: 2 }
        ];
        mainScales = {
            y_cac: { type: 'linear', beginAtZero: true, position: 'left', title: { display: true, text: 'CAC Médio' }, ticks: { callback: (v) => formatBRL(v) } },
            y_roas: { type: 'linear', beginAtZero: true, position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: 'ROAS' }, ticks: { callback: (v) => (v || 0).toFixed(1) + 'x' } }
        };
    } else if (secondary === 'volume_csat') {
        mainDatasets = [
            { type: 'line', label: 'Nota CSAT Média', data: periods.map(d => d.csat_medio || 0), borderColor: '#f59e0b', backgroundColor: '#f59e0b', borderWidth: 2.5, tension: 0.3, pointRadius: 4, yAxisID: 'y_csat', order: 1 },
            { type: 'bar', label: 'Volume de Tickets', data: periods.map(d => d.volume_tickets || 0), backgroundColor: '#8b5cf6', borderRadius: 4, yAxisID: 'y_vol', order: 2 }
        ];
        mainScales = {
            y_vol: { type: 'linear', beginAtZero: true, position: 'left', title: { display: true, text: 'Qtd. Chamados' }, ticks: { callback: (v) => formatNum(v) } },
            y_csat: { type: 'linear', min: 0, max: 5, position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: 'CSAT (1 a 5)' }, ticks: { callback: (v) => (v || 0).toFixed(1) } }
        };
    } else if (secondary === 'receita_liquida_perdida') {
        mainDatasets = [
            { type: 'line', label: 'Receita Perdida (Devoluções + Frete Reverso)', data: periods.map(d => d.receita_perdida || 0), borderColor: '#ef4444', backgroundColor: '#ef4444', borderWidth: 2.5, tension: 0.3, pointRadius: 4, yAxisID: 'y', order: 1 },
            { type: 'bar', label: 'Margem de Contribuição', data: periods.map(d => d.margem_contribuicao || 0), backgroundColor: '#3b82f6', borderRadius: 4, yAxisID: 'y', order: 2 }
        ];
        mainScales = { y: { beginAtZero: true, ticks: { callback: (v) => formatBRL(v) } } };
    } else {
        const cfg = {
            margem: ['Margem de Contribuição', periods.map(d => d.margem_contribuicao), '#10b981'],
            ticket: ['Ticket Médio', periods.map(d => d.ticket_medio), '#f59e0b']
        }[secondary] || ['Margem de Contribuição', periods.map(d => d.margem_contribuicao), '#10b981'];

        mainDatasets = [
            { type: 'line', label: cfg[0], data: cfg[1], borderColor: cfg[2], backgroundColor: cfg[2], borderWidth: 2.5, tension: 0.3, pointRadius: 4, yAxisID: secondary === 'ticket' ? 'y_line' : 'y', order: 1 },
            { type: 'bar', label: 'Receita Bruta Total', data: periods.map(d => d.receita_bruta), backgroundColor: '#3b82f6', borderRadius: 4, yAxisID: 'y', order: 2 }
        ];
        mainScales = {
            y: { beginAtZero: true, position: 'left', title: { display: true, text: 'Faturamento Bruto' }, ticks: { callback: (v) => formatBRL(v) } }
        };
        if (secondary === 'ticket') {
            mainScales.y_line = { beginAtZero: true, position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: 'Ticket Médio' }, ticks: { callback: (v) => formatBRL(v) } };
        }
    }

    charts.main = new Chart(ctxMain, {
        type: 'bar',
        data: { labels: labelsMain, datasets: mainDatasets },
        options: { responsive: true, maintainAspectRatio: false, scales: mainScales }
    });

    // Gráfico RFM
    charts.rfm = new Chart(document.getElementById('rfmChart').getContext('2d'), {
        type: 'doughnut',
        data: {
            labels: data.rfm.map(d => d.segmento),
            datasets: [{
                data: data.rfm.map(d => d.quantidade),
                backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#64748b']
            }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right' } } }
    });

    // Impacto Financeiro Consolidado
    charts.impacto = new Chart(document.getElementById('impactoExecutiveChart').getContext('2d'), {
        type: 'bar',
        data: {
            labels: data.impacto.acoes.map(a => a.nome),
            datasets: [{
                data: data.impacto.acoes.map(a => a.valor),
                backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444'],
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true, ticks: { callback: (v) => formatBRL(v) } } }
        }
    });

    renderArea(data, selectedArea);

    // Gráficos de Canais
    const canaisData = data.canais || [];
    charts.canal = new Chart(document.getElementById('canalChart').getContext('2d'), {
        type: 'bar',
        data: {
            labels: canaisData.map(d => d.canal),
            datasets: [
                { label: 'Investimento em Mídia', data: canaisData.map(d => d.investimento), backgroundColor: '#f59e0b' },
                { label: 'Receita Efetivada de Vendas', data: canaisData.map(d => d.receita_liquida), backgroundColor: '#2563eb' }
            ]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            scales: { x: { beginAtZero: true, ticks: { callback: (v) => formatBRL(v) } } }
        }
    });

    charts.canalRfm = new Chart(document.getElementById('canalRfmChart').getContext('2d'), {
        type: 'bar',
        data: {
            labels: data.canais_rfm.map(d => d.canal),
            datasets: [
                { type: 'line', label: 'Ticket Médio', data: data.canais_rfm.map(d => d.ticket_medio || 0), borderColor: '#0f172a', borderWidth: 2, tension: 0.3, pointRadius: 4, yAxisID: 'y1', order: 1 },
                { type: 'bar', label: 'Campeão', data: data.canais_rfm.map(d => d['Campeão'] || 0), backgroundColor: '#10b981', stack: 'rfm', yAxisID: 'y', order: 2 },
                { type: 'bar', label: 'Fiel', data: data.canais_rfm.map(d => d['Fiel'] || 0), backgroundColor: '#3b82f6', stack: 'rfm', yAxisID: 'y', order: 2 },
                { type: 'bar', label: 'Promissor', data: data.canais_rfm.map(d => d['Promissor'] || 0), backgroundColor: '#8b5cf6', stack: 'rfm', yAxisID: 'y', order: 2 },
                { type: 'bar', label: 'Em Risco', data: data.canais_rfm.map(d => d['Em Risco'] || 0), backgroundColor: '#f59e0b', stack: 'rfm', yAxisID: 'y', order: 2 },
                { type: 'bar', label: 'Hibernando', data: data.canais_rfm.map(d => d['Hibernando'] || 0), backgroundColor: '#94a3b8', stack: 'rfm', yAxisID: 'y', order: 2 },
                { type: 'bar', label: 'Churn', data: data.canais_rfm.map(d => d['Churn'] || 0), backgroundColor: '#ef4444', stack: 'rfm', yAxisID: 'y', order: 2 }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: true, stacked: true, position: 'left' },
                y1: { beginAtZero: true, position: 'right', grid: { drawOnChartArea: false }, ticks: { callback: (val) => formatBRL(val) } }
            }
        }
    });

    renderCategoryTable(data);

    // SKUs
    const products = data.produtos_ordenados || [];
    document.getElementById('product-count').textContent = `${formatNum(products.length)} produtos analisados`;
    document.getElementById('products-list').innerHTML = products.map((product, index) => `
        <tr class="hover:bg-slate-50/80 transition-colors">
            <td class="px-3 py-2.5 truncate max-w-[240px]" title="${product.produto}">
                <span class="mr-2 font-mono text-xs text-slate-400 font-bold">${index + 1}</span>
                <span class="font-medium text-slate-900">${product.produto}</span>
            </td>
            <td class="px-3 py-2.5 text-right font-mono font-bold ${product.rentabilidade < 0 ? 'text-red-600' : 'text-emerald-700'}">${formatPct(product.rentabilidade)}</td>
            <td class="px-3 py-2.5 text-right font-mono">${formatBRL(product.faturamento)}</td>
            <td class="px-3 py-2.5 text-right font-mono">${formatBRL(product.margem)}</td>
            <td class="px-3 py-2.5">${product.status_estoque || 'Disponível'}</td>
        </tr>`).join('');
}

function renderCategoryTable(data) {
    const catData = data.saude_categorias || [];
    const catView = document.getElementById('categoria_view_toggle')?.value || 'saude';
    const theadCat = document.getElementById('categoria-thead');
    const tbodyCat = document.getElementById('categoria-tbody');
    const titleCat = document.getElementById('cat-table-title');
    const subtitleCat = document.getElementById('cat-table-subtitle');

    if (catView === 'sangria') {
        titleCat.textContent = 'Diagnóstico de Margem & Sangria Comercial por Categoria';
        subtitleCat.textContent = 'Mapeia descontos excessivos, fretes absorvidos e pedidos com margem negativa.';
        theadCat.innerHTML = `
            <tr>
                <th class="px-3 py-2.5">Categoria</th>
                <th class="px-3 py-2.5 text-right">Receita Bruta</th>
                <th class="px-3 py-2.5 text-right">Margem Contribuição</th>
                <th class="px-3 py-2.5 text-right">Desconto Concedido</th>
                <th class="px-3 py-2.5 text-right">Custo de Frete</th>
                <th class="px-3 py-2.5 text-center">Pedidos Margem Neg.</th>
                <th class="px-3 py-2.5 text-right">Receita Perdida</th>
            </tr>`;
        tbodyCat.innerHTML = catData.map(c => `
            <tr class="hover:bg-slate-50/80 transition-colors">
                <td class="px-3 py-3 font-semibold text-slate-900">${c.categoria}</td>
                <td class="px-3 py-3 text-right font-mono">${formatBRL(c.receita_bruta)}</td>
                <td class="px-3 py-3 text-right font-mono text-emerald-700 font-bold">${formatBRL(c.margem_contribuicao)} (${formatPct(c.margem_pct)})</td>
                <td class="px-3 py-3 text-right font-mono text-amber-700">${formatBRL(c.desconto_reais)} (${formatPct(c.desconto_pct)})</td>
                <td class="px-3 py-3 text-right font-mono text-slate-600">${formatBRL(c.custo_frete)}</td>
                <td class="px-3 py-3 text-center font-mono">
                    <span class="px-2 py-0.5 rounded text-xs font-bold ${c.pedidos_margem_neg > 50 ? 'bg-red-100 text-red-700 border border-red-200' : 'bg-slate-100 text-slate-700'}">
                        ${c.pedidos_margem_neg} (${formatPct(c.pct_pedidos_margem_neg)})
                    </span>
                </td>
                <td class="px-3 py-3 text-right font-mono text-red-600 font-semibold">${formatBRL(c.receita_perdida)}</td>
            </tr>`).join('');
    } else if (catView === 'turnover') {
        titleCat.textContent = 'Eficiência de Capital & Giro de Estoque por Categoria';
        subtitleCat.textContent = 'Identifica estoque estagnado, tempo de cobertura e capital imobilizado no armazém.';
        theadCat.innerHTML = `
            <tr>
                <th class="px-3 py-2.5">Categoria</th>
                <th class="px-3 py-2.5 text-right">Unidades Vendidas</th>
                <th class="px-3 py-2.5 text-right">Estoque Físico</th>
                <th class="px-3 py-2.5 text-center">Giro</th>
                <th class="px-3 py-2.5 text-center">Cobertura</th>
                <th class="px-3 py-2.5 text-right">Capital Parado (Custo)</th>
                <th class="px-3 py-2.5 text-right">Volume (m³)</th>
            </tr>`;
        tbodyCat.innerHTML = catData.map(c => `
            <tr class="hover:bg-slate-50/80 transition-colors">
                <td class="px-3 py-3 font-semibold text-slate-900">${c.categoria}</td>
                <td class="px-3 py-3 text-right font-mono">${formatNum(c.quantidade_vendida)} un</td>
                <td class="px-3 py-3 text-right font-mono font-medium">${formatNum(c.estoque_fisico)} un</td>
                <td class="px-3 py-3 text-center font-mono font-bold ${c.giro_estoque < 0.05 ? 'text-purple-700' : 'text-slate-700'}">
                    ${(c.giro_estoque || 0).toFixed(2)}x
                </td>
                <td class="px-3 py-3 text-center font-mono">
                    <span class="px-2 py-0.5 rounded text-xs font-semibold ${c.meses_cobertura > 100 ? 'bg-purple-100 text-purple-700' : 'bg-slate-100 text-slate-700'}">
                        ${(c.meses_cobertura || 0).toFixed(0)} meses
                    </span>
                </td>
                <td class="px-3 py-3 text-right font-mono font-bold text-slate-800">${formatBRL(c.valor_estoque_custo)}</td>
                <td class="px-3 py-3 text-right font-mono text-slate-600">${formatNum((c.volume_total_m3 || 0).toFixed(0))}</td>
            </tr>`).join('');
    } else {
        titleCat.textContent = 'Saúde Operacional & Ruptura por Categoria';
        subtitleCat.textContent = 'Diagnóstico cruzado de faturamento, perda por falta de produto e índice de trocas.';
        theadCat.innerHTML = `
            <tr>
                <th class="px-3 py-2.5">Categoria</th>
                <th class="px-3 py-2.5 text-right">Receita Bruta</th>
                <th class="px-3 py-2.5 text-right">Margem %</th>
                <th class="px-3 py-2.5 text-center">Ruptura (SKUs)</th>
                <th class="px-3 py-2.5 text-center">Giro</th>
                <th class="px-3 py-2.5 text-center">Taxa Devolução</th>
                <th class="px-3 py-2.5">Ação Recomendada</th>
            </tr>`;
        tbodyCat.innerHTML = catData.map(c => `
            <tr class="hover:bg-slate-50/80 transition-colors">
                <td class="px-3 py-3 font-semibold text-slate-900">${c.categoria}</td>
                <td class="px-3 py-3 text-right font-mono font-medium">${formatBRL(c.receita_bruta)}</td>
                <td class="px-3 py-3 text-right font-mono text-emerald-700 font-semibold">${formatPct(c.margem_pct)}</td>
                <td class="px-3 py-3 text-center font-mono">
                    <span class="px-2 py-0.5 rounded text-xs font-bold ${c.skus_ruptura > 10 ? 'bg-red-100 text-red-700 border border-red-200' : 'bg-slate-100 text-slate-600'}">
                        ${c.skus_ruptura} SKU${c.skus_ruptura !== 1 ? 's' : ''}
                    </span>
                </td>
                <td class="px-3 py-3 text-center font-mono font-medium ${c.giro_estoque < 0.05 ? 'text-purple-700 font-bold' : 'text-slate-600'}">
                    ${(c.giro_estoque || 0).toFixed(2)}x
                </td>
                <td class="px-3 py-3 text-center font-mono ${c.taxa_devolucao > 0.15 ? 'text-red-600 font-bold' : 'text-slate-600'}">
                    ${formatPct(c.taxa_devolucao)}
                </td>
                <td class="px-3 py-3">
                    <span class="inline-flex items-center text-xs font-medium text-slate-600">${c.acao_recomendada}</span>
                </td>
            </tr>`).join('');
    }
}

// ================= EXTENSÕES DE RIGOR & METADADOS =================
function renderRigorExtensions(data) {
    if (!data) return;
    renderJsonPathPlaceholders(data);
    renderRigorHeader(data);
    renderDynamicRoadmap(data);
    renderImpactDetailPlaceholders(data);
    renderReportRigorMeta(data);
    renderScenariosRigor(data);
    renderExtraMetrics(data);
}

function windowLabelRigor(data) {
    const inicio = getPathRigor(data, 'meta.janela_vendas_inicio', getPathRigor(data, 'modo_integrado.vendas_iniciadas_em', ''));
    const fim = getPathRigor(data, 'meta.janela_vendas_fim', getPathRigor(data, 'modo_integrado.vendas_encerradas_em', ''));
    const meses = getPathRigor(data, 'meta.janela_meses', getPathRigor(data, 'modo_integrado.janela_meses', null));

    let label = '';
    if (inicio && fim) label += `Janela temporal: ${formatDateRigor(inicio)} a ${formatDateRigor(fim)}`;
    if (meses !== null) label += ` · ${Number(meses).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} meses`;
    return label || 'Janela temporal auditada';
}

function formatAutoRigor(format, value) {
    if (format === 'brl') return formatBRLRigor(value);
    if (format === 'payback') return formatPaybackRigor(value);
    if (format === 'pct') return formatPctRigor(value);
    if (format === 'date') return formatDateRigor(value);
    if (format === 'num') return (value === null || isNaN(value)) ? '—' : formatNum(value);
    return value ?? '—';
}

function renderJsonPathPlaceholders(data) {
    document.querySelectorAll('[data-json-path]').forEach((el) => {
        const path = el.getAttribute('data-json-path');
        const format = el.getAttribute('data-format') || '';
        const value = getPathRigor(data, path, null);
        el.textContent = formatAutoRigor(format, value);
    });
}

function renderRigorHeader(data) {
    const windowLabel = windowLabelRigor(data);
    const rigorWindow = document.getElementById('rigor-window');
    if (rigorWindow) rigorWindow.textContent = windowLabel;

    document.querySelectorAll('[data-window-label]').forEach(el => el.textContent = windowLabel);

    const source = document.getElementById('rigor-source');
    if (source) {
        const updatedAt = getPathRigor(data, 'meta.atualizado_em', null);
        source.textContent = updatedAt ? `Atualizado em ${new Date(updatedAt).toLocaleDateString('pt-BR')}` : 'Base Consolidada Auditada';
    }
}

function renderDynamicRoadmap(data) {
    const tbody = document.getElementById('roadmap-tbody');
    if (!tbody) return;

    let roadmap = getPathRigor(data, 'modo_integrado.roadmap', []) || [];

    if (!roadmap.length) {
        const actions = getPathRigor(data, 'modo_integrado.impacto.acoes', []) || [];
        roadmap = actions.map((action, index) => ({
            ordem: index + 1,
            iniciativa: action.iniciativa || action.nome,
            area: action.area || '—',
            horizonte: '—',
            status: 'Planejamento',
            ganho_na_janela: action.valor,
            progresso_pct: 0
        }));
    }

    tbody.innerHTML = roadmap.map((item) => {
        const title = item.iniciativa || item.nome || '—';
        const ordem = item.ordem || '';
        const area = item.area || '—';
        const horizonte = item.horizonte || '—';
        const status = item.status || 'Planejamento';
        const ganho = item.ganho_na_janela ?? item.valor ?? null;
        const progresso = item.progresso_pct ?? 0;

        return `
            <tr class="hover:bg-slate-50/80 transition-colors">
                <td class="px-4 py-3 font-semibold text-slate-900">${ordem ? `${ordem}. ` : ''}${title}</td>
                <td class="px-4 py-3"><span class="px-2 py-0.5 bg-slate-100 rounded text-slate-700 font-medium">${area}</span></td>
                <td class="px-4 py-3 font-mono">${horizonte}</td>
                <td class="px-4 py-3"><span class="px-2.5 py-1 bg-slate-100 text-slate-800 rounded-full font-bold text-[11px]">${status}</span></td>
                <td class="px-4 py-3 text-right font-mono font-bold text-emerald-700">${formatBRLRigor(ganho)}</td>
                <td class="px-4 py-3 text-right font-mono font-bold text-slate-500">${formatPctRigor(progresso)}</td>
            </tr>
        `;
    }).join('');
}

function renderImpactDetailPlaceholders(data) {
    const impact = getPathRigor(data, 'modo_integrado.impacto', {}) || {};

    document.querySelectorAll('[data-impact-global]').forEach((el) => {
        const key = el.getAttribute('data-impact-global');
        const value = impact[key];
        el.textContent = String(key).toLowerCase().includes('payback') ? formatPaybackRigor(value) : formatBRLRigor(value);
    });
}

function renderReportRigorMeta(data) {
    const windowEl = document.getElementById('rep-doc-window');
    if (windowEl) windowEl.textContent = windowLabelRigor(data);
    const emissaoEl = document.getElementById('rep-doc-emissao');
    if (emissaoEl) emissaoEl.textContent = new Date().toLocaleDateString('pt-BR');
}

function renderScenariosRigor(data) {
    const container = document.getElementById('scenarios-rigor');
    if (!container) return;

    const cenarios = getPathRigor(data, 'modo_integrado.cenarios', null);
    if (cenarios && typeof cenarios === 'object') {
        const rows = Object.entries(cenarios).map(([name, c]) => ({
            'Cenário': name,
            'Recuperação EBITDA': formatBRLRigor(c.resumo.recuperacao_ebitda),
            'Economia Opex': formatBRLRigor(c.resumo.economia_opex_total),
            'Capital Liberado': formatBRLRigor(c.resumo.capital_desrepresado),
            'Payback': formatPaybackRigor(c.resumo.payback_global_meses)
        }));

        const keys = Object.keys(rows[0]);
        container.innerHTML = `
            <table class="min-w-full text-xs">
                <thead><tr class="border-b border-slate-200">${keys.map(k => `<th class="py-1.5 px-2">${k}</th>`).join('')}</tr></thead>
                <tbody class="divide-y divide-slate-100">${rows.map(r => `<tr>${keys.map(k => `<td class="py-1.5 px-2">${r[k]}</td>`).join('')}</tr>`).join('')}</tbody>
            </table>`;
    }
}

function renderExtraMetrics(data) {
    const excess = getPathRigor(data, 'modo_integrado.hipoteses.sobre_estoque_h4', []) || [];
    const bundleUnits = excess.reduce((acc, item) => acc + Number(item.estoque_disponivel || 0), 0);
    document.querySelectorAll('[data-bundles-unidades]').forEach(el => el.textContent = formatNum(bundleUnits));

    const periods = getPathRigor(data, 'modo_integrado.temporal.mes', []) || [];
    const pedidosDev = periods.reduce((acc, p) => acc + Number(p.pedidos_devolvidos || 0), 0);
    document.querySelectorAll('[data-devolucoes-pedidos]').forEach(el => el.textContent = formatNum(pedidosDev));

    const wismoPct = getPathRigor(data, 'modo_integrado.kpis.produtividade.potencial_automacao_wismo_pct', null);
    document.querySelectorAll('[data-wismo-percentual]').forEach(el => el.textContent = formatPctRigor(wismoPct));
}

// ================= LISTENERS DE EVENTOS =================
document.getElementById('gran_toggle')?.addEventListener('change', (e) => renderDashboard(e.target.value));
document.getElementById('area_toggle')?.addEventListener('change', (e) => {
    selectedArea = e.target.value;
    if (dashboardData) renderArea(dashboardData.modo_integrado, selectedArea);
});
document.getElementById('secondary_toggle')?.addEventListener('change', () => renderDashboard(selectedGranularity));
document.getElementById('canal_toggle')?.addEventListener('change', () => renderDashboard(selectedGranularity));
document.getElementById('categoria_view_toggle')?.addEventListener('change', () => {
    if (dashboardData) renderCategoryTable(dashboardData.modo_integrado);
});

document.addEventListener('DOMContentLoaded', init);