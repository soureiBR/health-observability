#!/bin/bash
# Exemplo: Como chamar o webhook do Kuma

# Este script mostra como enviar um alert teste para o webhook enricher

set -e

# ============================================
# CONFIGURAÇÃO
# ============================================

# Se rodando local
WEBHOOK_URL="http://localhost:5000/webhook/kuma-alert"

# Se rodando no K8s (dentro do cluster)
# WEBHOOK_URL="http://kuma-webhook-enricher:5000/webhook/kuma-alert"

# Webhooks do Discord e Telegram
DISCORD_WEBHOOK="https://discordapp.com/api/webhooks/YOUR_DISCORD_WEBHOOK_ID/YOUR_TOKEN"
TELEGRAM_URL="https://api.telegram.org/botYOUR_BOT_TOKEN/sendMessage"
TELEGRAM_CHAT_ID="YOUR_CHAT_ID"

# ============================================
# EXEMPLO 1: Alert simples com Discord
# ============================================

echo "📤 Enviando alert para Discord..."

curl -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "monitor_name": "gtm-api",
    "service_url": "https://api.soureicdn.com/debug/healthz",
    "error": "Request failed with status code 503",
    "discord_webhook": "'"$DISCORD_WEBHOOK"'"
  }'

echo ""
echo "✅ Alert enviado!"

# ============================================
# EXEMPLO 2: Alert com Discord e Telegram
# ============================================

# echo "📤 Enviando alert para Discord e Telegram..."
# 
# curl -X POST "$WEBHOOK_URL" \
#   -H "Content-Type: application/json" \
#   -d '{
#     "monitor_name": "gtm-web",
#     "service_url": "https://web.soureicdn.com/debug/healthz",
#     "error": "Request failed with status code 500",
#     "discord_webhook": "'"$DISCORD_WEBHOOK"'",
#     "telegram_url": "'"$TELEGRAM_URL"'",
#     "telegram_chat_id": "'"$TELEGRAM_CHAT_ID"'"
#   }'

# ============================================
# EXEMPLO 3: Integração com Kuma
# ============================================

# Para integrar com o Kuma, adicione uma notificação customizada:
#
# 1. No Kuma Dashboard:
#    Settings → Notifications → Add (Webhook tipo)
#
# 2. Use esta URL:
#    http://kuma-webhook-enricher:5000/webhook/kuma-alert
#
# 3. Método: POST
#
# 4. Body (com variáveis do Kuma):
#
# {
#   "monitor_name": "$monitorName",
#   "service_url": "$monitorURL",
#   "error": "$lastErrorMessage",
#   "discord_webhook": "SEU_DISCORD_WEBHOOK",
#   "telegram_url": "SEU_TELEGRAM_URL",
#   "telegram_chat_id": "SEU_CHAT_ID"
# }

# ============================================
# REFERÊNCIA: Variáveis disponíveis do Kuma
# ============================================

# $monitorName        - Nome do monitor (ex: gtm-api)
# $monitorURL         - URL sendo monitorada
# $monitorStatus      - Status (up/down)
# $monitorType        - Tipo (http/tcp/etc)
# $lastCheckTime      - Hora do último check
# $lastErrorMessage   - Última mensagem de erro
# $lastResponseTime   - Tempo da última resposta (ms)
# $statusPageURL      - URL da status page
# $uptime             - Uptime %
