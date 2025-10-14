# Instagram Bio Collector
Coletor de bio de perfis do Instagram.


## Instalação e Configuração
1. **Crie um ambiente virtual para instalar as dependências:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # No Windows use `venv\Scripts\activate`
   ```
2. **Instale as dependências necessárias:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure as variáveis de ambiente:**
   Coloque o arquivo `.env` na raiz do projeto com as seguintes variáveis de ambiente definidas.
   
4. **Configure as credenciais da VPN:**
   Coloque o arquivo `protonvpn_credentials.txt` e/ou `nordvpn_credentials.txt` na raiz do projeto com as credenciais da VPN.

5. **Instale o OpenVPN se ainda não estiver instalado:**
   ```bash
   sudo apt install openvpn
   ```

## Uso
Há duas versões do script principal: a `main_instagrapi.py` que utiliza a biblioteca Instagrapi e requer login em conta do Instagram. Vale lembrar que o uso de contas reais pode levar ao bloqueio das mesmas por parte do Instagram.
A outra versão é a `main_instaloader.py` que utiliza a biblioteca Instaloader e não requer login, mas utiliza vpn para evitar bloqueios.



### Usando o `main_instaloader.py`
1. **Execute o script principal:**
    ```bash
    python main_instaloader.py vpn
    ```

Onde "vpn" pode ser "protonvpn" ou "nordvpn" dependendo de qual VPN você deseja usar.
Exemplo:
```bash
python main_instaloader.py protonvpn
```


### Usando o `main_instagrapi.py`
TODO

