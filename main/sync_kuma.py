import time
from uptime_kuma_api import UptimeKumaApi, MonitorType
from kubernetes import client, config
import os

# Configurações (Ajuste se necessário)
KUMA_URL = "https://status.soureicdn.com"
KUMA_USER = "admin"
KUMA_PASS = "3mUXcHwMajWM8S"
NAMESPACE = "analytics"
EXCLUDE_PATTERN = "proxy|preview|data-api"

def sync():
    print(f"🚀 [PASSO 1] Conectando ao Kubernetes (Namespace: {NAMESPACE})...")
    try:
        config.load_incluster_config()
        v1 = client.AppsV1Api()
        deployments = v1.list_namespaced_deployment(NAMESPACE)
        
        k8s_list = []
        for dep in deployments.items:
            # Filtro: Apenas GTMs ativos (1/1) e sem os termos proibidos
            name = dep.metadata.name
            if (dep.status.ready_replicas or 0) > 0 and not any(p in name for p in EXCLUDE_PATTERN.split('|')):
                k8s_list.append({
                    'name': name,
                    'url': f"https://{name}.soureicdn.com/debug/healthz"
                })
        
        k8s_names = [d['name'] for d in k8s_list]
        print(f"✅ [K8s] Encontrados {len(k8s_list)} serviços válidos para monitoramento.")

    except Exception as e:
        print(f"❌ [ERRO K8S] Falha ao ler cluster: {e}")
        return

    print(f"🚀 [PASSO 2] Conectando ao Uptime Kuma...")
    try:
        with UptimeKumaApi(KUMA_URL) as api:
            api.login(KUMA_USER, KUMA_PASS)
            print("✅ [Kuma] Login realizado com sucesso!")
            
            # Mapear o que já existe no Kuma
            monitors = api.get_monitors()
            kuma_monitors_map = {m['name']: m['id'] for m in monitors if m['name'].startswith("gtm-")}
            print(f"✅ [Kuma] Atualmente existem {len(kuma_monitors_map)} monitores 'gtm-' no painel.")

            # 1. ADICIONAR NOVOS
            print("🔍 Verificando se há novos serviços para adicionar...")
            for dep in k8s_list:
                if dep['name'] not in kuma_monitors_map:
                    try:
                        print(f"➕ [ADD] Criando: {dep['name']}")
                        api.add_monitor(
                            type=MonitorType.HTTP,
                            name=dep['name'],
                            url=dep['url'],
                            interval=300,
                            retryInterval=60
                        )
                        time.sleep(0.5) # Pausa para não estressar a API
                    except Exception as e_add:
                        print(f"⚠️ [ERRO ADD] Falha em {dep['name']}: {e_add}")

            # 2. REMOVER ANTIGOS / DUPLICADOS
            print("🔍 Verificando se há lixo para limpar...")
            for name, monitor_id in kuma_monitors_map.items():
                if name not in k8s_names:
                    try:
                        print(f"🗑️ [DEL] Removendo: {name} (ID: {monitor_id})")
                        api.delete_monitor(monitor_id)
                        time.sleep(0.5) # Pausa para não estressar a API
                    except Exception as e_del:
                        print(f"⚠️ [ERRO DEL] Falha ao deletar {name}: {e_del}")

            print("🏁 [FIM] Sincronização concluída com sucesso!")

    except Exception as e:
        print(f"❌ [ERRO CRÍTICO KUMA] Ocorreu uma falha na API: {e}")

if __name__ == "__main__":
    sync()