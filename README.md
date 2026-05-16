# Cantina Escolar

Sistema web para cantina escolar feito em um arquivo Python, com HTML, CSS e JavaScript embutidos.

## Versao atual

`v1.0.0`

## Recursos

- Cardapio digital responsivo com fotos ilustradas, precos, descricoes e tags nutricionais.
- Filtros por categoria, alergeno e opcoes como sem lactose, vegano e sem gluten.
- Carrinho e pre-venda para retirada no intervalo.
- Carteira virtual com recarga de saldo.
- Limite diario de gastos para controle dos pais.
- Historico de compras por cliente.
- Agendamento de lanche por dia ou pela semana escolar.
- Notificacoes na tela quando o pedido fica pronto.
- Painel administrativo com faturamento, pedidos, ticket medio e alertas.
- Controle de estoque com alerta de estoque baixo.
- Gestao de status: recebido, em preparo, pronto e cancelado.
- Fechamento de caixa por saldo do sistema, cartao e dinheiro.
- Modo escuro.

## Como rodar

```bash
python cantina_escolar.py
```

Depois abra:

```text
http://127.0.0.1:8000
```

O arquivo `cantina_data.json` e criado automaticamente para salvar pedidos, saldos, estoque e agendamentos.

## Estrutura

- `cantina_escolar.py`: aplicacao completa.
- `VERSION`: versao atual do projeto.
- `CHANGELOG.md`: historico de versoes.
- `.gitignore`: arquivos gerados que nao devem ir para o GitHub.

## Politica de versao

Este projeto usa versionamento semantico simples:

- `MAJOR`: mudancas grandes ou incompatibilidades.
- `MINOR`: novas funcionalidades.
- `PATCH`: ajustes, correcao de bugs e melhorias pequenas.

Toda nova alteracao deve atualizar:

- `APP_VERSION` em `cantina_escolar.py`.
- `VERSION`.
- `CHANGELOG.md`.
