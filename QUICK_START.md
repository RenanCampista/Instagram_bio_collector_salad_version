# GUIA RÁPIDO - Instagram Bio Collector no SaladCloud

## Checklist de Configuração

### Pré-requisitos
- [ ] Docker instalado e rodando
- [ ] Conta no Docker Hub ou registry similar
- [ ] Conta no SaladCloud com créditos
- [ ] Variáveis de ambiente configuradas

### Passo 1: Preparar a Imagem Docker

1. **Edite o arquivo `build-and-deploy.bat` (Windows) ou `build-and-deploy.sh` (Linux/Mac)**:
   ```bash
   # Mude esta linha:
   set DOCKER_USERNAME=seu-usuario-do-dockerhub
   ```

2. **Execute o script de build**:
   ```cmd
   # Windows
   build-and-deploy.bat
   
   # Linux/Mac
   chmod +x build-and-deploy.sh
   ./build-and-deploy.sh
   ```

3. **Confirme o upload** quando solicitado (digite 'y')

### Passo 2: Configurar no SaladCloud Portal

1. **Acesse**: https://portal.salad.com/
2. **Vá para**: Container Groups → Create Container Group
3. **Configure**:

   **Básico:**
   - Name: `instagram-bio-collector`
   - Image: `seu-usuario/instagram-bio-collector:latest`
   - Command: `python3 main_instaloader_salad.py nordvpn`

   **Recursos:**
   - vCPUs: `1-2`
   - Memory: `1-2 GB`
   - Storage: `2 GB`

   **Scaling:**
   - Replicas: `30` (ou quantas quiser)

   **Environment Variables:**
   ```
   MONGO_CONNECTION_STRING=mongodb://...
   MONGO_DB=seu_banco
   MONGO_COLLECTION=sua_colecao
   API_ROUTE=https://sua-api.com/endpoint
   SECRET_TOKEN=seu_token
   VPN_SERVICE=nordvpn
   INSTANCE_COUNT=30
   ```

   **Configurações Avançadas:**
   - Privileged: `✅ Enabled`
   - Capabilities: Adicione `NET_ADMIN` e `SYS_MODULE`

### Passo 3: Deploy e Monitoramento

1. **Clique em "Deploy"** no SaladCloud
2. **Monitore os logs** através da interface web
3. **Use o script de monitoramento** localmente:
   ```bash
   python monitor.py
   ```

### Passo 4: Verificar se está Funcionando

**Indicadores de Sucesso:**
- Containers iniciando sem erros
- Conexões VPN estabelecidas
- Dados sendo coletados e enviados para API
- Status no MongoDB mudando para "collected"

**Logs importantes para verificar:**
```
Informações da Instância: Hostname: xxx, Instance ID: xxx
Usando serviço VPN: nordvpn
Coletando dados do perfil: username
Dados enviados com sucesso para o perfil: username
```

### Troubleshooting Rápido

**Container não inicia:**
- Verificar variáveis de ambiente
- Verificar se imagem foi construída corretamente

**VPN não conecta:**
- Verificar se `privileged: true` está habilitado
- Verificar arquivos de credenciais

**Rate limiting:**
- Reduzir número de réplicas temporariamente
- Aumentar delay entre requisições

**Instâncias processando os mesmos perfis:**
- Verificar se `INSTANCE_COUNT` está correto
- Implementar locks no MongoDB se necessário

### Estimativa de Performance

**Com 30 instâncias:**
- ~150-300 perfis/hora por instância
- Total: ~4.500-9.000 perfis/hora
- 1 milhão de perfis: ~111-222 horas (4-9 dias)

### Suporte

Para problemas específicos:
1. Verificar logs no SaladCloud Portal
2. Executar `python monitor.py` para estatísticas
3. Verificar README.md para documentação completa

---

**Arquivos Importantes:**
- `Dockerfile`: Configuração do container
- `main_instaloader_salad.py`: Versão otimizada para múltiplas instâncias
- `docker-entrypoint.sh`: Script de inicialização
- `monitor.py`: Monitoramento em tempo real
- `SALAD_SETUP.md`: Documentação completa