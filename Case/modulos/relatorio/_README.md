# Relatório Executivo Periódico

Módulo independente para geração de relatórios MBR (mensal) e WBR (semanal) da Vértice Retail. Os períodos são carregados de `../../dados/process_data.json` e podem ser impressos ou salvos como PDF pelo navegador.

## Arquivos

- `index.html`: estrutura do relatório e controles de período.
- `styles.css`: estilos da tela e regras de impressão A4.
- `script.js`: carregamento dos dados, KPIs, tabelas, gráficos e alternância MBR/WBR.

## Como executar

Na raiz de `Case`, inicie um servidor HTTP:

```bash
python -m http.server 8000
```

Acesse `http://localhost:8000/modulos/relatorio/`.

Antes de abrir o módulo, gere o arquivo de dados quando necessário:

```bash
python dados/process_data.py
```

O navegador precisa de um servidor HTTP para permitir o carregamento do JSON via `fetch`.
