# Atendimento Inteligente

Módulo de atendimento da Vértice Retail. O chatbot carrega as bases CSV de `../../data`, autentica clientes pelo Customer ID, consulta pedidos, registra tickets da sessão e permite exportar o histórico em CSV.

## Arquivos

- `index.html`: estrutura e interface do atendimento.
- `styles.css`: estilos específicos do chat.
- `script.js`: carregamento das bases, fluxos de atendimento, persistência local e exportação CSV.

## Como executar

Na raiz de `Case`, inicie um servidor HTTP:

```bash
python -m http.server 8000
```

Acesse `http://localhost:8000/modulos/chatbot/`.

O uso de servidor HTTP é necessário porque o navegador pode bloquear `fetch` de arquivos CSV quando a página é aberta diretamente com `file://`.
