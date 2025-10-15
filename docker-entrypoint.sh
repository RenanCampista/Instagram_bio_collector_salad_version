#!/bin/bash

# Script de entrada para Instagram Bio Collector - Sem VPN
# Otimizado para rotação de containers no SaladCloud

set -e

echo "Iniciando Instagram Bio Collector no SaladCloud..."

# Verificar variáveis de ambiente obrigatórias
echo "Verificando variáveis de ambiente..."
required_vars=("MONGO_CONNECTION_STRING" "MONGO_DB" "MONGO_COLLECTION" "API_ROUTE" "SECRET_TOKEN")
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
    exit 1
fi

# Log informações do sistema
echo "Informações do sistema:"
echo "   - Hostname: $(hostname)"
echo "   - IP atual: $(curl -s ifconfig.me || echo 'Não disponível')"

# Adicionar ID único da instância baseado no hostname
INSTANCE_ID=$(hostname | tail -c 8)
export INSTANCE_ID

echo "   - Instance ID: $INSTANCE_ID"
echo ""

# Configurar política de restart para rotação de IP
echo "Estratégia: Rotação automática de containers para novos IPs"
echo "Rate limits: Restart automático quando detectados"
echo ""

# Executar aplicação principal
echo "Iniciando coleta de perfis Instagram..."
exec "$@"