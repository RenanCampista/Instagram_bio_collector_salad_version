#!/bin/bash

# Script para construir e fazer deploy da aplicação no SaladCloud versão linux

set -e

# Configurações - MODIFIQUE ESTAS VARIÁVEIS
DOCKER_USERNAME="renan2002"  # Seu usuário do Docker Hub
IMAGE_NAME="instagram-bio-collector"
VERSION="latest"
FULL_IMAGE_NAME="${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}"

echo "Construindo imagem Docker: $FULL_IMAGE_NAME"

# Verificar se Docker está rodando
if ! docker info > /dev/null 2>&1; then
    echo "ERRO: Docker não está rodando. Inicie o Docker primeiro."
    exit 1
fi

# Construir a imagem
echo "Construindo imagem..."
docker build -t "$FULL_IMAGE_NAME" .

echo "Imagem construída com sucesso!"

# Perguntar se deve fazer upload
read -p "Fazer upload para Docker Hub? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Fazendo upload para Docker Hub..."
    
    # Login no Docker Hub
    echo "Faça login no Docker Hub:"
    docker login
    
    # Fazer upload
    docker push "$FULL_IMAGE_NAME"
    
    echo "Upload concluído!"
    echo ""
    echo "Informações para o SaladCloud:"
    echo "   Image: $FULL_IMAGE_NAME"
    echo "   Command: python3 main_instaloader_salad.py nordvpn"
    echo ""
    echo "Configure estas variáveis de ambiente no SaladCloud:"
    echo "   - MONGO_CONNECTION_STRING"
    echo "   - MONGO_DB" 
    echo "   - MONGO_COLLECTION"
    echo "   - API_ROUTE"
    echo "   - SECRET_TOKEN"
    echo "   - VPN_SERVICE (opcional, padrão: nordvpn)"
else
    echo "Upload cancelado. Para fazer upload mais tarde:"
    echo "   docker push $FULL_IMAGE_NAME"
fi

echo ""
echo "Consulte SALAD_SETUP.md para instruções completas de configuração!"