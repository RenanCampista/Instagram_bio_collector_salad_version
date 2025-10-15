#!/bin/bash

# Script de entrada para configurar o container e executar a aplicação

set -e

echo "Iniciando Instagram Bio Collector no SaladCloud..."

# Verificar se estamos rodando com privilégios necessários para VPN
if [ ! -c /dev/net/tun ]; then
    echo "Criando dispositivo TUN para VPN..."
    mkdir -p /dev/net
    mknod /dev/net/tun c 10 200 2>/dev/null || true
    chmod 666 /dev/net/tun 2>/dev/null || true
fi

# Configurar iptables se necessário
echo "Configurando iptables..."
iptables -P FORWARD ACCEPT 2>/dev/null || echo "Não foi possível configurar iptables (pode ser normal em containers)"

# Verificar variáveis de ambiente obrigatórias
echo "Verificando variáveis de ambiente..."
required_vars=("MONGO_CONNECTION_STRING" "MONGO_DB" "MONGO_COLLECTION" "API_ROUTE" "SECRET_TOKEN" "VPN_USERNAME" "VPN_PASSWORD")
missing_vars=()

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "ERRO: Variáveis de ambiente obrigatórias não definidas:"
    printf '   - %s\n' "${missing_vars[@]}"
    echo ""
    echo "Configure estas variáveis no SaladCloud Portal:"
    echo "   MONGO_CONNECTION_STRING: String de conexão do MongoDB"
    echo "   MONGO_DB: Nome do banco de dados"
    echo "   MONGO_COLLECTION: Nome da coleção"
    echo "   API_ROUTE: URL da API para enviar dados"
    echo "   SECRET_TOKEN: Token de autenticação da API"
    echo "   VPN_USERNAME: Usuário da VPN"
    echo "   VPN_PASSWORD: Senha da VPN"
    exit 1
fi

# Configurar serviço VPN baseado na variável de ambiente
VPN_SERVICE=${VPN_SERVICE:-nordvpn}
echo "Usando serviço VPN: $VPN_SERVICE"

# Verificar se diretório VPN existe
if [ ! -d "vpn_files/$VPN_SERVICE" ]; then
    echo "ERRO: Diretório VPN não encontrado: vpn_files/$VPN_SERVICE"
    exit 1
fi

# Log informações do sistema
echo "Informações do sistema:"
echo "   - Hostname: $(hostname)"
echo "   - IP atual: $(curl -s ifconfig.me || echo 'Não disponível')"
echo "   - Arquivos VPN disponíveis: $(ls vpn_files/$VPN_SERVICE/*.ovpn | wc -l)"

# Adicionar ID único da instância baseado no hostname
INSTANCE_ID=$(hostname | tail -c 8)
export INSTANCE_ID

echo "ID da instância: $INSTANCE_ID"

# Executar comando passado como argumento
echo "Executando: $@"
exec "$@"