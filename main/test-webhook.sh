#!/bin/bash
# Script para testar o webhook enricher localmente

set -e

echo "🚀 Iniciando teste do Webhook Enricher..."
echo ""

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Variáveis
WEBHOOK_URL="http://localhost:5000/webhook/kuma-alert"
DISCORD_WEBHOOK="${DISCORD_WEBHOOK:-}"
TELEGRAM_URL="${TELEGRAM_URL:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}"

echo -e "${YELLOW}Configuração:${NC}"
echo "  Webhook URL: $WEBHOOK_URL"
echo "  Discord: ${DISCORD_WEBHOOK:0:50}..."
echo ""

# Teste 1: Verificar se o servidor está rodando
echo -e "${YELLOW}📡 Teste 1: Health Check${NC}"
if curl -s "$WEBHOOK_URL/../health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Servidor está respondendo${NC}"
else
    echo -e "${RED}❌ Servidor não está respondendo${NC}"
    echo "   Execute: python kuma_webhook_enricher.py"
    exit 1
fi
echo ""

# Teste 2: Webhook com alert DOWN
echo -e "${YELLOW}📡 Teste 2: Simulando alert de container caído${NC}"
PAYLOAD=$(cat <<EOF
{
  "monitor_name": "gtm-camaleoaplussize",
  "service_url": "https://camaleoaplussize.soureicdn.com/debug/healthz",
  "error": "Request failed with status code 503",
  "discord_webhook": "$DISCORD_WEBHOOK",
  "telegram_url": "$TELEGRAM_URL",
  "telegram_chat_id": "$TELEGRAM_CHAT_ID"
}
EOF
)

RESPONSE=$(curl -s -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")

echo -e "${GREEN}✅ Requisição enviada${NC}"
echo "Resposta:"
echo "$RESPONSE" | jq . 2>/dev/null || echo "$RESPONSE"
echo ""

# Teste 3: Multiple alerts
echo -e "${YELLOW}📡 Teste 3: Simulando múltiplos alerts${NC}"
for container in "gtm-api" "gtm-web" "gtm-worker"; do
    echo "  Enviando alerta para $container..."
    PAYLOAD=$(cat <<EOF
{
  "monitor_name": "$container",
  "service_url": "https://$container.soureicdn.com/debug/healthz",
  "error": "Request failed with status code 500",
  "discord_webhook": "$DISCORD_WEBHOOK"
}
EOF
)
    curl -s -X POST "$WEBHOOK_URL" \
      -H "Content-Type: application/json" \
      -d "$PAYLOAD" > /dev/null
    sleep 0.5
done
echo -e "${GREEN}✅ Alertas enviados${NC}"
echo ""

echo -e "${GREEN}✅ Testes concluídos!${NC}"
echo ""
echo "💡 Próximas ações:"
echo "  1. Verifique no Discord/Telegram se as mensagens chegaram"
echo "  2. Verifique os logs: kubectl logs -f deployment/kuma-webhook-enricher -n analytics"
echo "  3. Configure no Kuma: Settings → Notifications → Add Webhook"
