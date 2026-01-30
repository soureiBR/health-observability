import os
from kubernetes import client, config
from uptime_kuma_api import UptimeKumaApi, MonitorType

# Variáveis vindas do export que você fez
KUMA_URL = os.getenv("KUMA_URL", "https://status.soureicdn.com")
KUMA_USER = os.getenv("KUMA_USER")
KUMA_PASS = os.getenv("KUMA_PASS")

def get_k8s_deployments():
    """Usa a Client Library para buscar no namespace analytics"""
    try:
        try:
            config.load_incluster_config()
        except:
            config.load_kube_config()

        apps_v1 = client.AppsV1Api()
        # Busca no namespace que você criou: analytics
        deps = apps_v1.list_namespaced_deployment(namespace="analytics")
        
        active_services = []
        for dep in deps.items:
            name = dep.metadata.name
            if name.startswith("gtm-"):
                identifier = name.replace("gtm-", "")
                active_services.append({
                    "name": name,
                    "url": f"https://{identifier}.soureicdn.com/debug/healthz"
                })
        return active_services
    except Exception as e:
        print(f"❌ Erro K8s: {e}")
        return []

def sync_to_kuma(services):
    """Loga no Kuma e sincroniza os monitores"""
    if not services:
        print("⚠️ Nenhum serviço gtm- encontrado.")
        return

    try:
        api = UptimeKumaApi(KUMA_URL)
        api.login(KUMA_USER, KUMA_PASS)
        print("🔓 Logado no Uptime Kuma com sucesso!")

        existing_monitors = api.get_monitors()
        kuma_names = [m['name'] for m in existing_monitors]

        for srv in services:
            if srv['name'] not in kuma_names:
                print(f"➕ Criando monitor: {srv['name']}")
                api.add_monitor(
                    type=MonitorType.HTTP,
                    name=srv['name'],
                    url=srv['url'],
                    interval=60
                )
            else:
                print(f"✅ {srv['name']} já existe no Kuma.")
        
        api.disconnect()
    except Exception as e:
        print(f"❌ Erro Kuma: {e}")

if __name__ == "__main__":
    print("🚀 Iniciando Sincronização Completa...")
    services_found = get_k8s_deployments()
    print(f"🔍 Encontrados {len(services_found)} serviços no K8s.")
    sync_to_kuma(services_found)
    print("🏁 Processo finalizado.")