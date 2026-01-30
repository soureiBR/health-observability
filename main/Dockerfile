FROM python:3.11-slim

# Instala o kubectl (necessário para rodar os comandos do K8s)
RUN apt-get update && apt-get install -y curl && \
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && \
    chmod +x kubectl && mv kubectl /usr/local/bin/

WORKDIR /app

# Instala as dependências do Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o script
COPY sync_kuma.py .

# Comando para rodar o script
CMD ["python", "sync_kuma.py"]