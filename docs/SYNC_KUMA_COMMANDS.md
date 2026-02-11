# Sincronização Kuma - Guia de Comandos

## 📋 Visão Geral

Este documento lista todos os comandos disponíveis para sincronizar e gerenciar monitors no Uptime Kuma, além de enriquecer notificações com informações do Kubernetes.

---

## 🔄 Comando 1: Sincronização Kubernetes → Kuma (Padrão)

**Descrição:** Puxa todos os deployments do Kubernetes com o prefixo `gtm-` e cria monitors HTTP no Uptime Kuma.

**Uso:**
```bash
python main/sync_kuma.py
```

**O que faz:**
- ✅ Conecta ao cluster Kubernetes (namespace: `analytics`)
- ✅ Busca deployments com prefixo `gtm-`
- ✅ Exclui os padrões: `proxy`, `preview`, `data-api`
- ✅ Cria monitors HTTP no Kuma automaticamente
- ✅ Delay de 0.8s entre requisições (segurança)

**Exemplo de output:**
```
🚀 [SINCRONIZAÇÃO] Iniciando busca de deployments...
📊 45 deployments encontrados com prefixo 'gtm-'
✅ gtm-api
✅ gtm-frontend
✅ gtm-worker
...
🏁 Sincronização finalizada!
```

---

## 🏷️ Comando 2: Atualizar Monitor Groups

**Descrição:** Adiciona monitors existentes ao **Monitor Group** no Kuma sem precisar refazer o upload.

### Para containers GTM (400+ monitors):

```bash
python main/sync_kuma.py update gtm- "waster-project (gtm)" 797
```

### Para outros prefixos (futuros):

```bash
# Prefixo XYZ
python main/sync_kuma.py update xyz- "waster-project (xyz)" <group_id>

# Prefixo ABC
python main/sync_kuma.py update abc- "waster-project (abc)" <group_id>

# Qualquer outro prefixo
python main/sync_kuma.py update <prefixo> "<nome-do-grupo>" <group_id>
```

**O que faz:**
- ✅ Busca todos os monitors com o prefixo especificado
- ✅ Adiciona o Monitor Group em batch (sem refazer upload)
- ✅ Delay de 0.2s entre requisições (mais rápido)
- ✅ Mostra progresso: ✅ sucesso, ⚠️ erro
- ✅ Exibe estatísticas finais

**Exemplo de output:**
```
🚀 [ATUALIZAÇÃO] Adicionando monitors com prefixo 'gtm-' ao grupo 'waster-project (gtm)'...
📊 412 monitors encontrados para atualizar
✅ gtm-24c
✅ gtm-agc
✅ gtm-web
...
🏁 Atualização finalizada!
   ✅ Sucesso: 412
   ❌ Falhas: 0
```

---

## 🚨 Comando 3: Webhook Enricher (Notificações Enriquecidas)

**Descrição:** Servidor que intercepta alertas do Kuma e os enriquece com logs do Kubernetes e status HTTP.

### Iniciar o servidor (local)

```bash
python main/kuma_webhook_enricher.py
```

### Deploy no Kubernetes

```bash
kubectl apply -f main/webhook-enricher-deployment.yaml
```

**O que faz:**
- ✅ Captura status HTTP exato (500, 503, etc)
- ✅ Extrai logs do container quando falha
- ✅ Mostra "describe" do pod quando está em Pending
- ✅ Formata mensagens enriquecidas pro Discord e Telegram
- ✅ Não interfere com notificações padrão do Kuma

**Exemplo de notificação enriquecida:**
```
❌ gtm-api CAIU ❌

📊 Status HTTP: 503 - Service Unavailable
🔗 URL: https://api.soureicdn.com/debug/healthz
⏰ Hora: 07/02/2026 16:14:14

🐳 Pod Info:
   • Status: Pending
   • Pod Name: gtm-api-5f8d9a7c-2b3e1
   • Pronto: ❌ Não

📋 Descrição (Investigue por quê não subiu):
   Insufficient cpu
   Insufficient memory
```

### Configuração no Kuma

Veja [WEBHOOK_ENRICHER_SETUP.md](WEBHOOK_ENRICHER_SETUP.md) para setup completo.

---

## ⚙️ Configuração

Antes de rodar os comandos, verifique as configurações em `main/sync_kuma.py`:

```python
KUMA_URL = "https://status.soureicdn.com"     # URL do Kuma
KUMA_USER = "admin"                           # Usuário Kuma
KUMA_PASS = "3mUXcHwMajWM8S"                 # Senha Kuma
NAMESPACE = "analytics"                       # Namespace K8s
EXCLUDE_PATTERN = "proxy|preview|data-api"   # Padrões a excluir
```

---

## 📝 Exemplos Práticos

### Cenário 1: Setup inicial completo

```bash
# 1. Sincronizar deployments K8s com Kuma
python main/sync_kuma.py

# 2. Organizar em grupos
python main/sync_kuma.py update gtm- "waster-project (gtm)" 797

# 3. Iniciar webhook (em outro terminal/pod)
python main/kuma_webhook_enricher.py

# 4. Configurar notificações no Kuma apontando pro webhook
# (veja docs/WEBHOOK_ENRICHER_SETUP.md)
```

### Cenário 2: Adicionar novo prefixo com webhook

```bash
# Sync novo prefixo
python main/sync_kuma.py

# Adicionar ao grupo
python main/sync_kuma.py update services- "waster-project (services)" <group_id>

# Webhook já enriquece automaticamente!
```

### Cenário 3: Forçar re-sincronização

```bash
# Remove e readiciona todos os monitors
python main/sync_kuma.py

# Se quiser organizar novamente em grupos
python main/sync_kuma.py update gtm- "waster-project (gtm)" 797
```

---

## 🚀 Fluxo Recomendado

1. **Primeiro upload (única vez):**
   ```bash
   python main/sync_kuma.py
   ```

2. **Organizar em grupos (após upload):**
   ```bash
   python main/sync_kuma.py update gtm- "waster-project (gtm)" 797
   ```

3. **Deploy do webhook enricher:**
   ```bash
   kubectl apply -f main/webhook-enricher-deployment.yaml
   ```

4. **Configurar notificações no Kuma:**
   - Ir em `Settings` → `Notifications`
   - Adicionar novo webhook customizado
   - URL: `http://kuma-webhook-enricher:5000/webhook/kuma-alert`
   - Incluir webhooks Discord/Telegram no body (veja docs)

5. **Próximos prefixos (conforme solicitado):**
   ```bash
   python main/sync_kuma.py update <novo-prefixo> "<novo-grupo>" <group_id>
   ```

---

## ❓ Dúvidas Comuns

**P: Posso rodar o comando de update sem ter rodado sync antes?**
R: Sim! O update apenas modifica monitors que já existem. Ele não cria novos.

**P: Quanto tempo leva para atualizar 412 monitors?**
R: Aproximadamente 1-2 minutos (0.2s × 412 = 82s + delay).

**P: Preciso parar o Kuma durante a sincronização?**
R: Não, ele continua funcionando normalmente.

**P: O webhook enriquecedor interfere nas notificações padrão?**
R: Não! Ele apenas intercepta e enriquece. Se algo falhar, o Kuma continua enviando a notificação padrão.

**P: Como encontrar o Group ID?**
R: No Kuma, vá em `Monitors` → Clique na setinha do grupo → Inspect no DevTools → Network tab → procure pelo ID na requisição.

**P: Posso usar o webhook com múltiplos canais (Discord + Telegram)?**
R: Sim! Configure ambos no body da notificação no Kuma.

---

## 📞 Suporte

Se encontrar erros, verifique:
- ✅ Credenciais Kuma estão corretas
- ✅ URL do Kuma está acessível
- ✅ Cluster K8s está disponível
- ✅ RBAC foi aplicado (`kubectl get rolebinding -n analytics`)
- ✅ Webhook está rodando (`kubectl logs -n analytics -f deployment/kuma-webhook-enricher`)
- ✅ Conectividade entre Kuma e webhook (`kubectl exec -it ...pod... -- curl http://kuma-webhook-enricher:5000/health`)

---

## 📚 Arquivos Relacionados

- [WEBHOOK_ENRICHER_SETUP.md](WEBHOOK_ENRICHER_SETUP.md) - Setup detalhado do enriquecedor
- `main/sync_kuma.py` - Script principal de sincronização
- `main/kuma_webhook_enricher.py` - Servidor webhook
- `main/webhook-enricher-deployment.yaml` - Manifest K8s
- `main/rbac.yaml` - Permissões necessárias
