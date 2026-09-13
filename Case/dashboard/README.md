# Dashboard Executivo de Varejo

Dashboard analítico para tomada de decisões em operações de varejo, processando dados em tempo real de múltiplas fontes CSV.

## 🎯 Objetivo

Fornecer uma visão clara e acionável da performance do negócio, permitindo que a diretoria identifique problemas, oportunidades e priorize ações com base em dados concretos.

## 📊 KPIs Monitorados

### Comercial
- Receita Bruta
- Pedidos
- Ticket Médio
- Conversão

### Margem
- Margem de Contribuição
- Margem Percentual
- Desconto Médio
- Frete Médio
- Rentabilidade por SKU

### Marketing
- CAC (Custo de Aquisição de Cliente)
- ROAS (Retorno sobre Investimento em Publicidade)
- Conversões
- Margem por Canal

### Cliente
- Taxa de Recompra
- LTV (Valor Vitalício do Cliente)
- Churn Rate
- Segmentos RFM

### Operações
- Taxa de Devolução
- Taxa de Ruptura
- Giro de Estoque
- Lead Time Médio

### Atendimento
- Volume de Tickets
- SLA (Acordo de Nível de Serviço)
- CSAT (Satisfação do Cliente)
- Custo por Ticket

### Produtividade
- Horas Economizadas
- Automação Potencial
- Retrabalho Reduzido
- Tempo de Resposta

### Impacto Financeiro
- EBITDA Potencial
- Economia Estimada
- Receita Protegida
- Payback

## 🚀 Funcionalidades

- **Gráfico Temporal Interativo**: Visualize a evolução de Receita Bruta e Margem de Contribuição simultaneamente
- **Seletor de KPI**: Alterne entre diferentes KPIs para análise focada
- **Granularidade Flexível**: Analise dados por Dia, Semana ou Mês
- **Modo Dados Recentes**: Toggle para análise dos últimos 7 dias com alerta de lacuna temporal
- **4 Gráficos Secundários**:
  - ROAS por Canal
  - Segmentos de Clientes
  - Top 10 Produtos Mais Vendidos
  - Receita por Canal
- **Cards de Destaque**: Melhor Canal (ROAS) e Top Segmento
- **KPIs Detalhados por Área**: Abas organizadas pelas 8 áreas do negócio
- **Insights Acionáveis**: Análise comparativa automática com prioridades e impacto estimado
- **Design Corporativo**: Tema claro, compacto e responsivo

## 📁 Estrutura do Projeto

```
Case/
├── data/                    # Bases de dados CSV
│   ├── vendas.csv          # Transações de vendas
│   ├── clientes.csv        # Base de clientes
│   ├── estoque.csv         # Controle de estoque
│   ├── marketing.csv       # Campanhas de marketing
│   └── atendimento.csv     # Tickets de suporte
├── dashboard/
│   ├── app.py              # Backend Flask
│   ├── templates/
│   │   └── index.html      # Template HTML principal
│   └── static/
│       ├── css/
│       │   └── style.css   # Estilos corporativos
│       └── js/
│           └── dashboard.js # Lógica do frontend
└── notebooks/
    └── hipoteses.ipynb     # Análise exploratória
```

## 🔧 Instalação e Uso

### Pré-requisitos
- Python 3.8+
- pip

### Instalação das Dependências

```bash
cd Case/dashboard
pip install flask pandas numpy
```

### Executando o Dashboard

```bash
python app.py
```

O servidor iniciará em `http://localhost:5000`

### Acessando o Dashboard

1. Abra seu navegador
2. Acesse `http://localhost:5000`
3. Utilize os controles no topo para:
   - Selecionar o KPI principal para análise
   - Alterar granularidade (Dia/Semana/Mês)
   - Ativar modo "Dados Recentes" para últimos 7 dias

## 📈 Como Interpretar

### Cards Principais
- **Variações (%)**: Comparação com período anterior (30 ou 7 dias)
- **Cores**: Verde (positivo), Vermelho (negativo), Cinza (neutro)

### Gráfico Principal
- Mostra **Receita Bruta** (azul, eixo esquerdo) e **Margem de Contribuição** (verde, eixo direito)
- Use o seletor de KPI para focar em métricas específicas

### Insights & Ações
- **Crítico**: Requer ação imediata da diretoria
- **Alta**: Importante, planejar ação em curto prazo
- **Média**: Oportunidades de melhoria
- **Baixa**: Informações contextuais

### Alerta de Lacuna de Dados
Ao ativar "Dados Recentes", o sistema verifica se há dados completos nos últimos 7 dias. Se houver lacuna, um alerta amarelo informa quantos dias possuem dados válidos.

## ⚠️ Considerações sobre os Dados

- **Janela Válida**: As análises consideram apenas dados dentro da janela temporal disponível nas bases CSV
- **Última Data**: Os dados mais recentes vão até 26/01/2024
- **Comparação Temporal**: O modo "Dados Recentes" compara os últimos 7 dias disponíveis com os 7 dias anteriores
- **Lacunas**: Alguns períodos podem ter menos dados devido à natureza das bases originais

## 🛠️ Tecnologias

- **Backend**: Flask (Python)
- **Frontend**: HTML5, CSS3, JavaScript Vanilla
- **Visualização**: Chart.js
- **Processamento**: Pandas, NumPy

## 📝 Notas de Implementação

- O backend processa CSVs em tempo real (sem JSON pré-gerado)
- Cache de dados carregados para performance
- Cálculo correto de Margem de Contribuição: `Receita Líquida - Custo Produto - Custo Frete`
- Conversão calculada como % de pedidos com pagamento aprovado
- Insights gerados automaticamente baseado em análise comparativa de períodos

## 👥 Público-Alvo

- Diretoria Executiva
- Gerentes de Área
- Analistas de Business Intelligence
- Equipes de Planejamento Estratégico

---

**Dashboard desenvolvido para Case de Varejo** | 2024
