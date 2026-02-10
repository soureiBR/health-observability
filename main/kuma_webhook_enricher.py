"""
Webhook Server para enriquecer notificações do Kuma com logs do Kubernetes
Recebe notificações de falha do Kuma, captura logs/describe do pod, e reenvia enriquecido
"""

from flask import Flask, request, jsonify
from kubernetes import client, config
import subprocess
import requests
import re
from datetime import datetime

app = Flask(__name__)

NAMESPACE = "analytics"

def extract_http_status(error_msg: str) -> tuple:
    """Extrai status HTTP e código da mensagem de erro"""
    match = re.search(r'(\d{3})', error_msg)
    status_code = int(match.group(1)) if match else None
    
    status_messages = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        500: "Internal Server Error",
        502: "Bad Gateway",
        503: "Service Unavailable",
        504: "Gateway Timeout",
    }
    
    return status_code, status_messages.get(status_code, "Unknown Error")

def get_pod_logs(pod_name: str, namespace: str = NAMESPACE, tail_lines: int = 50) -> str:
    """Pega os últimos logs do pod"""
    try:
        v1 = client.CoreV1Api()
        logs = v1.read_namespaced_pod_log(
            pod_name,
            namespace,
            tail_lines=tail_lines,
            timestamps=True
        )
        return logs[-1500:] if len(logs) > 1500 else logs
    except Exception as e:
        return f"❌ Erro ao buscar logs: {str(e)[:200]}"

def get_pod_describe(pod_name: str, namespace: str = NAMESPACE) -> str:
    """Faz describe do pod (útil para Pending/Failed)"""
    try:
        result = subprocess.run(
            ['kubectl', 'describe', 'pod', pod_name, '-n', namespace],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            output = result.stdout
            return output[-1500:] if len(output) > 1500 else output
        else:
            return f"Erro: {result.stderr[:200]}"
    except Exception as e:
        return f"❌ Erro ao descrever pod: {str(e)[:200]}"

def get_pod_status(deployment_name: str, namespace: str = NAMESPACE) -> dict:
    """Retorna status detalhado do pod relacionado ao deployment"""
    try:
        v1 = client.CoreV1Api()
        pods = v1.list_namespaced_pod(namespace)
        
        print(f"   🔍 Buscando pod para: '{deployment_name}'")
        all_pod_names = [p.metadata.name for p in pods.items]
        print(f"   📋 Total de pods no namespace: {len(all_pod_names)}")
        if all_pod_names[:3]:
            print(f"      Exemplos: {all_pod_names[:3]}")
        
        for pod in pods.items:
            pod_name = pod.metadata.name.lower()
            deployment_name_lower = deployment_name.lower()
            
            # Tenta diferentes formas de match
            matches = False
            if deployment_name_lower in pod_name:
                matches = True
            elif pod_name.startswith(deployment_name_lower):
                matches = True
            elif deployment_name_lower.replace("gtm-", "") in pod_name:
                matches = True
            
            if matches:
                pod_name = pod.metadata.name
                status = pod.status.phase
                
                info = {
                    'pod_name': pod_name,
                    'status': status,
                    'logs': '',
                    'describe': '',
                    'ready': False,
                    'containers': []
                }
                
                # Checa condições
                if pod.status.conditions:
                    for condition in pod.status.conditions:
                        if condition.type == 'Ready':
                            info['ready'] = condition.status == 'True'
                
                # Lista containers
                if pod.spec.containers:
                    info['containers'] = [c.name for c in pod.spec.containers]
                
                # Busca logs/describe baseado no status
                if status == 'Pending':
                    info['describe'] = get_pod_describe(pod_name, namespace)
                elif status == 'Running':
                    info['logs'] = get_pod_logs(pod_name, namespace)
                elif status == 'Failed':
                    info['describe'] = get_pod_describe(pod_name, namespace)
                    info['logs'] = get_pod_logs(pod_name, namespace)
                
                return info
        
        return {
            'pod_name': 'Não encontrado',
            'status': 'Unknown',
            'logs': '',
            'describe': '',
            'ready': False,
            'containers': []
        }
    except Exception as e:
        return {
            'pod_name': 'Erro na conexão',
            'status': 'Error',
            'logs': str(e)[:200],
            'describe': '',
            'ready': False,
            'containers': []
        }

def format_discord_message(monitor_name: str, service_url: str, error_msg: str, pod_info: dict) -> dict:
    """Formata mensagem para Discord (embed)"""
    
    status_code, status_name = extract_http_status(error_msg)
    
    embed = {
        "title": f"❌ {monitor_name} CAIU",
        "color": 15158332,
        "fields": [
            {
                "name": "📊 Status HTTP",
                "value": f"{status_code} - {status_name}" if status_code else error_msg[:100],
                "inline": True
            },
            {
                "name": "🔗 URL",
                "value": service_url,
                "inline": False
            },
            {
                "name": "🐳 Pod Status",
                "value": pod_info['status'],
                "inline": True
            },
            {
                "name": "✓ Pronto",
                "value": "✅ Sim" if pod_info['ready'] else "❌ Não",
                "inline": True
            },
            {
                "name": "📦 Pod Name",
                "value": pod_info['pod_name'][:100],
                "inline": False
            },
        ],
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Adiciona describe para Pending
    if pod_info['status'] == 'Pending' and pod_info['describe']:
        embed["fields"].append({
            "name": "📋 Describe do Pod (Por quê não subiu?)",
            "value": f"```\n{pod_info['describe'][:500]}...\n```",
            "inline": False
        })
    
    # Adiciona describe + logs para Failed
    elif pod_info['status'] == 'Failed':
        if pod_info['describe']:
            embed["fields"].append({
                "name": "📋 Describe do Pod",
                "value": f"```\n{pod_info['describe'][:300]}\n```",
                "inline": False
            })
        if pod_info['logs']:
            embed["fields"].append({
                "name": "📝 Logs do Container",
                "value": f"```\n{pod_info['logs'][-500:]}\n```",
                "inline": False
            })
    
    # Adiciona logs para Running
    elif pod_info['status'] == 'Running' and pod_info['logs']:
        embed["fields"].append({
            "name": "📝 Últimos Logs",
            "value": f"```\n{pod_info['logs'][-500:]}\n```",
            "inline": False
        })
    
    return {"embeds": [embed]}

def format_telegram_message(monitor_name: str, service_url: str, error_msg: str, pod_info: dict) -> str:
    """Formata mensagem para Telegram"""
    
    status_code, status_name = extract_http_status(error_msg)
    
    message = f"""
❌ **{monitor_name} CAIU** ❌

📊 **Status HTTP**: {status_code} - {status_name if status_code else error_msg[:100]}
🔗 **URL**: {service_url}
⏰ **Hora**: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

🐳 **Pod Info**:
   • Status: {pod_info['status']}
   • Pod Name: {pod_info['pod_name']}
   • Pronto: {'✅ Sim' if pod_info['ready'] else '❌ Não'}
"""
    
    if pod_info['status'] == 'Pending' and pod_info['describe']:
        message += f"\n📋 **Descrição (Investigue por quê não subiu)**:\n```\n{pod_info['describe'][:400]}...\n```"
    
    elif pod_info['status'] == 'Failed':
        if pod_info['describe']:
            message += f"\n📋 **Describe**:\n```\n{pod_info['describe'][:300]}\n```"
        if pod_info['logs']:
            message += f"\n📝 **Logs**:\n```\n{pod_info['logs'][-400:]}\n```"
    
    elif pod_info['status'] == 'Running' and pod_info['logs']:
        message += f"\n📝 **Últimos Logs**:\n```\n{pod_info['logs'][-400:]}\n```"
    
    return message

@app.route('/health', methods=['GET'])
@app.route('/webhook/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({"status": "ok"}), 200

@app.route('/webhook/kuma-alert', methods=['POST'])
def kuma_alert_webhook():
    """
    Webhook que recebe alertas do Kuma e enriquece com logs do K8s
    """
    try:
        data = request.json
        
        monitor_name = data.get('monitor_name', 'Unknown')
        service_url = data.get('service_url', '')
        error_msg = data.get('error', 'Unknown error')
        discord_webhook = data.get('discord_webhook')
        telegram_url = data.get('telegram_url')
        telegram_chat_id = data.get('telegram_chat_id')
        
        print(f"📥 Webhook recebido para: {monitor_name}")
        
        # Extrai nome do deployment
        deployment_name = monitor_name.replace("gtm-", "")
        
        # Busca informações do pod
        pod_info = get_pod_status(deployment_name)
        print(f"   Pod Status: {pod_info['status']}")
        
        # Envia para Discord
        if discord_webhook:
            try:
                discord_msg = format_discord_message(monitor_name, service_url, error_msg, pod_info)
                r = requests.post(discord_webhook, json=discord_msg, timeout=10)
                print(f"   ✅ Discord enviado - Status: {r.status_code}")
            except Exception as e:
                print(f"   ❌ Erro ao enviar Discord: {e}")
        
        # Envia para Telegram
        if telegram_url and telegram_chat_id:
            try:
                telegram_msg = format_telegram_message(monitor_name, service_url, error_msg, pod_info)
                telegram_data = {
                    "chat_id": telegram_chat_id,
                    "text": telegram_msg,
                    "parse_mode": "Markdown"
                }
                r = requests.post(telegram_url, json=telegram_data, timeout=10)
                print(f"   ✅ Telegram enviado - Status: {r.status_code}")
            except Exception as e:
                print(f"   ❌ Erro ao enviar Telegram: {e}")
        
        return jsonify({
            "status": "ok",
            "monitor": monitor_name,
            "pod_info": pod_info
        }), 200
        
    except Exception as e:
        print(f"❌ Erro no webhook: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    try:
        config.load_incluster_config()
        print("✅ Kubernetes config carregado (in-cluster)")
    except:
        try:
            config.load_kube_config()
            print("✅ Kubernetes config carregado (local)")
        except Exception as e:
            print(f"⚠️ Aviso: Não consegui carregar config K8s: {e}")
    
    print("🚀 Iniciando Webhook Enricher...")
    print("📡 Escutando em http://0.0.0.0:5000/webhook/kuma-alert")
    app.run(host='0.0.0.0', port=5000, debug=False)