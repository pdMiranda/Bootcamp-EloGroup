# Executive Decision Dashboard - Vértice Retail

Este projeto implementa a solução de dashboard analítico compacto descrita no prompt. 
A arquitetura é dividida em uma camada de processamento de dados (Python/Pandas) e uma de visualização (HTML/CSS/JS Estático).

## Arquivos do Projeto

- `process_data.py`: Script Python que realiza a ingestão e transformação dos CSVs (Vendas, Clientes, Estoque, Marketing, Atendimento), calculando KPIs e hipóteses, e gerando um JSON estruturado.
- `dashboard_data.json`: Arquivo gerado que contém todos os dados mastigados e prontos para leitura pelo front-end (zero processamento no browser).
- `index.html`: Dashboard SPA construído com Tailwind CSS e Chart.js, seguindo um Bento Grid Minimalista.
- Arquivos CSV de entrada: `vendas.csv`, `clientes.csv`, `estoque.csv`, `marketing.csv`, `atendimento.csv`, localizados em `../data`.

## Como Executar

### 1. Processar os Dados
Certifique-se de que possui o Python instalado juntamente com as bibliotecas `pandas` e `numpy`. A partir da pasta `Case/dashboard`, rode:

```bash
pip install pandas numpy
python process_data.py
```
*(O arquivo `dashboard_data.json` será criado na mesma pasta, com os modos integrado e estendido e séries semanais, mensais e anuais).*

### 2. Visualizar o Dashboard
Devido às políticas de segurança dos navegadores (CORS), requisições locais (usando `fetch` via `file://`) podem ser bloqueadas se você abrir o `index.html` diretamente com dois-cliques.

Para visualizar corretamente, inicie um servidor HTTP simples no terminal:

```bash
python -m http.server 8000
```
Em seguida, acesse no seu navegador: [http://localhost:8000](http://localhost:8000)

O dashboard carregará instantaneamente as respostas já processadas.
