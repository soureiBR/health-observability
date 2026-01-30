import os
import re
from kubernetes import client, config
from uptime_kuma_api import UptimeKumaApi, MonitorType

# Configurações via Variáveis de Ambiente (Segurança)
KUMA_URL = os.getenv("KUMA_URL", "https://status.soureicdn.com")
KUMA_USER = os.getenv("KUMA_USER")
KUMA_PASS = os.getenv("KUMA_PASS")
NAMESPACE = os.getenv("K8S_NAMESPACE", "analytics")
EXCLUDE_PATTERN = "proxy|preview|data-api"

def get_k8s_deployments():
    """Busca deployments via API oficial com filtros do script original"""
    try:
        try:
            config.load_incluster_config()
        except:
            config.load_kube_config()

        apps_v1 = client.AppsV1Api()
        deps = apps_v1.list_namespaced_deployment(namespace=NAMESPACE)
        
        active_services = []
        for dep in deps.items:
            name = dep.metadata.name
            
            # 1. Filtro de exclusão (Regex original)
            if re.search(EXCLUDE_PATTERN, name):
                continue
            
            # 2. Filtro de Réplicas (Substitui o "0/0" do kubectl)
            replicas = dep.spec.replicas if dep.spec.replicas is not None else 0
            
            # Regra: Só processa se começar com gtm- e estiver ativo
            if name.startswith("gtm-") and replicas > 0:
                identifier = name.replace("gtm-", "")
                active_services.append({
                    "name": name,
                    "url": f"https://{identifier}.soureicdn.com/debug/healthz"
                })
                
        return active_services
    except Exception as e:
        print(f"❌ Erro K8s: {e}")
        return []

def sync():
    """Sincronização completa: Adiciona novos e REMOVE antigos"""
    k8s_list = get_k8s_deployments()
    k8s_names = [d['name'] for d in k8s_list]
    print(f"🔍 Ativos no K8s ({NAMESPACE}): {len(k8s_names)}")

    try:
        with UptimeKumaApi(KUMA_URL) as api:
            api.login(KUMA_USER, KUMA_PASS)
            
            # Pega monitores atuais do Kuma que começam com gtm-
            existing_monitors = api.get_monitors()
            kuma_monitors_map = {m['name']: m['id'] for m in existing_monitors if m['name'].startswith("gtm-")}

            # 1. ADICIONAR NOVOS
            for dep in k8s_list:
                if dep['name'] not in kuma_monitors_map:
                    print(f"➕ Adicionando: {dep['name']}")
                    api.add_monitor(
                        type=MonitorType.HTTP,
                        name=dep['name'],
                        url=dep['url'],
                        interval=300, # 5 minutos
                        retryInterval=60
                    )
                else:
                    print(f"✅ Mantendo: {dep['name']}")

            # 2. REMOVER ANTIGOS (Que não estão mais no K8s ou estão 0/0)
            for name, monitor_id in kuma_monitors_map.items():
                if name not in k8s_names:
                    print(f"🗑️ Removendo: {name} (Não encontrado ou inativo no K8s)")
                    api.delete_monitor(monitor_id)

    except Exception as e:
        print(f"❌ Erro Kuma: {e}")

if __name__ == "__main__":
    print("🚀 Iniciando Sincronização Inteligente...")
    sync()
    print("🏁 Processo finalizado.")