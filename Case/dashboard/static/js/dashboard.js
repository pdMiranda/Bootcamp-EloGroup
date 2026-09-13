/**
 * Dashboard Executivo - JavaScript
 * Gerencia gráficos, dados e interações
 */

// Estado global
let mainChart = null;
let roasChart = null;
let segmentosChart = null;
let produtosChart = null;
let canalChart = null;

let currentKPI = 'receita_bruta';
let currentGranularity = 'day';
let recentMode = false;

// Inicialização
document.addEventListener('DOMContentLoaded', function() {
    initializeEventListeners();
    loadDashboardData();
});

// Inicializa event listeners
function initializeEventListeners() {
    // Seletor de KPI
    document.getElementById('kpiSelect').addEventListener('change', function(e) {
        currentKPI = e.target.value;
        updateMainChart();
    });

    // Seletor de granularidade
    document.getElementById('granularitySelect').addEventListener('change', function(e) {
        currentGranularity = e.target.value;
        loadDashboardData();
    });

    // Toggle de dados recentes
    document.getElementById('recentToggle').addEventListener('change', function(e) {
        recentMode = e.target.checked;
        loadDashboardData();
    });

    // Tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const tabId = this.dataset.tab;
            
            // Remove active de todos
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
            
            // Adiciona active no selecionado
            this.classList.add('active');
            document.getElementById(`tab-${tabId}`).classList.add('active');
        });
    });
}

// Carrega dados do dashboard
async function loadDashboardData() {
    try {
        const params = new URLSearchParams({
            recent: recentMode,
            granularity: currentGranularity,
            kpi: currentKPI
        });

        const response = await fetch(`/api/dashboard-data?${params}`);
        const data = await response.json();

        updateKPIs(data.kpis);
        updateHighlightCards(data);
        updateMainChart(data.chart_data);
        updateSecondaryCharts(data);
        updateDetailTabs(data.kpis);
        updateInsights(data.insights);
        updatePeriodInfo(data.periodo);
        updateWarning(data.data_warning);

    } catch (error) {
        console.error('Erro ao carregar dados:', error);
    }
}

// Atualiza KPIs principais
function updateKPIs(kpis) {
    // Comercial
    updateKPIValue('receita_bruta', kpis.comercial.receita_bruta, 'currency');
    updateKPIVariation('receita_bruta', kpis.comercial.receita_bruta_var);
    
    updateKPIValue('pedidos', kpis.comercial.pedidos, 'number');
    updateKPIVariation('pedidos', kpis.comercial.pedidos_var);
    
    updateKPIValue('ticket_medio', kpis.comercial.ticket_medio, 'currency');
    updateKPIVariation('ticket_medio', kpis.comercial.ticket_medio_var);
    
    updateKPIValue('conversao', kpis.comercial.conversao, 'percent');
    updateKPIVariation('conversao', kpis.comercial.conversao_var);
    
    // Margem
    updateKPIValue('margem_contribuicao', kpis.margem.margem_contribuicao, 'currency');
    updateKPIVariation('margem_contribuicao', kpis.margem.margem_contribuicao_var);
    
    updateKPIValue('margem_percentual', kpis.margem.margem_percentual, 'percent');
    updateKPIVariation('margem_percentual', kpis.margem.margem_percentual_var);
}

// Atualiza cards de destaque
function updateHighlightCards(data) {
    document.getElementById('melhor_canal_nome').textContent = data.melhor_canal.canal;
    document.getElementById('melhor_canal_roas').textContent = data.melhor_canal.roas.toFixed(2);
    
    document.getElementById('top_segmento_nome').textContent = data.top_segmento.segmento;
    document.getElementById('top_segmento_clientes').textContent = data.top_segmento.clientes.toLocaleString('pt-BR');
}

// Atualiza gráfico principal
function updateMainChart(chartData = null) {
    const ctx = document.getElementById('mainChart').getContext('2d');
    
    if (mainChart) {
        mainChart.destroy();
    }

    const labels = chartData.map(d => d.data);
    const receitaData = chartData.map(d => d.receita_bruta);
    const margemData = chartData.map(d => d.margem_contribuicao);

    mainChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Receita Bruta',
                    data: receitaData,
                    borderColor: '#4299e1',
                    backgroundColor: 'rgba(66, 153, 225, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    yAxisID: 'y'
                },
                {
                    label: 'Margem de Contribuição',
                    data: margemData,
                    borderColor: '#38a169',
                    backgroundColor: 'rgba(56, 161, 105, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    position: 'top',
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const value = context.raw;
                            return `${context.dataset.label}: R$ ${value.toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Receita Bruta (R$)'
                    },
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Margem (R$)'
                    },
                    grid: {
                        drawOnChartArea: false
                    }
                }
            }
        }
    });
}

// Atualiza gráficos secundários
function updateSecondaryCharts(data) {
    // ROAS por Canal
    const roasCtx = document.getElementById('roasChart').getContext('2d');
    if (roasChart) roasChart.destroy();
    
    roasChart = new Chart(roasCtx, {
        type: 'bar',
        data: {
            labels: data.roas_por_canal.map(d => d.canal),
            datasets: [{
                label: 'ROAS',
                data: data.roas_por_canal.map(d => d.roas),
                backgroundColor: '#d69e2e',
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'ROAS'
                    }
                }
            }
        }
    });

    // Segmentos
    const segCtx = document.getElementById('segmentosChart').getContext('2d');
    if (segmentosChart) segmentosChart.destroy();
    
    segmentosChart = new Chart(segCtx, {
        type: 'doughnut',
        data: {
            labels: data.segmentos.map(d => d.segmento),
            datasets: [{
                data: data.segmentos.map(d => d.clientes),
                backgroundColor: [
                    '#4299e1',
                    '#38a169',
                    '#d69e2e',
                    '#805ad5',
                    '#ed64a6'
                ],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right'
                }
            }
        }
    });

    // Top Produtos
    const prodCtx = document.getElementById('produtosChart').getContext('2d');
    if (produtosChart) produtosChart.destroy();
    
    produtosChart = new Chart(prodCtx, {
        type: 'bar',
        data: {
            labels: data.top_produtos.map(d => d.produto.substring(0, 20) + '...'),
            datasets: [{
                label: 'Quantidade Vendida',
                data: data.top_produtos.map(d => d.quantidade),
                backgroundColor: '#319795',
                borderRadius: 4
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    beginAtZero: true
                }
            }
        }
    });

    // Receita por Canal
    const canCtx = document.getElementById('canalChart').getContext('2d');
    if (canalChart) canalChart.destroy();
    
    canalChart = new Chart(canCtx, {
        type: 'pie',
        data: {
            labels: data.vendas_por_canal.map(d => d.canal),
            datasets: [{
                data: data.vendas_por_canal.map(d => d.receita),
                backgroundColor: [
                    '#4299e1',
                    '#38a169',
                    '#d69e2e',
                    '#805ad5',
                    '#ed64a6',
                    '#319795',
                    '#9f7aea'
                ],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right'
                }
            }
        }
    });
}

// Atualiza abas de detalhes
function updateDetailTabs(kpis) {
    // Comercial
    updateDetailValue('receita_bruta', kpis.comercial.receita_bruta, 'currency');
    updateDetailValue('pedidos', kpis.comercial.pedidos, 'number');
    updateDetailValue('ticket_medio', kpis.comercial.ticket_medio, 'currency');
    updateDetailValue('conversao', kpis.comercial.conversao, 'percent');
    
    // Margem
    updateDetailValue('margem_contribuicao', kpis.margem.margem_contribuicao, 'currency');
    updateDetailValue('margem_percentual', kpis.margem.margem_percentual, 'percent');
    updateDetailValue('desconto_medio', kpis.margem.desconto_medio, 'currency');
    updateDetailValue('frete_medio', kpis.margem.frete_medio, 'currency');
    updateDetailValue('rentabilidade_sku', kpis.margem.rentabilidade_sku, 'currency');
    
    // Marketing
    updateDetailValue('cac_medio', kpis.marketing.cac_medio, 'currency');
    updateDetailValue('roas_medio', kpis.marketing.roas_medio, 'number');
    updateDetailValue('conversoes_marketing', kpis.marketing.conversoes_marketing, 'number');
    
    // Cliente
    updateDetailValue('recompra', kpis.cliente.recompra, 'percent');
    updateDetailValue('ltv_medio', kpis.cliente.ltv_medio, 'currency');
    updateDetailValue('churn_rate', kpis.cliente.churn_rate, 'percent');
    updateDetailValue('top_segmento', kpis.cliente.top_segmento, 'text');
    
    // Operações
    updateDetailValue('taxa_devolucao', kpis.operacoes.taxa_devolucao, 'percent');
    updateDetailValue('taxa_ruptura', kpis.operacoes.taxa_ruptura, 'percent');
    updateDetailValue('giro_estoque', kpis.operacoes.giro_estoque, 'number');
    updateDetailValue('lead_time_medio', kpis.operacoes.lead_time_medio, 'number');
    
    // Atendimento
    updateDetailValue('volume_tickets', kpis.atendimento.volume_tickets, 'number');
    updateDetailValue('sla_rate', kpis.atendimento.sla_rate, 'percent');
    updateDetailValue('csat_medio', kpis.atendimento.csat_medio, 'number');
    updateDetailValue('custo_por_ticket', kpis.atendimento.custo_por_ticket, 'currency');
    
    // Produtividade
    updateDetailValue('horas_economizadas', kpis.produtividade.horas_economizadas, 'number');
    updateDetailValue('automacao_potencial', kpis.produtividade.automacao_potencial, 'percent');
    updateDetailValue('retrabalho_horas', kpis.produtividade.retrabalho_horas, 'number');
    updateDetailValue('tempo_resposta_medio_min', kpis.produtividade.tempo_resposta_medio_min, 'number');
    
    // Impacto
    updateDetailValue('ebitda_potencial', kpis.impacto.ebitda_potencial, 'currency');
    updateDetailValue('economia_estimada', kpis.impacto.economia_estimada, 'currency');
    updateDetailValue('receita_protegida', kpis.impacto.receita_protegida, 'currency');
    updateDetailValue('payback_meses', kpis.impacto.payback_meses, 'number');
}

// Atualiza insights
function updateInsights(insights) {
    const container = document.getElementById('insightsContainer');
    container.innerHTML = '';
    
    insights.forEach(insight => {
        const card = document.createElement('div');
        card.className = `insight-card ${insight.tipo}`;
        
        card.innerHTML = `
            <div class="insight-header">
                <span class="insight-title">${insight.titulo}</span>
                <span class="insight-priority ${insight.prioridade}">${insight.prioridade}</span>
            </div>
            <p class="insight-description">${insight.descricao}</p>
            <span class="insight-impact">💡 ${insight.impacto}</span>
        `;
        
        container.appendChild(card);
    });
}

// Atualiza informações de período
function updatePeriodInfo(periodo) {
    const start = new Date(periodo.inicio).toLocaleDateString('pt-BR');
    const end = new Date(periodo.fim).toLocaleDateString('pt-BR');
    const modeText = periodo.recent_mode ? '(Últimos 7 dias)' : '(Últimos 30 dias)';
    
    document.getElementById('periodRange').textContent = 
        `Período: ${start} a ${end} ${modeText}`;
}

// Atualiza warning de lacuna de dados
function updateWarning(warning) {
    const warningBox = document.getElementById('dataWarning');
    const warningText = document.getElementById('warningText');
    
    if (warning.has_gap) {
        warningBox.style.display = 'flex';
        warningText.textContent = warning.message;
    } else {
        warningBox.style.display = 'none';
    }
}

// Helpers
function updateKPIValue(key, value, format) {
    const element = document.getElementById(`kpi_${key}`);
    if (element) {
        element.textContent = formatValue(value, format);
    }
}

function updateKPIVariation(key, variation) {
    const element = document.getElementById(`var_${key}`);
    if (element && variation !== undefined) {
        const signal = variation > 0 ? '+' : '';
        element.textContent = `${signal}${variation.toFixed(1)}%`;
        element.className = `kpi-variation ${variation > 0 ? 'positive' : variation < 0 ? 'negative' : 'neutral'}`;
    } else if (element) {
        element.textContent = '';
    }
}

function updateDetailValue(key, value, format) {
    const element = document.getElementById(`det_${key}`);
    if (element) {
        element.textContent = formatValue(value, format);
    }
}

function formatValue(value, format) {
    if (value === undefined || value === null) return '-';
    
    switch (format) {
        case 'currency':
            return `R$ ${value.toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        case 'percent':
            return `${value.toFixed(2)}%`;
        case 'number':
            return value.toLocaleString('pt-BR');
        default:
            return value.toString();
    }
}
