import os
from kubernetes import client, config
from uptime_kuma_api import UptimeKumaApi, MonitorType

def get_k8s_deployments():
    """Usa a Client Library oficial para listar deployments locais"""
    try:
        # Tenta carregar a config interna (para quando for CronJob)
        # Se falhar, usa a config do seu terminal (Docker Desktop)
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()

        # Instancia a API para lidar com Apps (Deployments)
        apps_v1 = client.AppsV1Api()
        
        # Lista os deployments do namespace 'default'
        # (Onde você criou o gtm-local-test)
        deployments = apps_v1.list_namespaced_deployment(namespace="default")
        
        active_list = []
        for dep in deployments.items:
            name = dep.metadata.name
            
            # Filtro para identificar seus serviços
            if name.startswith("gtm-"):
                # No seu PC, a URL será apenas para teste
                identifier = name.replace("gtm-", "")
                active_list.append({
                    "name": name,
                    "url": f"https://{identifier}.soureicdn.com/debug/healthz"
                })
        return active_list
    except Exception as e:
        print(f"❌ Erro ao usar a Client Library: {e}")
        return []

if __name__ == "__main__":
    print("🚀 Testando conexão com o Docker Desktop...")
    services = get_k8s_deployments()
    
    if services:
        print(f"✅ Sucesso! Encontrei {len(services)} serviço(s):")
        for s in services:
            print(f" - {s['name']} (URL: {s['url']})")
    else:
        print("⚠️ Nenhum deployment 'gtm-' encontrado no namespace default.")