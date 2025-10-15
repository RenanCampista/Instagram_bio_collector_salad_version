# Configuração SaladCloud - Instagram Bio Collector

## Configuração do Container Group

### Imagem Docker
```
renan2002/instagram-bio-collector:latest
```

### Configurações Básicas
- **Réplicas**: 30 (recomendado para máxima eficiência)
- **CPU**: 0.5 vCPU por container
- **Memória**: 1GB por container  
- **Restart Policy**: Always (essencial para rotação de IPs)

### Variáveis de Ambiente
```yaml
MONGO_CONNECTION_STRING: "mongodb://readwrite:e2f774eE7d8616cD553238e913e501c@159.89.39.93:27018/?authSource=admin"
MONGO_DB: "Search_terms"
MONGO_COLLECTION: "profiles_bio"
API_ROUTE: "http://159.89.254.129:8000/instagram/profile/json"
SECRET_TOKEN: "%45+_@.:31VJ_st%wcM8Z-ID"
TOTAL_INSTANCES: "30"  # Deve corresponder ao número de réplicas
```

### Configurações Avançadas
```yaml
# Restart Policy (OBRIGATÓRIO)
restart_policy: always

# Resource Limits
resources:
  cpu: "0.5"
  memory: "1Gi"
  
# Logging
logging:
  driver: "json-file" 
  options:
    max-size: "10m"
    max-file: "3"
```

## Estratégia de Funcionamento

### Como Funciona a Rotação de IPs:
1. **Container inicia** → SaladCloud atribui IP único
2. **Processa ~120 perfis** → Sistema monitora rate limits
3. **Rate limit detectado** → Container reinicia automaticamente  
4. **Novo container** → SaladCloud atribui novo IP
5. **Ciclo se repete** → IPs sempre diferentes, bypass natural

### Benefícios desta Abordagem:
- **Simplicidade**: Sem VPN para configurar ou manter
- **Confiabilidade**: Não depende de servidores VPN externos
- **Escalabilidade**: Fácil aumentar réplicas para mais throughput
- **IPs Únicos**: SaladCloud garante IPs diferentes por container
- **Rate Limit Bypass**: Reinício automático transparente
- **Custo-benefício**: Sem custos adicionais de VPN

### Performance Esperada:
- **30 containers** × **120 perfis/ciclo** = **3.600 perfis/ciclo**
- **Ciclos por hora**: ~5 (considerando rate limits do Instagram)
- **Perfis por hora**: ~18.000
- **Perfis por dia**: ~432.000
- **Meta de 1 milhão**: ~2.3 dias

### Detecção Inteligente de Rate Limits:
- Mensagens "Please wait a few minutes before you try again"
- Códigos HTTP 429 (Too Many Requests)
- Erros de DNS temporários
- Múltiplos erros consecutivos (3+)

### Distribuição de Trabalho:
- Cada container processa perfis exclusivos (sem duplicatas)
- Sistema atômico de reserva de perfis no MongoDB
- Balanceamento automático entre instâncias
- Tolerância a falhas de containers individuais

## Comandos para Deploy

### Build e Push:
```bash
docker build -t renan2002/instagram-bio-collector:latest .
docker push renan2002/instagram-bio-collector:latest
```

### Teste Local:
```bash
docker run \
  -e MONGO_CONNECTION_STRING="..." \
  -e MONGO_DB="Search_terms" \
  -e MONGO_COLLECTION="profiles_bio" \
  -e API_ROUTE="..." \
  -e SECRET_TOKEN="..." \
  -e TOTAL_INSTANCES="1" \
  renan2002/instagram-bio-collector:latest
```

### Monitoramento:
- Logs mostram IP de cada container na inicialização
- Estatísticas de performance por instância
- Detecção automática e logging de rate limits
- Contadores de sucessos/erros por container

---

**Esta estratégia utiliza a infraestrutura do SaladCloud de forma nativa e eficiente para bypass de rate limits.**