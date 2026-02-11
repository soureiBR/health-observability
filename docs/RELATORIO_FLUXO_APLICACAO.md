# Relatório Técnico - Health Observability: Fluxo da Aplicação

## Objetivo da Aplicação

O **Health Observability** é um sistema de **alerta enriquecido** para incidentes.
Ele **não é uma plataforma de logs** — ele complementa as ferramentas de logging existentes
(Logs Teste / OpenSearch) adicionando contexto imediato às notificações de queda de serviço.

---

## O Que a Aplicação FAZ vs O Que Ela NÃO FAZ

| FAZ | NÃO FAZ |
|-----|---------|
| Captura um trecho dos logs do pod **no momento da queda** | Armazenar logs permanentemente |
| Envia esse trecho como parte do **alerta no Discord/Telegram** | Substituir OpenSearch ou Logs Teste |
| Mostra o status do pod (Running, Pending, Failed) | Coletar ou indexar logs continuamente |
| Mostra o motivo de falha (ex: falta de CPU/memória) | Ser uma plataforma de observabilidade |

---

## Fluxo Completo (Passo a Passo)

```
PASSO 1                    PASSO 2                    PASSO 3
Uptime Kuma            Webhook Enricher           Discord / Telegram
(VM externa)           (Pod no Cluster K8s)       (Notificações)

[Monitora URLs]  ──▶  [Recebe alerta de queda]  ──▶  [Envia alerta enriquecido]
                            │
                            │  PASSO 2.1: Consulta K8s API
                            │  - Qual pod está associado?
                            │  - O pod está Running/Pending/Failed?
                            │  - Pega as últimas 50 linhas de log
                            │  - Pega o describe do pod (se Pending/Failed)
                            │
                            ▼
                       [Monta mensagem com contexto]
```

### Detalhamento de Cada Passo

**PASSO 1 - Uptime Kuma detecta queda:**
- O Kuma faz health check periódico nas URLs dos serviços (ex: `https://api.soureicdn.com/debug/healthz`)
- Quando um serviço retorna erro (500, 503, timeout), o Kuma dispara um webhook HTTP POST

**PASSO 2 - Webhook Enricher recebe o alerta e enriquece:**
- Recebe o nome do monitor e a mensagem de erro
- Consulta a API do Kubernetes para buscar informações do pod relacionado:
  - **Pod Running**: captura as últimas 50 linhas de log (máx 1500 caracteres)
  - **Pod Pending**: executa `kubectl describe` para mostrar por que o pod não subiu (ex: falta de recursos)
  - **Pod Failed**: captura tanto os logs quanto o describe
- Extrai o código HTTP do erro (500, 503, etc.)

**PASSO 3 - Envia notificação enriquecida:**
- Formata a mensagem com todos os dados coletados
- Envia para o **Discord** (embed formatado) e/ou **Telegram** (mensagem markdown)
- A equipe recebe no canal a notificação com contexto suficiente para o primeiro diagnóstico

---

## Exemplo Real de Notificação Gerada

Quando o serviço `gtm-api` cai com erro 503, a equipe recebe no Discord:

```
❌ gtm-api CAIU

📊 Status HTTP: 503 - Service Unavailable
🔗 URL: https://api.soureicdn.com/debug/healthz
🐳 Pod Status: Running
✓ Pronto: ❌ Não
📦 Pod Name: gtm-api-5f8d9a7c-2b3e1

📝 Últimos Logs:
  2025-01-15T10:32:01Z ERROR: Connection refused to database
  2025-01-15T10:32:02Z ERROR: Health check failed
  2025-01-15T10:32:03Z WARN: Retrying connection...
```

---

## De Onde Vêm os Logs e Para Onde Vão

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   ORIGEM DOS LOGS          DESTINO DOS LOGS                     │
│                                                                 │
│   Kubernetes API  ──────▶  Discord / Telegram (notificação)     │
│   (pod stdout/stderr)      NÃO são armazenados em nenhum DB    │
│                                                                 │
│   São as mesmas linhas que aparecem ao executar:                 │
│   $ kubectl logs <pod-name> -n analytics --tail=50              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Importante:** Os logs capturados são **apenas um trecho** (últimas 50 linhas) e servem
exclusivamente para dar contexto imediato no alerta. Eles **não substituem** a consulta
completa no OpenSearch ou Logs Teste para investigações aprofundadas.

---

## Relação com as Ferramentas de Logging Existentes

```
                    ┌──────────────────────────────┐
                    │     Logs dos Containers       │
                    │     (stdout / stderr)         │
                    └──────────┬───────────────────┘
                               │
                 ┌─────────────┼─────────────────┐
                 │             │                  │
                 ▼             ▼                  ▼
          ┌────────────┐ ┌──────────┐ ┌─────────────────────┐
          │  OpenSearch │ │  Logs    │ │  Webhook Enricher   │
          │  (completo) │ │  Teste   │ │  (trecho no alerta) │
          └────────────┘ └──────────┘ └─────────────────────┘
               │              │                  │
               ▼              ▼                  ▼
          Investigação   Investigação     Primeiro diagnóstico
          aprofundada    aprofundada      rápido no Discord
          histórico      histórico        (últimas 50 linhas)
```

**O Webhook Enricher complementa, não compete.** Ele fornece um "preview" rápido dos logs
no momento da queda para que a equipe saiba imediatamente o que está acontecendo,
sem precisar abrir o OpenSearch. Para análise completa, as ferramentas de logging
existentes continuam sendo a referência.

---

## Componentes da Aplicação

| Componente | Localização | Função |
|---|---|---|
| `sync_kuma.py` | CronJob no Cluster K8s (a cada 6h) | Sincroniza deployments K8s com monitores no Uptime Kuma |
| `kuma_webhook_enricher.py` | Pod no Cluster K8s (namespace analytics) | Servidor Flask que recebe alertas e enriquece com dados do K8s |
| Uptime Kuma | VM externa | Dashboard de monitoramento e disparo de alertas |
| Discord / Telegram | Serviços externos | Canais de notificação da equipe |

---

## Resumo Executivo

O Health Observability **acelera o tempo de resposta a incidentes**. Quando um serviço cai,
ao invés de a equipe receber apenas "serviço X está fora", ela recebe uma notificação
com o código HTTP, status do pod e um trecho dos logs — tudo no Discord/Telegram,
em segundos. Para a investigação completa, a equipe continua usando o OpenSearch / Logs Teste
normalmente.
