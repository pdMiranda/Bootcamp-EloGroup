# Políticas sintéticas — Central de Controle Logístico

1. O agente pode consultar dados, calcular cenários e recomendar ações; não pode executar mudanças em sistemas externos.
2. Reencaminhamento que aumente o custo operacional estimado em mais de 15% exige aprovação humana.
3. Mudança de transportadora para clientes Enterprise exige aprovação humana.
4. Quando a previsão de atraso for superior a 12 horas, clientes Enterprise devem ser priorizados para comunicação proativa.
5. Um hub com utilização acima de 100% e backlog acima de 150 volumes deve ser tratado como risco operacional alto.
6. Uma rota não deve receber aumento de volume quando a transportadora proposta estiver abaixo de 85% de pontualidade.
7. Incidentes críticos devem ser citados em qualquer recomendação que afete o hub ou rota relacionado.
8. Dados de atendimento devem ser utilizados de forma agregada, exceto quando o usuário fornecer explicitamente um shipment_id para investigação operacional.
9. Recomendações devem separar fatos observados, inferências e ações propostas.
10. Toda recomendação de contingência deve explicitar custo, risco de SLA e necessidade de aprovação.
