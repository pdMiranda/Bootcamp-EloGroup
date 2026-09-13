// Estado global
let mainChart = null;
let roasChart = null;
let segmentosChart = null;
let receitaCanalChart = null;
let produtosChart = null;

// Configurações
const API_BASE = '/api';
let currentData = null;
let dataGapWarning = false;

// Inicialização
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    loadData();
    
    // Event listeners
    document.getElementById('kpiSelector').addEventListener('change', updateMainChart);
    document.getElementById('granularitySelector').addEventListener('change', updateMainChart);
    document.getElementById('periodSelector').addEventListener('change', loadData);
    document.getElementById('recentToggle').addEventListener('change', loadData);
});

// Inicializar gráficos
function initCharts() {
    // Main Chart - Evolução Temporal
    const mainCtx = document.getElementById('mainChart').getContext('2d');
    mainChart = new Chart(mainCtx, {
        type: 'line',
        data: { labels: [], datasets: [] },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: ${formatValue(ctx.parsed.y, ctx.dataset.label)}`
                    }
                }
            },
            scales: {
                x: { grid: { display: false } },
                y: { beginAtZero: false, grid: { color: '#f1f5f9' } }
            }
        }
    });

    // ROAS por Canal
    const roasCtx = document.getElementById('roasChart').getContext('2d');
    roasChart = new Chart(roasCtx, {
        type: 'bar',
        data: { labels: [], datasets: [] },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `ROAS: ${ctx.parsed.x.toFixed(2)}`
                    }
                }
            },
            scales: {
                x: { beginAtZero: true, grid: { color: '#f1f5f9' } },
                y: { grid: { display: false } }
            }
        }
    });

    // Segmentos
    const segCtx = document.getElementById('segmentosChart').getContext('2d');
    segmentosChart = new Chart(segCtx, {
        type: 'doughnut',
        data: { labels: [], datasets: [] },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'right' },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.label}: ${ctx.parsed} clientes`
                    }
                }
            }
        }
    });

    // Receita por Canal
    const recCtx = document.getElementById('receitaCanalChart').getContext('2d');
    receitaCanalChart = new Chart(recCtx, {
        type: 'pie',
        data: { labels: [], datasets: [] },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'right' },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.label}: ${formatCurrency(ctx.parsed)}`
                    }
                }
            }
        }
    });

    // Top Produtos
    const prodCtx = document.getElementById('produtosChart').getContext('2d');
    produtosChart = new Chart(prodCtx, {
        type: 'bar',
        data: { labels: [], datasets: [] },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `Vendidos: ${ctx.parsed.y}`
                    }
                }
            },
            scales: {
                x: { grid: { display: false } },
                y: { beginAtZero: true, grid: { color: '#f1f5f9' } }
            }
        }
    });
}

// Carregar dados
async function loadData() {
    const days = document.getElementById('periodSelector').value;
    const recent = document.getElementById('recentToggle').checked;
    
    try {
        const response = await fetch(`${API_BASE}/kpis?days=${days}&recent=${recent}`);
        currentData = await response.json();
        
        updateDashboard(currentData);
        
        // Verificar lacuna de dados
        checkDataGap();
    } catch (error) {
        console.error('Erro ao carregar dados:', error);
    }
}

// Verificar lacuna de dados
async function checkDataGap() {
    try {
        const response = await fetch(`${API_BASE}/dates`);
        const dates = await response.json();
        
        document.getElementById('latestDate').textContent = `Dados até: ${formatDate(dates.latest_date)}`;
        
        if (dates.data_gap_days > 30) {
            dataGapWarning = true;
            const gapEl = document.getElementById('dataGap');
            gapEl.textContent = `⚠️ Lacuna: ${dates.data_gap_days} dias`;
            gapEl.style.display = 'inline-block';
        }
    } catch (error) {
        console.error('Erro ao verificar datas:', error);
    }
}

// Atualizar dashboard
function updateDashboard(data) {
    const kpis = data.kpis;
    
    // Atualizar KPI cards principais
    document.getElementById('receitaBruta').textContent = formatCurrency(kpis.comercial.receita_bruta);
    document.getElementById('margemContribuicao').textContent = formatCurrency(kpis.margem.margem_contribuicao);
    document.getElementById('pedidos').textContent = kpis.comercial.pedidos.toLocaleString('pt-BR');
    document.getElementById('ticketMedio').textContent = formatCurrency(kpis.comercial.ticket_medio);
    document.getElementById('conversao').textContent = `${(kpis.comercial.conversao * 100).toFixed(2)}%`;
    document.getElementById('melhorCanal').textContent = kpis.marketing.melhor_canal;
    document.getElementById('roasCanal').textContent = `ROAS: ${kpis.marketing.melhor_roas.toFixed(2)}`;
    document.getElementById('topSegmento').textContent = kpis.cliente.top_segmento;
    document.getElementById('ltvSegmento').textContent = `LTV: ${formatCurrency(kpis.cliente.ltv)}`;
    document.getElementById('volumeTickets').textContent = kpis.atendimento.volume_tickets.toLocaleString('pt-BR');
    document.getElementById('csatTickets').textContent = `CSAT: ${kpis.atendimento.csat.toFixed(1)}/5 | SLA: ${kpis.atendimento.sla.toFixed(0)}%`;
    
    // Impacto financeiro
    document.getElementById('ebitdaPotencial').textContent = formatCurrency(kpis.impacto.ebitda_potencial);
    document.getElementById('economiaEstimada').textContent = formatCurrency(kpis.impacto.economia_estimada);
    document.getElementById('receitaProtegida').textContent = formatCurrency(kpis.impacto.receita_protegida);
    document.getElementById('payback').textContent = `${kpis.impacto.payback.toFixed(2)}x`;
    
    // Tabelas detalhadas
    document.getElementById('detReceita').textContent = formatCurrency(kpis.comercial.receita_bruta);
    document.getElementById('detPedidos').textContent = kpis.comercial.pedidos.toLocaleString('pt-BR');
    document.getElementById('detTicket').textContent = formatCurrency(kpis.comercial.ticket_medio);
    document.getElementById('detConversao').textContent = `${(kpis.comercial.conversao * 100).toFixed(2)}%`;
    document.getElementById('detMargem').textContent = formatCurrency(kpis.margem.margem_contribuicao);
    document.getElementById('detRentabilidade').textContent = `${kpis.margem.rentabilidade.toFixed(1)}%`;
    
    document.getElementById('detCAC').textContent = formatCurrency(kpis.marketing.cac);
    document.getElementById('detROAS').textContent = kpis.marketing.roas.toFixed(2);
    document.getElementById('detRecompra').textContent = `${kpis.cliente.recompra.toFixed(1)}%`;
    document.getElementById('detLTV').textContent = formatCurrency(kpis.cliente.ltv);
    document.getElementById('detChurn').textContent = `${kpis.cliente.churn.toFixed(1)}%`;
    
    document.getElementById('detDevolucao').textContent = `${kpis.operacoes.taxa_devolucao.toFixed(1)}%`;
    document.getElementById('detRuptura').textContent = `${kpis.operacoes.ruptura.toFixed(1)}%`;
    document.getElementById('detGiro').textContent = kpis.operacoes.giro_estoque.toFixed(2);
    document.getElementById('detLeadTime').textContent = `${kpis.operacoes.lead_time.toFixed(0)} dias`;
    document.getElementById('detSLA').textContent = `${kpis.atendimento.sla.toFixed(0)}%`;
    document.getElementById('detCustoTicket').textContent = formatCurrency(kpis.atendimento.custo_por_ticket);
    
    // Atualizar insights
    updateInsights(data.insights);
    
    // Atualizar gráficos
    updateMainChart();
    updateRoasChart(data.roas_canal);
    updateSegmentosChart(data.segmentos);
    updateReceitaCanalChart(data.receita_canal);
    updateProdutosChart(data.top_produtos);
}

// Atualizar gráfico principal
function updateMainChart() {
    if (!currentData) return;
    
    const kpiType = document.getElementById('kpiSelector').value;
    const granularity = document.getElementById('granularitySelector').value;
    
    let serieData = [];
    let serieMargem = [];
    
    if (kpiType === 'margem_contribuicao') {
        serieData = currentData.serie_temporal.margem;
    } else {
        serieData = currentData.serie_temporal.receita;
    }
    
    // Agrupar por granularidade
    const groupedData = groupByGranularity(serieData, granularity);
    
    mainChart.data.labels = groupedData.map(d => d.label);
    mainChart.data.datasets = [
        {
            label: getKpiLabel(kpiType),
            data: groupedData.map(d => d.valor),
            borderColor: '#667eea',
            backgroundColor: 'rgba(102, 126, 234, 0.1)',
            fill: true,
            tension: 0.4
        }
    ];
    
    mainChart.options.scales.y.ticks = {
        callback: (value) => formatShortValue(value, kpiType)
    };
    
    mainChart.update();
}

// Atualizar gráfico ROAS
function updateRoasChart(roasData) {
    roasChart.data.labels = roasData.map(d => d.canal);
    roasChart.data.datasets = [{
        label: 'ROAS',
        data: roasData.map(d => d.roas),
        backgroundColor: [
            'rgba(102, 126, 234, 0.8)',
            'rgba(118, 75, 162, 0.8)',
            'rgba(245, 158, 11, 0.8)',
            'rgba(16, 185, 129, 0.8)',
            'rgba(59, 130, 246, 0.8)',
            'rgba(239, 68, 68, 0.8)'
        ]
    }];
    roasChart.update();
}

// Atualizar gráfico Segmentos
function updateSegmentosChart(segmentosData) {
    segmentosChart.data.labels = segmentosData.map(d => d.segmento);
    segmentosChart.data.datasets = [{
        data: segmentosData.map(d => d.count),
        backgroundColor: [
            'rgba(102, 126, 234, 0.8)',
            'rgba(118, 75, 162, 0.8)',
            'rgba(245, 158, 11, 0.8)',
            'rgba(16, 185, 129, 0.8)',
            'rgba(59, 130, 246, 0.8)'
        ]
    }];
    segmentosChart.update();
}

// Atualizar gráfico Receita por Canal
function updateReceitaCanalChart(receitaData) {
    receitaCanalChart.data.labels = receitaData.map(d => d.canal);
    receitaCanalChart.data.datasets = [{
        data: receitaData.map(d => d.receita),
        backgroundColor: [
            'rgba(102, 126, 234, 0.8)',
            'rgba(118, 75, 162, 0.8)',
            'rgba(245, 158, 11, 0.8)',
            'rgba(16, 185, 129, 0.8)',
            'rgba(59, 130, 246, 0.8)',
            'rgba(239, 68, 68, 0.8)'
        ]
    }];
    receitaCanalChart.update();
}

// Atualizar gráfico Produtos
function updateProdutosChart(produtosData) {
    produtosChart.data.labels = produtosData.map(d => d.produto.substring(0, 25) + '...');
    produtosChart.data.datasets = [{
        label: 'Quantidade Vendida',
        data: produtosData.map(d => d.quantidade),
        backgroundColor: 'rgba(102, 126, 234, 0.8)'
    }];
    produtosChart.update();
}

// Atualizar insights
function updateInsights(insights) {
    const container = document.getElementById('insightsContainer');
    
    if (!insights || insights.length === 0) {
        container.innerHTML = '<p style="color: #64748b;">Nenhum insight crítico no momento.</p>';
        return;
    }
    
    container.innerHTML = insights.map(insight => `
        <div class="insight-card ${insight.prioridade.toLowerCase()}">
            <div class="insight-header">
                <span class="insight-area">${insight.area}</span>
                <span class="insight-priority ${insight.prioridade.toLowerCase()}">${insight.prioridade}</span>
            </div>
            <div class="insight-problema">${insight.problema}</div>
            <div class="insight-acao"><strong>Ação:</strong> ${insight.acao}</div>
            <div class="insight-impacto">💰 ${insight.impacto}</div>
        </div>
    `).join('');
}

// Utilitários
function groupByGranularity(data, granularity) {
    const groups = {};
    
    data.forEach(item => {
        const date = new Date(item.data);
        let key;
        
        if (granularity === 'dia') {
            key = date.toLocaleDateString('pt-BR');
        } else if (granularity === 'semana') {
            const weekStart = new Date(date.setDate(date.getDate() - date.getDay()));
            key = `Semana ${weekStart.toLocaleDateString('pt-BR')}`;
        } else {
            key = date.toLocaleDateString('pt-BR', { month: 'short', year: '2-digit' });
        }
        
        if (!groups[key]) {
            groups[key] = { label: key, valor: 0, count: 0 };
        }
        groups[key].valor += item.valor;
        groups[key].count++;
    });
    
    return Object.values(groups);
}

function getKpiLabel(kpiType) {
    const labels = {
        'receita_bruta': 'Receita Bruta',
        'margem_contribuicao': 'Margem de Contribuição',
        'pedidos': 'Pedidos',
        'ticket_medio': 'Ticket Médio',
        'conversao': 'Taxa de Conversão'
    };
    return labels[kpiType] || kpiType;
}

function formatCurrency(value) {
    return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

function formatValue(value, type) {
    if (type === 'conversao') {
        return `${(value * 100).toFixed(4)}%`;
    }
    return formatCurrency(value);
}

function formatShortValue(value, type) {
    if (value >= 1000000) {
        return `R$ ${(value / 1000000).toFixed(1)}M`;
    } else if (value >= 1000) {
        return `R$ ${(value / 1000).toFixed(1)}K`;
    }
    return formatCurrency(value);
}

function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('pt-BR');
}
