#!/bin/bash
# Script para diagnosticar problemas com o webhook enricher

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔍 Diagnóstico do Webhook Enricher${NC}"
echo "=================================="
echo ""

# 1. Verificar se está rodando
echo -e "${YELLOW}1️⃣  Verificando se o webhook está rodando...${NC}"
if curl -s http://localhost:5000/health > /dev/null 2>&1; then
    echo -e "${GREEN}   ✅ Webhook rodando em http://localhost:5000${NC}"
else
    if kubectl get pods -n analytics -l app=kuma-webhook-enricher > /dev/null 2>&1; then
        echo -e "${YELLOW}   ⚠️  Webhook não responde em localhost${NC}"
        echo "   Verificando no K8s..."
        PODS=$(kubectl get pods -n analytics -l app=kuma-webhook-enricher -o name)
        if [ -z "$PODS" ]; then
            echo -e "${RED}   ❌ Nenhum pod encontrado${NC}"
            echo "   Execute: kubectl apply -f webhook-enricher-deployment.yaml"
        else
            echo -e "${GREEN}   ✅ Pods encontrados:${NC}"
            kubectl get pods -n analytics -l app=kuma-webhook-enricher
            echo ""
            echo "   Verificando logs..."
            kubectl logs -n analytics -f deployment/kuma-webhook-enricher --tail=20
        fi
    else
        echo -e "${RED}   ❌ Webhook não está rodando${NC}"
        echo "   Local: python kuma_webhook_enricher.py"
        echo "   K8s: kubectl apply -f webhook-enricher-deployment.yaml"
    fi
fi
echo ""

# 2. Verificar Kubernetes
echo -e "${YELLOW}2️⃣  Verificando Kubernetes...${NC}"
if command -v kubectl &> /dev/null; then
    echo -e "${GREEN}   ✅ kubectl instalado${NC}"
    
    # Verificar acesso ao cluster
    if kubectl cluster-info > /dev/null 2>&1; then
        echo -e "${GREEN}   ✅ Conectado ao cluster${NC}"
        
        # Verificar namespace
        if kubectl get namespace analytics > /dev/null 2>&1; then
            echo -e "${GREEN}   ✅ Namespace 'analytics' existe${NC}"
        else
            echo -e "${RED}   ❌ Namespace 'analytics' não existe${NC}"
        fi
        
        # Verificar RBAC
        if kubectl get role -n analytics deployment-reader > /dev/null 2>&1; then
            echo -e "${GREEN}   ✅ Role 'deployment-reader' existe${NC}"
        else
            echo -e "${RED}   ❌ Role 'deployment-reader' não existe${NC}"
            echo "   Execute: kubectl apply -f rbac.yaml"
        fi
        
        # Verificar service account
        if kubectl get sa -n analytics kuma-sync-sa > /dev/null 2>&1; then
            echo -e "${GREEN}   ✅ ServiceAccount 'kuma-sync-sa' existe${NC}"
        else
            echo -e "${RED}   ❌ ServiceAccount 'kuma-sync-sa' não existe${NC}"
        fi
    else
        echo -e "${RED}   ❌ Não conectado a um cluster Kubernetes${NC}"
    fi
else
    echo -e "${YELLOW}   ⚠️  kubectl não instalado${NC}"
    echo "   Para local testing: python kuma_webhook_enricher.py"
fi
echo ""

# 3. Verificar connectivity entre Kuma e Webhook
echo -e "${YELLOW}3️⃣  Testando conectividade...${NC}"
if [ ! -z "$KUMA_URL" ]; then
    if curl -s "$KUMA_URL" > /dev/null 2>&1; then
        echo -e "${GREEN}   ✅ Kuma acessível em $KUMA_URL${NC}"
    else
        echo -e "${RED}   ❌ Kuma não acessível em $KUMA_URL${NC}"
    fi
else
    echo "   Defina KUMA_URL para verificar conexão"
fi
echo ""

# 4. Verificar permissões
echo -e "${YELLOW}4️⃣  Verificando permissões no K8s...${NC}"
if kubectl auth can-i list pods -n analytics --as=system:serviceaccount:analytics:kuma-sync-sa > /dev/null 2>&1; then
    echo -e "${GREEN}   ✅ Pode listar pods${NC}"
else
    echo -e "${RED}   ❌ Não pode listar pods${NC}"
fi

if kubectl auth can-i get pods/log -n analytics --as=system:serviceaccount:analytics:kuma-sync-sa > /dev/null 2>&1; then
    echo -e "${GREEN}   ✅ Pode ler logs de pods${NC}"
else
    echo -e "${RED}   ❌ Não pode ler logs de pods${NC}"
fi
echo ""

# 5. Testar webhook
echo -e "${YELLOW}5️⃣  Testando webhook com alert teste...${NC}"
TEST_RESPONSE=$(curl -s -X POST http://localhost:5000/webhook/kuma-alert \
  -H "Content-Type: application/json" \
  -d '{
    "monitor_name": "gtm-test",
    "service_url": "https://test.soureicdn.com/debug/healthz",
    "error": "Request failed with status code 503"
  }' 2>&1 || echo "ERROR")

if echo "$TEST_RESPONSE" | grep -q "ok"; then
    echo -e "${GREEN}   ✅ Webhook respondeu corretamente${NC}"
    echo "   Resposta: $TEST_RESPONSE" | head -1
else
    if echo "$TEST_RESPONSE" | grep -q "ERROR\|Connection refused"; then
        echo -e "${RED}   ❌ Webhook não está rodando${NC}"
    else
        echo -e "${YELLOW}   ⚠️  Resposta inesperada${NC}"
        echo "   $TEST_RESPONSE"
    fi
fi
echo ""

# 6. Recomendações
echo -e "${BLUE}💡 Próximas ações:${NC}"
echo "   1. Verifique os logs: kubectl logs -n analytics -f deployment/kuma-webhook-enricher"
echo "   2. Teste o webhook: bash test-webhook.sh"
echo "   3. Configure no Kuma: Settings → Notifications"
echo "   4. URL do webhook: http://kuma-webhook-enricher:5000/webhook/kuma-alert"
echo ""

echo -e "${GREEN}✅ Diagnóstico concluído!${NC}"
