import time
from uptime_kuma_api import UptimeKumaApi, MonitorType
from kubernetes import client, config
import socketio
import json

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
                # Remove o prefixo 'gtm-' para gerar o subdomínio correto
                identifier = name.replace("gtm-", "")
                
                k8s_list.append({
                    'name': name,
                    'url': f"https://{identifier}.soureicdn.com/debug/healthz"
                })
        
        k8s_names = [d['name'] for d in k8s_list]
        print(f"✅ [K8s] {len(k8s_list)} serviços identificados (Desejado > 0).")

    except Exception as e:
        print(f"❌ [ERRO K8S] {e}")
        return

    print(f"🚀 [PASSO 2] Sincronizando com Uptime Kuma...")
    try:
        with UptimeKumaApi(KUMA_URL, timeout=300) as api:
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

def update_monitor_group(prefix: str, group_name: str, group_id: int = None):
    """
    Atualiza monitors existentes para adicionar ao Monitor Group usando Socket.io
    
    Exemplo:
        update_monitor_group("gtm-", "waster-project (gtm)", group_id=797)
    """
    print(f"🚀 [ATUALIZAÇÃO] Adicionando monitors com prefixo '{prefix}' ao grupo '{group_name}'...")
    try:
        with UptimeKumaApi(KUMA_URL) as api:
            api.login(KUMA_USER, KUMA_PASS)
            
            # Se group_id não foi fornecido, tenta encontrar
            if group_id is None:
                print("📋 Buscando grupos existentes...")
                try:
                    groups = api.get_monitor_groups()
                    target_group = next((g for g in groups if g.get('name') == group_name), None)
                    if not target_group:
                        print(f"❌ Grupo '{group_name}' não encontrado!")
                        print(f"   💡 Grupos disponíveis: {[g.get('name') for g in groups]}")
                        return
                    group_id = target_group['id']
                    print(f"✅ Grupo '{group_name}' encontrado com ID: {group_id}\n")
                except Exception as e:
                    print(f"⚠️ Não consegui buscar grupos automaticamente: {e}")
                    return
            
            monitors = api.get_monitors()
            filtered_monitors = [m for m in monitors if m['name'].startswith(prefix)]
            
            print(f"📊 {len(filtered_monitors)} monitors encontrados para atualizar")
            
            success = 0
            failed = 0
            
            # Usa o Socket.io da api para enviar editMonitor diretamente
            sio = api.sio
            
            # Campos que causam problemas e devem ser ignorados
            campos_ignore = ['notificationIDList', 'screenshot']
            
            for monitor in filtered_monitors:
                try:
                    # Cria minimal monitor object com APENAS campos não-null + parent
                    monitor_data = {k: v for k, v in monitor.items() 
                                   if v is not None and k not in campos_ignore}
                    monitor_data['parent'] = group_id
                    
                    # Envia diretamente via Socket.io
                    result = sio.call('editMonitor', monitor_data, timeout=10)
                    
                    if result and result.get('ok'):
                        success += 1
                        print(f"✅ {monitor['name']}")
                    else:
                        failed += 1
                        error = result.get('msg', 'Erro desconhecido') if result else 'Sem resposta'
                        print(f"⚠️ {monitor['name']}: {error}")
                    
                    time.sleep(0.2)
                except Exception as e:
                    failed += 1
                    error_msg = str(e)[:80]
                    print(f"⚠️ {monitor['name']}: {error_msg}")
                    time.sleep(0.2)
            
            print(f"\n🏁 Atualização finalizada!")
            print(f"   ✅ Sucesso: {success}")
            print(f"   ❌ Falhas: {failed}")
            
    except Exception as e:
        print(f"❌ [ERRO] {e}")

if __name__ == "__main__":
    import sys
    
    # Se quiser rodar o update manual via comando
    if len(sys.argv) > 1 and sys.argv[1] == "update":
        prefix = sys.argv[2] if len(sys.argv) > 2 else "gtm-"
        group = sys.argv[3] if len(sys.argv) > 3 else "waster-project (gtm)"
        group_id = int(sys.argv[4]) if len(sys.argv) > 4 else None
        update_monitor_group(prefix, group, group_id)
    
    # Modo padrão: Sincronização contínua
    else:
        while True:
            sync()
            print("⏳ Aguardando 10 minutos para a próxima sincronização...")
            time.sleep(600)  # 600 segundos = 10 minutos