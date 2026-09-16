        const formatBRL = (v) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v || 0);
        const formatNum = (v) => new Intl.NumberFormat('pt-BR').format(v || 0);
        const formatPct = (v) => ((v || 0) * 100).toFixed(1) + '%';
        const formatPts = (v) => ((v || 0) * 100).toFixed(1) + ' p.p.';

        let rawReportData = null;
        let activeGranularity = 'mes';
        let currentCharts = {};

        // Busca resiliente do JSON nos caminhos prováveis
        async function fetchReportData() {
            const candidatePaths = [
                '../../dados/process_data.json',
                '../dados/process_data.json',
                'dados/process_data.json',
                '/dados/process_data.json',
                'process_data.json',
                'dashboard_data.json'
            ];

            for (const path of candidatePaths) {
                try {
                    const res = await fetch(path);
                    if (res.ok) {
                        const json = await res.json();
                        if (json.relatorios) return json.relatorios;
                    }
                } catch (e) {}
            }
            throw new Error("Não foi possível encontrar o arquivo process_data.json.");
        }

        function renderDeltaBadge(val, isPoints = false, invertSentiment = false) {
            if (val === null || val === undefined || isNaN(val)) return `<span class="text-slate-400 font-normal">Base</span>`;
            if (val === 0) return `<span class="text-slate-500 font-normal">0.0% vs ant.</span>`;

            const isPositive = val > 0;
            const isGood = invertSentiment ? !isPositive : isPositive;
            const colorClass = isGood ? 'text-emerald-700 bg-emerald-50 border-emerald-200' : 'text-red-700 bg-red-50 border-red-200';
            const arrow = isPositive ? '▲' : '▼';
            const formatted = isPoints ? formatPts(Math.abs(val)) : ((Math.abs(val) * 100).toFixed(1) + '%');

            return `<span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] font-bold ${colorClass}">
                ${arrow}${formatted} vs ant.
            </span>`;
        }

        function setGranularity(gran) {
            activeGranularity = gran;
            document.getElementById('btn-gran-mes').className = gran === 'mes' 
                ? 'px-3 py-1.5 rounded-md bg-white text-blue-700 shadow-xs transition'
                : 'px-3 py-1.5 rounded-md text-slate-600 hover:text-slate-900 transition';
            document.getElementById('btn-gran-semana').className = gran === 'semana' 
                ? 'px-3 py-1.5 rounded-md bg-white text-blue-700 shadow-xs transition'
                : 'px-3 py-1.5 rounded-md text-slate-600 hover:text-slate-900 transition';

            document.getElementById('rep-title').textContent = gran === 'mes' ? 'Monthly Business Review (MBR)' : 'Weekly Business Review (WBR)';
            populatePeriodSelector();
        }

        function populatePeriodSelector() {
            const granData = rawReportData[activeGranularity];
            if (!granData) return;

            const select = document.getElementById('period-select');
            const periods = [...granData.periodos_disponiveis].reverse(); // Mais recentes primeiro

            select.innerHTML = periods.map(p => `<option value="${p}">${p}</option>`).join('');
            if (periods.length > 0) {
                renderReportSnapshot(periods[0]);
            }
        }

        function onPeriodChange(periodKey) {
            renderReportSnapshot(periodKey);
        }

        function renderReportSnapshot(periodKey) {
            const periodData = rawReportData[activeGranularity].dados[periodKey];
            if (!periodData) return;

            // Cabeçalho
            document.getElementById('rep-cur-period').textContent = periodData.periodo;
            document.getElementById('rep-prev-period').textContent = periodData.periodo_anterior || 'Início da série';

            // 1. Preenchimento de KPIs
            const k = periodData.kpis;
            document.getElementById('kpi-rec').textContent = formatBRL(k.receita_bruta.val);
            document.getElementById('kpi-rec-delta').innerHTML = renderDeltaBadge(k.receita_bruta.delta_pct);

            document.getElementById('kpi-mc').textContent = formatBRL(k.margem_contribuicao.val);
            document.getElementById('kpi-mc-delta').innerHTML = renderDeltaBadge(k.margem_contribuicao.delta_pct);

            document.getElementById('kpi-mcpct').textContent = formatPct(k.margem_pct.val);
            document.getElementById('kpi-mcpct-delta').innerHTML = renderDeltaBadge(k.margem_pct.delta_pts, true);

            document.getElementById('kpi-pedidos').textContent = formatNum(k.pedidos.val);
            document.getElementById('kpi-pedidos-delta').innerHTML = renderDeltaBadge(k.pedidos.delta_pct);

            document.getElementById('kpi-roas').textContent = `${(k.roas.val || 0).toFixed(2)}x · ${formatBRL(k.cac.val)}`;
            document.getElementById('kpi-cac-delta').innerHTML = renderDeltaBadge(k.cac.delta_pct, false, true);

            document.getElementById('kpi-csat').textContent = `${(k.csat_medio.val || 0).toFixed(2)} ★ · ${formatPct(k.taxa_devolucao.val)}`;
            document.getElementById('kpi-dev-delta').innerHTML = renderDeltaBadge(k.taxa_devolucao.delta_pts, true, true);

            // 2. DRE Operacional
            const dre = periodData.dre_operacional;
            const recBruta = dre.receita_bruta || 1;
            document.getElementById('dre-tbody').innerHTML = `
                <tr class="font-bold text-slate-900 bg-slate-50/50">
                    <td class="py-2">(=) Receita Bruta Faturada</td>
                    <td class="py-2 text-right">${formatBRL(dre.receita_bruta)}</td>
                    <td class="py-2 text-right text-slate-500">100.0%</td>
                </tr>
                <tr class="text-amber-700">
                    <td class="py-1.5 pl-4">(-) Descontos Concedidos</td>
                    <td class="py-1.5 text-right">- ${formatBRL(dre.descontos)}</td>
                    <td class="py-1.5 text-right text-slate-500">- ${formatPct(dre.descontos / recBruta)}</td>
                </tr>
                <tr class="font-semibold text-slate-800">
                    <td class="py-2">(=) Receita Líquida</td>
                    <td class="py-2 text-right">${formatBRL(dre.receita_liquida)}</td>
                    <td class="py-2 text-right text-slate-500">${formatPct(dre.receita_liquida / recBruta)}</td>
                </tr>
                <tr class="text-slate-600">
                    <td class="py-1.5 pl-4">(-) Custo das Mercadorias Vendidas (CMV)</td>
                    <td class="py-1.5 text-right">- ${formatBRL(dre.custo_mercadoria)}</td>
                    <td class="py-1.5 text-right text-slate-500">- ${formatPct(dre.custo_mercadoria / recBruta)}</td>
                </tr>
                <tr class="text-slate-600">
                    <td class="py-1.5 pl-4">(-) Custo de Frete de Entrega</td>
                    <td class="py-1.5 text-right">- ${formatBRL(dre.custo_frete)}</td>
                    <td class="py-1.5 text-right text-slate-500">- ${formatPct(dre.custo_frete / recBruta)}</td>
                </tr>
                <tr class="text-red-600">
                    <td class="py-1.5 pl-4">(-) Perdas com Devoluções & Frete Reverso</td>
                    <td class="py-1.5 text-right">- ${formatBRL(dre.perda_devolucoes)}</td>
                    <td class="py-1.5 text-right text-slate-500">- ${formatPct(dre.perda_devolucoes / recBruta)}</td>
                </tr>
                <tr class="font-bold text-emerald-700 bg-emerald-50/60 border-t-2 border-emerald-200">
                    <td class="py-2.5">(=) Margem de Contribuição Operacional</td>
                    <td class="py-2.5 text-right text-sm">${formatBRL(dre.margem_contribuicao)}</td>
                    <td class="py-2.5 text-right text-sm">${formatPct(dre.margem_contribuicao_pct)}</td>
                </tr>
            `;

            // 3. Tabela e Gráfico de Categorias
            const cats = periodData.categorias || [];
            document.getElementById('cat-tbody').innerHTML = cats.map(c => `
                <tr>
                    <td class="py-1.5 font-semibold text-slate-800">${c.categoria}</td>
                    <td class="py-1.5 text-right font-mono">${formatBRL(c.receita_bruta)}</td>
                    <td class="py-1.5 text-right font-mono text-emerald-700 font-bold">${formatBRL(c.margem_contribuicao)}</td>
                    <td class="py-1.5 text-right font-mono">${formatPct(c.margem_pct)}</td>
                    <td class="py-1.5 text-center font-mono">${formatNum(c.quantidade)}</td>
                </tr>
            `).join('');

            // 4. Tabela e Gráfico de Canais
            const chans = periodData.canais || [];
            document.getElementById('chan-tbody').innerHTML = chans.map(c => `
                <tr>
                    <td class="py-1.5 font-semibold text-slate-800">${c.canal}</td>
                    <td class="py-1.5 text-right font-mono">${formatBRL(c.investimento)}</td>
                    <td class="py-1.5 text-right font-mono">${formatBRL(c.receita_ads)}</td>
                    <td class="py-1.5 text-center font-mono font-bold ${(c.roas || 0) < 2 ? 'text-red-600' : 'text-emerald-700'}">${(c.roas || 0).toFixed(2)}x</td>
                    <td class="py-1.5 text-right font-mono">${formatBRL(c.cac)}</td>
                </tr>
            `).join('');

            // 5. Tabelas de SKUs
            const topSkus = periodData.destaques_skus.top_receita || [];
            const worstSkus = periodData.destaques_skus.menor_margem || [];

            document.getElementById('top-skus-tbody').innerHTML = topSkus.map((s, idx) => `
                <tr class="hover:bg-slate-50">
                    <td class="py-1.5 truncate max-w-[200px]" title="${s.produto}">
                        <span class="text-slate-400 font-mono font-bold mr-1">${idx + 1}.</span>${s.produto}
                    </td>
                    <td class="py-1.5 text-right font-mono font-bold text-slate-800">${formatBRL(s.receita_bruta)}</td>
                    <td class="py-1.5 text-right font-mono text-emerald-700">${formatPct(s.margem_pct)}</td>
                </tr>
            `).join('');

            document.getElementById('worst-skus-tbody').innerHTML = worstSkus.map((s, idx) => `
                <tr class="hover:bg-slate-50">
                    <td class="py-1.5 truncate max-w-[200px]" title="${s.produto}">
                        <span class="text-slate-400 font-mono font-bold mr-1">${idx + 1}.</span>${s.produto}
                    </td>
                    <td class="py-1.5 text-right font-mono text-slate-800">${formatBRL(s.receita_bruta)}</td>
                    <td class="py-1.5 text-right font-mono font-bold ${s.margem_pct < 0 ? 'text-red-600' : 'text-amber-700'}">${formatPct(s.margem_pct)}</td>
                </tr>
            `).join('');

            // 6. Atualização dos Minigráficos
            renderReportCharts(cats, chans);
        }

        function renderReportCharts(cats, chans) {
            Object.values(currentCharts).forEach(c => c.destroy());
            currentCharts = {};

            const ctxCat = document.getElementById('chartCatRep').getContext('2d');
            currentCharts.cat = new Chart(ctxCat, {
                type: 'bar',
                data: {
                    labels: cats.map(c => c.categoria),
                    datasets: [
                        { label: 'Receita (R$)', data: cats.map(c => c.receita_bruta), backgroundColor: '#3b82f6', borderRadius: 3 },
                        { label: 'Margem (R$)', data: cats.map(c => c.margem_contribuicao), backgroundColor: '#10b981', borderRadius: 3 }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 10 } } } },
                    scales: { y: { beginAtZero: true, ticks: { callback: (v) => 'R$ ' + (v / 1000).toFixed(0) + 'k' } } }
                }
            });

            const ctxChan = document.getElementById('chartChanRep').getContext('2d');
            currentCharts.chan = new Chart(ctxChan, {
                type: 'bar',
                data: {
                    labels: chans.map(c => c.canal),
                    datasets: [
                        { label: 'Investimento (R$)', data: chans.map(c => c.investimento), backgroundColor: '#f59e0b', borderRadius: 3 },
                        { label: 'Receita Ads (R$)', data: chans.map(c => c.receita_ads), backgroundColor: '#8b5cf6', borderRadius: 3 }
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

        async function init() {
            try {
                rawReportData = await fetchReportData();
                setGranularity('mes');
            } catch (err) {
                console.error(err);
                document.getElementById('report-content').innerHTML = `
                    <div class="card p-6 border-l-4 border-red-500 bg-red-50 text-red-700">
                        <h4 class="font-bold">Erro ao carregar dados</h4>
                        <p class="text-xs mt-1">Execute o script <code class="font-mono bg-red-100 px-1">python dados/process_data.py</code> para gerar o arquivo <code class="font-mono bg-red-100 px-1">process_data.json</code> e certifique-se de estar rodando via servidor HTTP local.</p>
                    </div>`;
            }
        }

        document.addEventListener('DOMContentLoaded', init);
