# SaladCloud Configuration for Instagram Bio Collector

Este guia explica como configurar e executar o Instagram Bio Collector no SaladCloud.

## Configuração no SaladCloud Portal

### 1. Preparar a Imagem Docker

Primeiro, você precisa construir e fazer upload da imagem Docker para um registry (Docker Hub, GitHub Container Registry, etc.).

```bash
# Construir a imagem
docker build -t seu-usuario/instagram-bio-collector:latest .

# Fazer upload para Docker Hub (exemplo)
docker push seu-usuario/instagram-bio-collector:latest
```

### 2. Configurar Container Group no SaladCloud

1. **Acesse o SaladCloud Portal** (https://portal.salad.com/)
2. **Vá para "Container Groups"**
3. **Clique em "Create Container Group"**

### 3. Configurações Básicas

- **Container Group Name**: `instagram-bio-collector`
- **Container Image**: `seu-usuario/instagram-bio-collector:latest`
- **Command**: `python3 main_instaloader.py nordvpn`

### 4. Variáveis de Ambiente (OBRIGATÓRIAS)

Configure estas variáveis na seção "Environment Variables":

```
MONGO_CONNECTION_STRING=mongodb://seu-usuario:senha@host:porta/database
MONGO_DB=nome_do_banco
MONGO_COLLECTION=nome_da_colecao
API_ROUTE=https://sua-api.com/endpoint
SECRET_TOKEN=seu_token_secreto
VPN_SERVICE=nordvpn
```

### 5. Configurações de Recursos

**Recursos Recomendados por Instância:**
- **vCPUs**: 1-2 (dependendo da carga)
- **Memory**: 1-2 GB
- **Storage**: 1-5 GB

**Para múltiplas instâncias:**
- **Replicas**: 30 (ou quantas quiser executar simultaneamente)

### 6. Configurações de Rede e Segurança

⚠️ **IMPORTANTE**: Para usar VPN, você precisa de privilégios especiais:

- **Privileged Mode**: ✅ Habilitado
- **Capabilities**: Adicione `NET_ADMIN` e `SYS_MODULE`

### 7. Monitoring e Logging

- **Health Check**: Configure um endpoint simples se necessário
- **Logs**: Os logs serão armazenados em `/app/logs` dentro do container

## Configurações Avançadas

### Distribuição de Carga

Para otimizar a distribuição entre as 30 instâncias, considere modificar o código para:

1. **Usar ID único por instância** (já configurado via hostname)
2. **Distribuir perfis** baseado no ID da instância
3. **Evitar conflitos** entre instâncias

### Exemplo de Modificação no Código

```python
import os

# No início do main()
instance_id = os.getenv('INSTANCE_ID', '0')
instance_count = int(os.getenv('INSTANCE_COUNT', '1'))

# Modificar a query do MongoDB para distribuir trabalho
def get_profiles_from_db_distributed(collection, instance_id, instance_count, log):
    # Usar modulo para distribuir perfis
    query = {
        "status": "pending",
        "$expr": {
            "$eq": [
                {"$mod": [{"$toInt": "$_id"}, instance_count]},
                int(instance_id)
            ]
        }
    }
    # resto da função...
```

## Estimativa de Custos

**Configuração sugerida para 30 instâncias:**
- 30 × 1 vCPU × 1GB RAM
- Região de menor custo disponível
- Execute apenas quando necessário

**Cálculo aproximado**: Consulte os preços atuais no portal SaladCloud.

## Troubleshooting

### Problemas Comuns:

1. **Container não inicia**:
   - Verifique as variáveis de ambiente
   - Confirme que a imagem foi construída corretamente

2. **VPN não conecta**:
   - Verifique se `privileged: true` está configurado
   - Confirme que os arquivos de credenciais estão corretos

3. **Rate limiting mesmo com VPN**:
   - Aumente o delay entre requisições
   - Reduza o número de requisições antes de trocar VPN

4. **Instâncias conflitando**:
   - Implemente distribuição de trabalho por instância
   - Use locks distribuídos no MongoDB

### Logs Úteis:

```bash
# Ver logs de uma instância específica no SaladCloud
# (usar interface web do portal)

# Verificar status da VPN
docker exec container_id ip route

# Verificar IP atual
docker exec container_id curl ifconfig.me
```

## Monitoramento

Para monitorar o progresso:

1. **MongoDB**: Acompanhe contadores de status na coleção
2. **Logs**: Use agregação de logs no SaladCloud
3. **API**: Monitor de requisições no seu endpoint

## Otimizações

1. **Usar regiões próximas** ao MongoDB e API
2. **Configurar auto-scaling** baseado na fila de perfis
3. **Implementar circuit breaker** para falhas de VPN
4. **Cache local** de dados já coletados

---

**Próximos Passos:**
1. Construir e fazer upload da imagem Docker
2. Configurar as variáveis de ambiente no SaladCloud
3. Criar o Container Group com 30 réplicas
4. Monitorar os primeiros execuções
5. Ajustar recursos conforme necessário