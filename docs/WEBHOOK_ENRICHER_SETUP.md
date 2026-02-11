# Kuma Webhook Enricher - Configuração

## 🎯 O que é?

Um servidor webhook que intercepta alertas do Kuma e os enriquece com:
- ✅ Status HTTP exato (500, 503, etc)
- ✅ Logs do container quando falha
- ✅ Describe do pod (por quê está em Pending/Failed)

## 🚀 Instalação

### 1. Build da imagem Docker
```bash
cd /home/hugom/health-observability/main
docker build -f Dockerfile.webhook -t kuma-webhook-enricher:latest .
```

### 2. Deploy no Kubernetes
```bash
kubectl apply -f rbac.yaml
kubectl apply -f webhook-enricher-deployment.yaml
```

### 3. Verificar se está rodando
```bash
kubectl get pods -n analytics | grep webhook
kubectl logs -n analytics -f deployment/kuma-webhook-enricher
```

### 4. Testar o webhook (local)
```bash
python kuma_webhook_enricher.py

# Em outro terminal
curl -X POST http://localhost:5000/webhook/kuma-alert \
  -H "Content-Type: application/json" \
  -d '{
    "monitor_name": "gtm-test",
    "service_url": "https://test.soureicdn.com/debug/healthz",
    "error": "Request failed with status code 503",
    "discord_webhook": "YOUR_DISCORD_WEBHOOK_URL"
  }'
```

## 🔗 Integração com Kuma

### Opção 1: Notificação Customizada (Recomendado)

1. **No Kuma Dashboard**, vá em:
   `Settings` → `Notifications` → `Add Notification`

2. **Tipo**: Webhook/Custom

3. **URL**: 
   ```
   http://kuma-webhook-enricher:5000/webhook/kuma-alert
   ```

4. **Headers** (se necessário):
   ```
   Content-Type: application/json
   ```

5. **Body**:
   ```json
   {
     "monitor_name": "$monitorName",
     "service_url": "$monitorURL",
     "error": "$lastErrorMessage",
     "discord_webhook": "YOUR_DISCORD_WEBHOOK_URL",
     "telegram_url": "https://api.telegram.org/botXXXX/sendMessage",
     "telegram_chat_id": "YOUR_CHAT_ID"
   }
   ```

### Opção 2: Proxy do Kuma (Alternativa)

Se você já tem notificações Discord/Telegram configuradas, você pode:

1. Fazer o webhook único chamar o enriquecedor
2. O enriquecedor busca logs e reenvia pro Discord/Telegram com mais info

## 💬 Variáveis do Kuma

| Variável | Descrição |
|----------|-----------|
| `$monitorName` | Nome do monitor (ex: gtm-api) |
| `$monitorURL` | URL sendo monitorada |
| `$monitorStatus` | Status atual (up/down) |
| `$lastErrorMessage` | Última mensagem de erro |
| `$lastCheckTime` | Hora do último check |

## 📊 Exemplos de Mensagens

### Quando um pod está em Pending:
```
❌ gtm-api CAIU ❌

📊 Status HTTP: 503 - Service Unavailable
🐳 Pod Status: Pending
📋 Describe (Por quê não subiu?):
   Insufficient cpu
   Insufficient memory
```

### Quando está rodando mas com erro:
```
❌ gtm-web CAIU ❌

📊 Status HTTP: 500 - Internal Server Error
🐳 Pod Status: Running
📝 Últimos Logs:
   2026-02-09 15:20:14 Error connecting to database
   2026-02-09 15:20:14 Connection timeout
```

## 🔧 Troubleshooting

### "Pod não encontrado"
- Verifique se o nome do deployment combina com o prefixo `gtm-`
- Exemplo: monitor `gtm-api` procura por deployment `api`

### "Erro ao buscar logs"
- Verifique se o RBAC foi aplicado corretamente
- `kubectl get rolebinding -n analytics`
- `kubectl logs <pod> -n analytics` deve funcionar

### Webhook não está sendo chamado
- Verifique a notificação no Kuma:
  `Settings` → `Notifications` → Edit → Test
- Veja se a URL está correta e acessível

## 📝 Environment Variables

```bash
NAMESPACE=analytics  # Namespace do K8s onde estão os containers
```

## 🔒 Segurança

- [ ] Use HTTPS for Flask (considere reverse proxy com nginx/traefik)
- [ ] Adicione autenticação ao webhook (bearer token)
- [ ] Limpe logs regularmente
- [ ] Considere IP whitelist para chamadas ao webhook

## 📚 Referências

- Logs do Kubernetes: https://kubernetes.io/docs/tasks/debug-application-cluster/logs/
- Kuma Notifications: https://github.com/louislam/uptime-kuma/wiki/Notification-Methods
