/**
 * Dashboard Executivo - Lógica JavaScript
 * Comunicação com backend Flask para dados em tempo real
 */

// Estado global
let currentPeriod = 'dia';
let currentKpi = 'receita_bruta';
let useLatestData = false;
let mainChart = null;

// Formatação de moeda
const formatCurrency = (value) => {
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL'
    }).format(value);
};

// Formatação de números
const formatNumber = (value, decimals = 0) => {
    return new Intl.NumberFormat('pt-BR', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    }).format(value);
};

// Calcular variação percentual
const calculateDelta = (current, previous) => {
    if (!previous || previous === 0) return null;
    const delta = ((current - previous) / previous) * 100;
    return delta;
};

// Criar elemento delta
const createDeltaElement = (delta) => {
    if (delta === null) return '<span class="kpi-delta neutral">-</span>';
    
    const sign = delta >= 0 ? '+' : '';
    const className = delta >= 0 ? 'positive' : 'negative';
    return `<span class="kpi-delta ${className}">${sign}${formatNumber(delta, 1)}%</span>`;
};

// Atualizar KPIs na tela
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
        document.getElementById('kpi-rentabilidade-sku').textContent = 
            `${topSku.sku_id}: ${formatNumber(topSku.rentabilidade_pct, 1)}%`;
    }
    
    // Marketing
    updateKpiValue('cac', formatCurrency(kpis.marketing.cac));
    updateKpiValue('roas', formatNumber(kpis.marketing.roas, 2));
    updateKpiValue('conversoes-marketing', formatNumber(kpis.marketing.conversoes));
    
    if (kpis.marketing.margem_por_canal && kpis.marketing.margem_por_canal.length > 0) {
        const melhorCanal = kpis.marketing.margem_por_canal.reduce((prev, current) => 
            (current.margem_canal > prev.margem_canal) ? current : prev
        );
        document.getElementById('kpi-melhor-canal').textContent = melhorCanal.canal;
    }
    
    // Cliente
    updateKpiValue('recompra', `${formatNumber(kpis.cliente.recompra, 1)}%`);
    updateKpiValue('ltv', formatCurrency(kpis.cliente.ltv));
    updateKpiValue('churn', `${formatNumber(kpis.cliente.churn, 1)}%`);
    
    if (kpis.cliente.segmentos && Object.keys(kpis.cliente.segmentos).length > 0) {
        const topSegmento = Object.entries(kpis.cliente.segmentos)
            .sort((a, b) => b[1] - a[1])[0];
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

// Atualizar valor individual de KPI
const updateKpiValue = (id, value) => {
    const element = document.getElementById(`kpi-${id}`);
    if (element) {
        element.textContent = value;
    }
};

// Atualizar deltas (variações)
const updateDeltas = (currentData, previousData) => {
    const deltas = [
        { id: 'receita-bruta', current: currentData.comercial?.receita_bruta, previous: previousData?.comercial?.receita_bruta },
        { id: 'pedidos', current: currentData.comercial?.pedidos, previous: previousData?.comercial?.pedidos },
        { id: 'ticket-medio', current: currentData.comercial?.ticket_medio, previous: previousData?.comercial?.ticket_medio },
        { id: 'conversao', current: currentData.comercial?.conversao, previous: previousData?.comercial?.conversao },
        { id: 'margem-contribuicao', current: currentData.margem?.margem_contribuicao, previous: previousData?.margem?.margem_contribuicao },
        { id: 'cac', current: currentData.marketing?.cac, previous: previousData?.marketing?.cac },
        { id: 'roas', current: currentData.marketing?.roas, previous: previousData?.marketing?.roas },
        { id: 'recompra', current: currentData.cliente?.recompra, previous: previousData?.cliente?.recompra },
        { id: 'churn', current: currentData.cliente?.churn, previous: previousData?.cliente?.churn },
        { id: 'taxa-devolucao', current: currentData.operacoes?.taxa_devolucao, previous: previousData?.operacoes?.taxa_devolucao },
        { id: 'ruptura', current: currentData.operacoes?.ruptura, previous: previousData?.operacoes?.ruptura }
    ];
    
    deltas.forEach(({ id, current, previous }) => {
        const delta = calculateDelta(current, previous);
        const element = document.getElementById(`delta-${id}`);
        if (element) {
            element.outerHTML = createDeltaElement(delta);
            // Re-adicionar o elemento após outerHTML
            const newElement = document.createElement('span');
            newElement.className = `kpi-delta ${delta >= 0 ? 'positive' : 'negative'}`;
            newElement.textContent = delta >= 0 ? `+${formatNumber(delta, 1)}%` : `${formatNumber(delta, 1)}%`;
            element.parentNode.appendChild(newElement);
            element.remove();
        }
    });
};

// Atualizar gráfico principal
const updateChart = (chartData) => {
    const ctx = document.getElementById('main-chart').getContext('2d');
    
    const labels = chartData.data.map(d => {
        const date = new Date(d.periodo);
        if (currentPeriod === 'dia') {
            return date.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
        } else if (currentPeriod === 'semana') {
            return date.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
        } else {
            return date.toLocaleDateString('pt-BR', { month: '2-digit', year: '2-digit' });
        }
    });
    
    const values = chartData.data.map(d => d.valor || d.receita_bruta);
    
    const kpiLabels = {
        'receita_bruta': 'Receita Bruta (R$)',
        'pedidos': 'Pedidos',
        'ticket_medio': 'Ticket Médio (R$)',
        'conversao': 'Conversão (%)',
        'margem_contribuicao': 'Margem de Contribuição (R$)'
    };
    
    if (mainChart) {
        mainChart.destroy();
    }
    
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
                pointRadius: 4,
                pointHoverRadius: 6,
                pointBackgroundColor: '#3b82f6',
                pointBorderColor: '#fff',
                pointBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: '#f1f5f9',
                        font: { size: 12 }
                    }
                },
                tooltip: {
                    backgroundColor: '#1e293b',
                    titleColor: '#f1f5f9',
                    bodyColor: '#94a3b8',
                    borderColor: '#475569',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: false,
                    callbacks: {
                        label: function(context) {
                            let value = context.parsed.y;
                            if (currentKpi === 'receita_bruta' || currentKpi === 'ticket_medio' || currentKpi === 'margem_contribuicao') {
                                return formatCurrency(value);
                            } else if (currentKpi === 'conversao') {
                                return `${formatNumber(value, 2)}%`;
                            }
                            return formatNumber(value);
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: '#334155'
                    },
                    ticks: {
                        color: '#94a3b8',
                        maxRotation: 45,
                        minRotation: 45
                    }
                },
                y: {
                    grid: {
                        color: '#334155'
                    },
                    ticks: {
                        color: '#94a3b8',
                        callback: function(value) {
                            if (currentKpi === 'receita_bruta' || currentKpi === 'ticket_medio' || currentKpi === 'margem_contribuicao') {
                                return `R$ ${formatNumber(value / 1000, 0)}`;
                            }
                            return formatNumber(value);
                        }
                    }
                }
            }
        }
    });
};

// Atualizar tabela de produtos
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

// Atualizar insights
const updateInsights = (insights) => {
    const container = document.getElementById('insights-container');
    
    if (!insights || insights.length === 0) {
        container.innerHTML = '<div class="loading">Nenhum insight gerado</div>';
        return;
    }
    
    const priorityLabels = {
        'alta': 'Alta',
        'media': 'Média',
        'baixa': 'Baixa'
    };
    
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

// Atualizar período no header
const updatePeriodDisplay = (periodo) => {
    const display = document.getElementById('period-display');
    const startDate = new Date(periodo.inicio);
    const endDate = new Date(periodo.fim);
    
    const startStr = startDate.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
    const endStr = endDate.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
    
    display.textContent = `${startStr} a ${endStr}`;
    
    // Atualizar warning de data gap
    const warningBanner = document.getElementById('data-gap-warning');
    const warningMessage = document.getElementById('data-gap-message');
    
    if (periodo.data_gap_warning) {
        warningMessage.textContent = periodo.data_gap_warning;
        warningBanner.style.display = 'flex';
    } else {
        warningBanner.style.display = 'none';
    }
};

// Carregar dados do dashboard
const loadDashboardData = async () => {
    try {
        const params = new URLSearchParams({
            period: currentPeriod,
            kpi: currentKpi,
            latest: useLatestData
        });
        
        const response = await fetch(`/api/dashboard?${params}`);
        const data = await response.json();
        
        updatePeriodDisplay(data.periodo);
        updateKpis(data);
        updateChart(data.chart);
        updateTopProducts(data.top_produtos);
        updateInsights(data.insights);
        
        // Atualizar timestamp
        const now = new Date();
        document.getElementById('last-update').textContent = 
            `Última atualização: ${now.toLocaleTimeString('pt-BR')}`;
            
    } catch (error) {
        console.error('Erro ao carregar dados:', error);
        document.getElementById('insights-container').innerHTML = 
            '<div class="insight-card alerta"><p class="insight-description">Erro ao carregar dados. Verifique a conexão.</p></div>';
    }
};

// Inicializar event listeners
const initEventListeners = () => {
    // Seletor de KPI
    document.getElementById('kpi-selector').addEventListener('change', (e) => {
        currentKpi = e.target.value;
        loadDashboardData();
    });
    
    // Botões de período
    document.querySelectorAll('.btn-period').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.btn-period').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentPeriod = btn.dataset.period;
            loadDashboardData();
        });
    });
    
    // Toggle de dados recentes
    document.getElementById('latest-data-toggle').addEventListener('change', (e) => {
        useLatestData = e.target.checked;
        loadDashboardData();
    });
};

// Inicializar dashboard
document.addEventListener('DOMContentLoaded', () => {
    // Marcar botão ativo inicial
    document.querySelector('[data-period="dia"]').classList.add('active');
    
    initEventListeners();
    loadDashboardData();
    
    // Auto-refresh a cada 60 segundos
    setInterval(loadDashboardData, 60000);
});
