/** Dashboard Executivo - Lógica JavaScript */

let currentPeriod = 'dia';
let currentKpi = 'receita_bruta';
let useLatestData = false;
let mainChart = null;
let roasChart = null;
let segmentosChart = null;

const formatCurrency = (value) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
const formatNumber = (value, decimals = 0) => new Intl.NumberFormat('pt-BR', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(value);

const updateKpiValue = (id, value) => {
    const element = document.getElementById(`kpi-${id}`);
    if (element) element.textContent = value;
};

const createDeltaElement = (delta) => {
    if (delta === null || delta === undefined) return '';
    const sign = delta >= 0 ? '+' : '';
    const className = delta >= 0 ? 'positive' : 'negative';
    return `<span class="kpi-delta ${className}">${sign}${formatNumber(delta, 1)}%</span>`;
};

const updateKpis = (data) => {
    const kpis = data.kpis;
    
    // Comercial
    updateKpiValue('receita-bruta', formatCurrency(kpis.comercial.receita_bruta));
    updateKpiValue('pedidos', formatNumber(kpis.comercial.pedidos));
    updateKpiValue('ticket-medio', formatCurrency(kpis.comercial.ticket_medio));
    updateKpiValue('conversao', `${formatNumber(kpis.comercial.conversao, 1)}%`);
    
    // Margem
    updateKpiValue('margem-contribuicao', formatCurrency(kpis.margem.margem_contribuicao));
    updateKpiValue('desconto-medio', formatCurrency(kpis.margem.desconto_medio));
    updateKpiValue('frete-medio', formatCurrency(kpis.margem.frete_medio));
    if (kpis.margem.rentabilidade_por_sku && kpis.margem.rentabilidade_por_sku.length > 0) {
        const topSku = kpis.margem.rentabilidade_por_sku[0];
        document.getElementById('kpi-rentabilidade-sku').textContent = `${topSku.sku_id}: ${formatNumber(topSku.rentabilidade_pct, 1)}%`;
    }
    
    // Marketing
    updateKpiValue('cac', formatCurrency(kpis.marketing.cac));
    updateKpiValue('roas', formatNumber(kpis.marketing.roas, 2));
    updateKpiValue('conversoes-marketing', formatNumber(kpis.marketing.conversoes));
    if (kpis.marketing.margem_por_canal && kpis.marketing.margem_por_canal.length > 0) {
        const melhorCanal = kpis.marketing.margem_por_canal.reduce((prev, current) => (current.margem_canal > prev.margem_canal) ? current : prev);
        document.getElementById('kpi-melhor-canal').textContent = melhorCanal.canal;
    }
    
    // Cliente
    updateKpiValue('recompra', `${formatNumber(kpis.cliente.recompra, 1)}%`);
    updateKpiValue('ltv', formatCurrency(kpis.cliente.ltv));
    updateKpiValue('churn', `${formatNumber(kpis.cliente.churn, 1)}%`);
    if (kpis.cliente.segmentos && Object.keys(kpis.cliente.segmentos).length > 0) {
        const topSegmento = Object.entries(kpis.cliente.segmentos).sort((a, b) => b[1] - a[1])[0];
        document.getElementById('kpi-top-segmento').textContent = topSegmento[0];
    }
    
    // Operações
    updateKpiValue('taxa-devolucao', `${formatNumber(kpis.operacoes.taxa_devolucao, 1)}%`);
    updateKpiValue('ruptura', `${formatNumber(kpis.operacoes.ruptura, 1)}%`);
    updateKpiValue('giro-estoque', formatNumber(kpis.operacoes.giro_estoque, 2));
    updateKpiValue('lead-time', `${kpis.operacoes.lead_time} dias`);
    
    // Atendimento
    updateKpiValue('volume-tickets', formatNumber(kpis.atendimento.volume_tickets));
    updateKpiValue('sla', `${formatNumber(kpis.atendimento.sla, 1)}%`);
    updateKpiValue('sentimento', `${formatNumber(kpis.atendimento.sentimento, 1)}/5`);
    updateKpiValue('custo-ticket', formatCurrency(kpis.atendimento.custo_por_ticket));
    
    // Produtividade
    updateKpiValue('horas-economizadas', formatNumber(kpis.produtividade.horas_economizadas, 1));
    updateKpiValue('automacao-potencial', `${formatNumber(kpis.produtividade.automacao_potencial, 1)}%`);
    updateKpiValue('retrabalho-reduzido', formatNumber(kpis.produtividade.retrabalho_reduzido));
    updateKpiValue('tempo-resposta', `${formatNumber(kpis.produtividade.tempo_resposta, 0)} min`);
    
    // Impacto
    updateKpiValue('ebitda-potencial', formatCurrency(kpis.impacto.ebitda_potencial));
    updateKpiValue('economia-estimada', formatCurrency(kpis.impacto.economia_estimada));
    updateKpiValue('receita-protegida', formatCurrency(kpis.impacto.receita_protegida));
    updateKpiValue('payback', `${formatNumber(kpis.impacto.payback, 1)} meses`);
};

const updateMainChart = (chartData) => {
    const ctx = document.getElementById('main-chart').getContext('2d');
    const labels = chartData.data.map(d => {
        const date = new Date(d.periodo);
        if (currentPeriod === 'dia') return date.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
        else if (currentPeriod === 'semana') return date.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
        else return date.toLocaleDateString('pt-BR', { month: '2-digit', year: '2-digit' });
    });
    const values = chartData.data.map(d => d.valor || d.receita_bruta);
    
    const kpiLabels = {
        'receita_bruta': 'Receita Bruta (R$)',
        'margem_contribuicao': 'Margem de Contribuição (R$)',
        'pedidos': 'Pedidos',
        'ticket_medio': 'Ticket Médio (R$)',
        'conversao': 'Conversão (%)'
    };
    
    if (mainChart) mainChart.destroy();
    
    mainChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: kpiLabels[currentKpi] || currentKpi,
                data: values,
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 3,
                pointHoverRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: true, labels: { color: '#f1f5f9', font: { size: 11 } } },
                tooltip: {
                    backgroundColor: '#1e293b',
                    titleColor: '#f1f5f9',
                    bodyColor: '#94a3b8',
                    callbacks: {
                        label: (ctx) => {
                            let value = ctx.parsed.y;
                            if (['receita_bruta', 'ticket_medio', 'margem_contribuicao'].includes(currentKpi)) return formatCurrency(value);
                            if (currentKpi === 'conversao') return `${formatNumber(value, 2)}%`;
                            return formatNumber(value);
                        }
                    }
                }
            },
            scales: {
                x: { grid: { color: '#334155' }, ticks: { color: '#94a3b8', maxRotation: 45 } },
                y: { grid: { color: '#334155' }, ticks: { color: '#94a3b8' } }
            }
        }
    });
};

const updateRoasChart = (roasData) => {
    const ctx = document.getElementById('roas-chart').getContext('2d');
    if (roasChart) roasChart.destroy();
    
    const labels = roasData.map(d => d.canal);
    const roasValues = roasData.map(d => d.roas);
    const investimentoValues = roasData.map(d => d.investimento_reais);
    
    roasChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                { label: 'ROAS', data: roasValues, backgroundColor: '#10b981', yAxisID: 'y' },
                { label: 'Investimento (R$)', data: investimentoValues, backgroundColor: '#3b82f6', yAxisID: 'y1' }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: true, labels: { color: '#f1f5f9', font: { size: 10 } } } },
            scales: {
                x: { grid: { color: '#334155' }, ticks: { color: '#94a3b8', font: { size: 9 } } },
                y: { type: 'linear', display: true, position: 'left', grid: { color: '#334155' }, ticks: { color: '#10b981', font: { size: 9 } } },
                y1: { type: 'linear', display: true, position: 'right', grid: { drawOnChartArea: false }, ticks: { color: '#3b82f6', font: { size: 9 } } }
            }
        }
    });
};

const updateSegmentosChart = (segmentosData) => {
    const ctx = document.getElementById('segmentos-chart').getContext('2d');
    if (segmentosChart) segmentosChart.destroy();
    
    const labels = segmentosData.map(d => d.segmento);
    const counts = segmentosData.map(d => d.count);
    const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];
    
    segmentosChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{ data: counts, backgroundColor: colors.slice(0, labels.length), borderWidth: 0 }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: true, position: 'right', labels: { color: '#f1f5f9', font: { size: 9 } } }
            }
        }
    });
};

const updateTopProducts = (products) => {
    const tbody = document.querySelector('#top-products-table tbody');
    if (!products || products.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5">Nenhum dado disponível</td></tr>';
        return;
    }
    tbody.innerHTML = products.map(p => `
        <tr>
            <td>${p.produto}</td>
            <td>${p.categoria}</td>
            <td>${formatNumber(p.quantidade)}</td>
            <td>${formatCurrency(p.receita_bruta)}</td>
            <td>${formatCurrency(p.margem)}</td>
        </tr>
    `).join('');
};

const updateInsights = (insights) => {
    const container = document.getElementById('insights-container');
    if (!insights || insights.length === 0) {
        container.innerHTML = '<div class="loading">Nenhum insight gerado</div>';
        return;
    }
    const priorityLabels = { alta: 'Alta', media: 'Média', baixa: 'Baixa' };
    container.innerHTML = insights.map(insight => `
        <div class="insight-card ${insight.tipo}">
            <div class="insight-header">
                <span class="insight-title">${insight.titulo}</span>
                <span class="insight-priority ${insight.prioridade}">${priorityLabels[insight.prioridade]}</span>
            </div>
            <p class="insight-description">${insight.descricao}</p>
        </div>
    `).join('');
};

const updatePeriodDisplay = (periodo) => {
    const display = document.getElementById('period-display');
    const startDate = new Date(periodo.inicio);
    const endDate = new Date(periodo.fim);
    const startStr = startDate.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
    const endStr = endDate.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
    display.textContent = `${startStr} a ${endStr}`;
    
    const warningBanner = document.getElementById('data-gap-warning');
    const warningMessage = document.getElementById('data-gap-message');
    if (periodo.data_gap_warning) {
        warningMessage.textContent = periodo.data_gap_warning;
        warningBanner.style.display = 'flex';
    } else {
        warningBanner.style.display = 'none';
    }
};

const loadDashboardData = async () => {
    try {
        const params = new URLSearchParams({ period: currentPeriod, kpi: currentKpi, latest: useLatestData });
        const response = await fetch(`/api/dashboard?${params}`);
        const data = await response.json();
        
        updatePeriodDisplay(data.periodo);
        updateKpis(data);
        updateMainChart(data.chart);
        updateRoasChart(data.roas_canais);
        updateSegmentosChart(data.segmentos_distribuicao);
        updateTopProducts(data.top_produtos);
        updateInsights(data.insights);
        
        const now = new Date();
        document.getElementById('last-update').textContent = `Última atualização: ${now.toLocaleTimeString('pt-BR')}`;
    } catch (error) {
        console.error('Erro ao carregar dados:', error);
        document.getElementById('insights-container').innerHTML = '<div class="insight-card alerta"><p class="insight-description">Erro ao carregar dados. Verifique a conexão.</p></div>';
    }
};

const initEventListeners = () => {
    document.getElementById('kpi-selector').addEventListener('change', (e) => {
        currentKpi = e.target.value;
        loadDashboardData();
    });
    
    document.querySelectorAll('.btn-period').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.btn-period').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentPeriod = btn.dataset.period;
            loadDashboardData();
        });
    });
    
    document.getElementById('latest-data-toggle').addEventListener('change', (e) => {
        useLatestData = e.target.checked;
        loadDashboardData();
    });
};

document.addEventListener('DOMContentLoaded', () => {
    initEventListeners();
    loadDashboardData();
    setInterval(loadDashboardData, 60000);
});
