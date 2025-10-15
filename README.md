# Instagram Bio Collector

Coletor automatizado de biografias de perfis do Instagram, otimizado para execução distribuída no SaladCloud com rotação automática de IPs.

## Características

- **Coleta sem autenticação**: Utiliza Instaloader para coletar dados sem login
- **Rotação automática de IPs**: Reinicia containers para obter novos IPs quando necessário
- **Distribuição inteligente**: Múltiplas instâncias trabalham sem conflitos
- **Rate limit bypass**: Detecção automática e restart quando limites são atingidos
- **Processamento em lote**: Updates eficientes no MongoDB

## Configuração SaladCloud

### Imagem Docker
```
renan2002/instagram-bio-collector:latest
```

### Configurações Básicas
- **Réplicas**: 30 (recomendado)
- **CPU**: 0.5 vCPU por container
- **Memória**: 1GB por container  
- **Restart Policy**: Always (obrigatório)

### Variáveis de Ambiente
```yaml
MONGO_CONNECTION_STRING: "sua_string_de_conexao_mongodb"
MONGO_DB: "nome_do_banco"
MONGO_COLLECTION: "nome_da_colecao"
API_ROUTE: "url_da_sua_api"
SECRET_TOKEN: "seu_token_de_autenticacao"
TOTAL_INSTANCES: "30"  # Número de réplicas
```

## Funcionamento

1. **Container inicia** → SaladCloud atribui IP único
2. **Processa ~120 perfis** → Sistema monitora rate limits
3. **Rate limit detectado** → Container reinicia automaticamente  
4. **Novo container** → SaladCloud atribui novo IP
5. **Ciclo se repete** → Bypass natural de rate limits

## Performance Esperada

- **30 containers** × **120 perfis/ciclo** = **3.600 perfis/ciclo**
- **Perfis por hora**: ~18.000
- **Perfis por dia**: ~432.000

## Desenvolvimento Local

### Instalação
```bash
# Clonar repositório
git clone https://github.com/RenanCampista/Instagram_bio_collector.git
cd Instagram_bio_collector

# Instalar dependências
pip install -r requirements.txt
```

### Teste Local
```bash
docker run \
  -e MONGO_CONNECTION_STRING="sua_string_conexao" \
  -e MONGO_DB="seu_banco" \
  -e MONGO_COLLECTION="sua_colecao" \
  -e API_ROUTE="sua_api" \
  -e SECRET_TOKEN="seu_token" \
  -e TOTAL_INSTANCES="1" \
  renan2002/instagram-bio-collector:latest
```

### Build da Imagem
```bash
docker build -t renan2002/instagram-bio-collector:latest .
docker push renan2002/instagram-bio-collector:latest
```

## Estrutura do Projeto

```
├── main_instaloader_salad.py    # Script principal
├── src/
│   ├── api_db_client.py         # Cliente API
│   ├── salad_utils.py           # Utilitários SaladCloud
│   └── utils.py                 # Utilitários gerais
├── docker-entrypoint.sh         # Script de entrada
├── Dockerfile                   # Configuração Docker
├── requirements.txt             # Dependências Python
└── reset_processing.py          # Utilitário reset status
```

