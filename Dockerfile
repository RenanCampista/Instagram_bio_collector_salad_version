# Use Ubuntu como base para suporte ao OpenVPN
FROM ubuntu:22.04

# Evitar prompts interativos durante a instalação
ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    openvpn \
    iptables \
    curl \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# Definir diretório de trabalho
WORKDIR /app

# Copiar requirements primeiro (para melhor cache do Docker)
COPY requirements.txt .

# Instalar dependências Python
RUN pip3 install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY src/ ./src/
COPY main_instaloader.py .
COPY main_instaloader_salad.py .
COPY nordvpn_credentials.txt .
COPY protonvpn_credentials.txt .

# Copiar arquivos VPN
COPY vpn_files/ ./vpn_files/

# Criar diretório de logs
RUN mkdir -p logs/bio_collector_instaloader

# Criar diretório para executáveis do OpenVPN
RUN mkdir -p /dev/net && \
    mknod /dev/net/tun c 10 200 || true

# Script para configurar permissões e executar a aplicação
COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Definir variáveis de ambiente padrão
ENV VPN_SERVICE=nordvpn
ENV PYTHONUNBUFFERED=1

# Expor porta para logs/monitoramento (opcional)
EXPOSE 8080

# Usar entrypoint para configurações especiais
ENTRYPOINT ["/entrypoint.sh"]

# Comando padrão - usar versão otimizada para SaladCloud
CMD ["python3", "main_instaloader_salad.py", "nordvpn"]