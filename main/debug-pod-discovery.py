#!/usr/bin/env python3
"""
Diagnóstico avançado para pod discovery
Mostra a relação entre deployments e pods
"""

from kubernetes import client, config
import sys

NAMESPACE = "analytics"

def main():
    # Tenta carregar config
    try:
        config.load_incluster_config()
        print("✅ Kubernetes config carregado (in-cluster)")
    except:
        try:
            config.load_kube_config()
            print("✅ Kubernetes config carregado (local)")
        except Exception as e:
            print(f"❌ Erro ao carregar config K8s: {e}")
            sys.exit(1)
    
    print("\n" + "="*80)
    print(f"📊 DIAGNÓSTICO DE POD DISCOVERY - Namespace: {NAMESPACE}")
    print("="*80 + "\n")
    
    # 1. Listar deployments
    print("📋 [1] DEPLOYMENTS COM PREFIXO 'gtm-':\n")
    try:
        apps_v1 = client.AppsV1Api()
        deployments = apps_v1.list_namespaced_deployment(NAMESPACE)
        
        gtm_deployments = [d for d in deployments.items if "gtm-" in d.metadata.name]
        
        if not gtm_deployments:
            print("   ⚠️ Nenhum deployment com prefixo 'gtm-' encontrado")
        else:
            print(f"   Total: {len(gtm_deployments)} deployments GTM\n")
            for i, dep in enumerate(gtm_deployments[:10], 1):
                print(f"   {i}. {dep.metadata.name}")
                print(f"      Replicas: {dep.spec.replicas} (desejado) / {dep.status.ready_replicas or 0} (ready)")
                
                # Labels que podem ser usados para encontrar pods
                if dep.spec.selector and dep.spec.selector.match_labels:
                    labels = dep.spec.selector.match_labels
                    print(f"      Selector: {labels}")
            
            if len(gtm_deployments) > 10:
                print(f"\n   ... e mais {len(gtm_deployments) - 10} deployments")
    except Exception as e:
        print(f"   ❌ Erro ao listar deployments: {e}")
    
    # 2. Listar todos os pods
    print("\n\n📋 [2] PODS NO NAMESPACE:\n")
    try:
        v1 = client.CoreV1Api()
        pods = v1.list_namespaced_pod(NAMESPACE)
        
        if not pods.items:
            print("   ⚠️ Nenhum pod encontrado")
        else:
            print(f"   Total: {len(pods.items)} pods\n")
            
            # Agrupa por deployment (via ownerReference)
            deployment_pods = {}
            other_pods = []
            
            for pod in pods.items:
                found_deployment = False
                
                # Tenta encontrar deployment via ownerReference
                if pod.metadata.owner_references:
                    for owner in pod.metadata.owner_references:
                        if owner.kind == 'ReplicaSet':
                            # O ReplicaSet foi criado pelo Deployment
                            # Nome do ReplicaSet começa com deployment-name
                            # Tenta extrair deployment name
                            rs_name = owner.name
                            # Remove -xxxxx no final (hash do RS)
                            deployment_name = '-'.join(rs_name.split('-')[:-1])
                            
                            if deployment_name not in deployment_pods:
                                deployment_pods[deployment_name] = []
                            deployment_pods[deployment_name].append(pod)
                            found_deployment = True
                            break
                
                if not found_deployment:
                    other_pods.append(pod)
            
            # Mostra pods agrupados por deployment
            print("   Pods por Deployment:\n")
            for dep_name in sorted(deployment_pods.keys()):
                pods_list = deployment_pods[dep_name]
                if "gtm-" in dep_name:
                    print(f"   📦 {dep_name}")
                    for pod in pods_list:
                        status = pod.status.phase
                        ready = "✅" if pod.status.conditions and any(c.type == 'Ready' and c.status == 'True' for c in pod.status.conditions) else "❌"
                        print(f"      {ready} {pod.metadata.name} ({status})")
            
            if other_pods:
                print(f"\n   Outros pods ({len(other_pods)}):")
                for pod in other_pods[:5]:
                    print(f"      • {pod.metadata.name}")
                if len(other_pods) > 5:
                    print(f"      ... e mais {len(other_pods) - 5}")
    except Exception as e:
        print(f"   ❌ Erro ao listar pods: {e}")
    
    # 3. Testar pod discovery com um deployment
    print("\n\n🔍 [3] TESTE DE POD DISCOVERY:\n")
    try:
        if gtm_deployments:
            test_deployment = gtm_deployments[0]
            deployment_name = test_deployment.metadata.name
            deployment_name_no_prefix = deployment_name.replace("gtm-", "")
            
            print(f"   Testando com deployment: {deployment_name}\n")
            print(f"   Extraído (sem gtm-): {deployment_name_no_prefix}\n")
            
            # Simula a lógica de busca
            v1 = client.CoreV1Api()
            pods = v1.list_namespaced_pod(NAMESPACE)
            
            matches = []
            for pod in pods.items:
                pod_name = pod.metadata.name.lower()
                deployment_lower = deployment_name_no_prefix.lower()
                
                if deployment_lower in pod_name:
                    matches.append(("deployment_name in pod_name", pod.metadata.name, pod.status.phase))
                elif pod_name.startswith(deployment_lower):
                    matches.append(("pod_name.startswith()", pod.metadata.name, pod.status.phase))
                elif deployment_lower.replace("gtm-", "") in pod_name:
                    matches.append(("nome sem prefixo in pod_name", pod.metadata.name, pod.status.phase))
            
            if matches:
                print(f"   ✅ Encontrados {len(matches)} pods:")
                for rule, pod_name, status in matches:
                    print(f"      • {pod_name} ({status})")
                    print(f"        → Regra: {rule}")
            else:
                print(f"   ❌ Nenhum pod encontrado com as regras atuais\n")
                
                # Tenta usar labels/selectors
                print(f"\n   💡 Tentando por labels do deployment:\n")
                if test_deployment.spec.selector and test_deployment.spec.selector.match_labels:
                    label_selector = test_deployment.spec.selector.match_labels
                    selector_str = ','.join([f"{k}={v}" for k, v in label_selector.items()])
                    print(f"      Selector: {selector_str}")
                    
                    # Lista pods com esses labels
                    pods_with_labels = v1.list_namespaced_pod(
                        NAMESPACE,
                        label_selector=selector_str
                    )
                    
                    if pods_with_labels.items:
                        print(f"\n      ✅ Encontrados {len(pods_with_labels.items)} pods com labels:")
                        for pod in pods_with_labels.items:
                            print(f"         • {pod.metadata.name} ({pod.status.phase})")
                    else:
                        print(f"      ❌ Nenhum pod encontrado com esses labels")
    except Exception as e:
        print(f"   ❌ Erro no teste: {e}")
    
    print("\n" + "="*80 + "\n")

if __name__ == '__main__':
    main()
