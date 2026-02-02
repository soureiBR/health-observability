import time
from uptime_kuma_api import UptimeKumaApi, MonitorType
from kubernetes import client, config

KUMA_URL = "https://status.soureicdn.com"
KUMA_USER = "admin"
KUMA_PASS = "3mUXcHwMajWM8S"
NAMESPACE = "analytics"
EXCLUDE_PATTERN = "proxy|preview|data-api"

def sync():
    print(f"🚀 [PASSO 1] Lendo Kubernetes...")
    try:
        config.load_incluster_config()
        v1 = client.AppsV1Api()
        deployments = v1.list_namespaced_deployment(NAMESPACE)
        
        k8s_list = []
        for dep in deployments.items:
            name = dep.metadata.name
            # Captura o valor após a barra (replicas desejadas)
            desired = dep.spec.replicas if dep.spec.replicas is not None else 0
            
            if desired > 0 and not any(p in name for p in EXCLUDE_PATTERN.split('|')):
                k8s_list.append({
                    'name': name,
                    'url': f"https://{name}.soureicdn.com/debug/healthz"
                })
        
        k8s_names = [d['name'] for d in k8s_list]
        print(f"✅ [K8s] {len(k8s_list)} serviços identificados (Desejado > 0).")

    except Exception as e:
        print(f"❌ [ERRO K8S] {e}")
        return

    print(f"🚀 [PASSO 2] Sincronizando com Uptime Kuma...")
    try:
        with UptimeKumaApi(KUMA_URL) as api:
            api.login(KUMA_USER, KUMA_PASS)
            monitors = api.get_monitors()
            kuma_monitors_map = {m['name']: m['id'] for m in monitors if m['name'].startswith("gtm-")}

            # 1. ADICIONAR / MANTER
            for dep in k8s_list:
                if dep['name'] not in kuma_monitors_map:
                    try:
                        print(f"➕ [ADD] {dep['name']}")
                        api.add_monitor(type=MonitorType.HTTP, name=dep['name'], url=dep['url'], interval=300)
                        time.sleep(0.8)
                    except Exception as e_add:
                        if "not logged in" in str(e_add).lower():
                            print("🔑 Relogando para adicionar...")
                            api.login(KUMA_USER, KUMA_PASS)
                            api.add_monitor(type=MonitorType.HTTP, name=dep['name'], url=dep['url'], interval=300)
                        else:
                            print(f"⚠️ Erro ADD {dep['name']}: {e_add}")

            # 2. REMOVER (Faxina)
            for name, monitor_id in kuma_monitors_map.items():
                if name not in k8s_names:
                    try:
                        print(f"🗑️ [DEL] {name}")
                        api.delete_monitor(monitor_id)
                        time.sleep(0.8)
                    except Exception as e_del:
                        if "not logged in" in str(e_del).lower():
                            print("🔑 Relogando para deletar...")
                            api.login(KUMA_USER, KUMA_PASS)
                            api.delete_monitor(monitor_id)
                        else:
                            print(f"⚠️ Erro DEL {name}: {e_del}")

            print("🏁 Sincronização finalizada!")
    except Exception as e:
        print(f"❌ [ERRO CRÍTICO KUMA] {e}")

if __name__ == "__main__":
    sync()