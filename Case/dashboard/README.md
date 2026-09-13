# Dashboard Executivo - Case Analytics

Dashboard corporativo para análise de métricas empresariais com foco em desempenho comercial, operações e atendimento.

## Funcionalidades

- **8 áreas de KPIs**: Comercial, Margem, Marketing, Cliente, Operações, Atendimento, Produtividade, Impacto
- **Análise temporal**: Comparação entre períodos com insights automáticos
- **Gráficos interativos**: Evolução temporal, ROAS por canal, Segmentos, Receita por canal, Top produtos
- **Dados reais**: Processamento direto dos CSVs sem intermediários
- **Alertas de lacuna**: Aviso claro sobre limitações temporais dos dados

## Estrutura do Projeto

```
Case/dashboard/
├── app.py              # Backend Flask (API + processamento CSV)
├── README.md           # Esta documentação
├── templates/
│   └── index.html      # Estrutura HTML
└── static/
    ├── css/style.css   # Estilo corporativo claro
    └── js/dashboard.js # Lógica frontend
```

## KPIs Disponíveis

### Comercial
- Receita Bruta
- Pedidos
- Ticket Médio
- Taxa de Conversão

### Margem
- Margem de Contribuição
- Desconto Médio
- Frete Médio
- Rentabilidade

### Marketing
- CAC (Custo de Aquisição)
- ROAS (Retorno sobre Anúncio)
- Melhor Canal

### Cliente
- Recompra
- LTV (Valor Vitalício)
- Churn
- Top Segmento

### Operações
- Taxa de Devolução
- Ruptura de Estoque
- Giro de Estoque
- Lead Time

### Atendimento
- Volume de Tickets
- SLA (% resolvido em 24h)
- CSAT (Satisfação)
- Custo por Ticket

### Produtividade
- Horas Economizadas
- Automação Potencial
- Retrabalho
- Tempo de Resposta

### Impacto
- EBITDA Potencial
- Economia Estimada
- Receita Protegida
- Payback

## Execução

1. Navegue até a pasta do dashboard:
```bash
cd Case/dashboard
```

2. Execute o servidor Flask:
```bash
python3 app.py
```

3. Acesse no browser:
```
http://localhost:5000
```

## Dados e Limitações

- **Fonte**: Arquivos CSV na pasta `Case/data/`
- **Período válido vendas**: Até 26/01/2024
- **Atendimento**: Dados disponíveis até 2025 (com lacunas)
- **Toggle "Dados Recentes"**: Analisa apenas últimos 7 dias dentro do período válido

## Uso da Interface

1. **Seletor de KPI**: Alterne entre Receita Bruta e Margem de Contribuição no gráfico principal
2. **Granularidade**: Dia, Semana ou Mês
3. **Período**: 7, 30 ou 90 dias
4. **Dados Recentes**: Ative para focar nos últimos dias disponíveis (com aviso de lacuna)
5. **Insights**: Leia as recomendações priorizadas por criticidade

## Tecnologias

- Backend: Python + Flask + Pandas
- Frontend: HTML5, CSS3, JavaScript
- Gráficos: Chart.js
