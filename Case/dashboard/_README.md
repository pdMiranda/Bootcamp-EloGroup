# Executive Decision Dashboard - Vértice Retail

Este projeto implementa a solução de dashboard analítico compacto descrita no prompt. 
A arquitetura é dividida em uma camada de processamento de dados (Python/Pandas) e uma de visualização (HTML/CSS/JS Estático).

## Arquivos do Projeto
- `index.html`: Dashboard SPA construído com Tailwind CSS e Chart.js, seguindo um Bento Grid Minimalista.
- `styles.css`: estilos próprios do dashboard e regras de impressão do relatório.
- `script.js`: navegação das abas, carregamento dos dados, renderização dos gráficos e lógica do relatório periódico.
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

## Módulos relacionados

- [Atendimento Inteligente](../modulos/chatbot/README.md): chatbot de atendimento com consulta de pedidos e exportação de tickets.
- [Relatório Executivo](../modulos/relatorio/README.md): relatório MBR/WBR independente para impressão ou exportação em PDF.

O dashboard referencia os módulos relativos pelo iframe e todos os assets locais são carregados por caminhos relativos ao próprio diretório. Isso permite abrir cada módulo pelo mesmo servidor HTTP sem alterar a configuração.
