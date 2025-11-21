import logging
import time
import random
import os
import sys
import requests
import io
import contextlib

from instaloader import Instaloader, Profile
from dotenv import load_dotenv
from pymongo import UpdateOne

from src.api_db_client import ApiDbClient
from src.utils import (
    connect_to_mongodb, 
    setup_logging, 
    send_pending_updates,
    reset_stuck_processing_profiles,
    get_instance_info, 
    SALAD_CONFIG
)


log = logging.getLogger(__name__)
log = setup_logging("logs/bio_collector_instaloader", "bio_collector")


def load_env_variables():
    load_dotenv()
    config = {
        "MONGO_CONNECTION_STRING": os.getenv("MONGO_CONNECTION_STRING"),
        "MONGO_DB": os.getenv("MONGO_DB"),
        "MONGO_COLLECTION": os.getenv("MONGO_COLLECTION"),
        "API_ROUTE": os.getenv("API_ROUTE"),
        "SECRET_TOKEN": os.getenv("SECRET_TOKEN"),
    }
    return config


def get_profiles_from_db_distributed(collection, instance_id, hostname, log, limit=100):
    """Obtém perfis do MongoDB com distribuição entre instâncias e marca como 'processing'."""
    try:
        # Query básica para perfis não coletados
        base_query = {"status": "not_collected"}
        
        # Usar agregação com $sample para seleção aleatória
        pipeline = [
            {"$match": base_query},
            {"$sample": {"size": limit}}
        ]
        
        profiles_docs = list(collection.aggregate(pipeline))
        
        if not profiles_docs:
            log.info("Nenhum perfil não coletado encontrado para esta instância")
            return []
        
        # Extrair usernames e _ids para o update
        usernames = []
        profile_ids = []
        
        for doc in profiles_docs:
            if "username" in doc:
                usernames.append(doc["username"])
                profile_ids.append(doc["_id"])
        
        # Atualizar status para 'processing' 
        final_usernames = []
        
        for username, profile_id in zip(usernames, profile_ids):
            # Para fins de rastreamento, adicionar informações de qual instância está processando
            result = collection.find_one_and_update(
                {"_id": profile_id, "status": "not_collected"},  # Só atualiza se ainda for 'not_collected'
                {
                    "$set": {
                        "status": "processing",
                        "processing_by": hostname,
                        "instance_id": instance_id
                    },
                    "$currentDate": {"processing_started_at": True}
                },
                return_document=True
            )
            
            if result:  # Se conseguiu fazer o update (não foi pego por outra instância)
                final_usernames.append(username)
        
        if final_usernames:
            log.info(f"Reservados {len(final_usernames)} perfis para processamento (Instância {instance_id})")
        else:
            log.info("Nenhum perfil disponível - todos já sendo processados por outras instâncias")
        
        return final_usernames
        
    except Exception as e:
        log.error(f"Erro ao obter perfis do MongoDB: {e}")
        return []


def handle_rate_limit_restart():
    """Reinicia o container quando atinge rate limits."""
    log.info("Rate limit atingido - reiniciando container para novo IP")
    sys.exit(2) # restart container


def check_rate_limit_in_output(error_message, captured_output=""):
    """Verifica se o erro ou saída capturada contém indicadores de rate limit."""
    rate_limit_indicators = [
        "Please wait a few minutes before you try again",
        "429",
        "Too Many Requests", 
        "rate limit",
        "Temporary failure in name resolution",
        "Max retries exceeded",
        "please wait",
        "checkpoint",
        "badrequest",
        "login required",
        "401"
    ]
    
    # Combina mensagem de erro com saída capturada
    full_text = str(error_message).lower() + " " + captured_output.lower()
    
    return any(indicator.lower() in full_text for indicator in rate_limit_indicators)


def main():
    """Main function to collect Instagram profile data without VPN."""
    config = load_env_variables()
    
    instance_id, instance_count, hostname = get_instance_info()
    
    try:
        current_ip = requests.get("https://api.ipify.org", timeout=5).text
        log.info(f"IP atual da instância: {current_ip}")
    except:
        log.info("IP atual: Não foi possível determinar")

    L = Instaloader()
    L.context.sleep = True
    
    api_client = ApiDbClient(config["API_ROUTE"], config["SECRET_TOKEN"], log)
    
    try:
        client = connect_to_mongodb(config["MONGO_CONNECTION_STRING"], log)
        database = client[config["MONGO_DB"]]
        collection = database[config["MONGO_COLLECTION"]]
        
        # Resetar perfis travados em 'processing' (de instâncias que crasharam/reiniciaram)
        reset_stuck_processing_profiles(collection, log)

        request_count = 0
        pending_updates = []
        while True:
            profiles = get_profiles_from_db_distributed(
                collection, instance_id, hostname, log
            )
            
            if not profiles:
                log.info("Não há mais perfis para processar. Encerrando o script.")
                break
            
            for profile in profiles:                
                
                sleep_time = random.uniform(*SALAD_CONFIG["sleep_range"])
                time.sleep(sleep_time)
                
                # Verificar se deve reiniciar por número de requisições
                if request_count >= SALAD_CONFIG["max_requests_per_restart"]:
                    log.info(f"Processadas {request_count} requisições - reiniciando para novo IP")
                    send_pending_updates(collection, pending_updates, log)
                    handle_rate_limit_restart()
                    
                try:
                    log.info(f"Coletando dados do perfil: {profile} (Instância {instance_id})")
                    
                    # Capturar stderr para detectar mensagens do Instaloader
                    stderr_capture = io.StringIO()
                    with contextlib.redirect_stderr(stderr_capture):
                        profile_data = Profile.from_username(L.context, profile.strip())
                    
                    # Obter saída capturada
                    captured_output = stderr_capture.getvalue()
                    
                    # Verificar se há indicadores de rate limit na saída, mesmo sem exceção
                    if check_rate_limit_in_output("", captured_output):
                        log.warning(f"Rate limit detectado na saída do Instaloader para {profile}")
                        log.debug(f"Saída capturada: {captured_output}")
                        request_count += 10
                        
                        pending_updates.append(
                            UpdateOne(
                                {"username": profile},
                                {
                                    "$set": {"status": "not_collected", "processed_by": hostname},
                                    "$currentDate": {"updated_at": True}
                                }
                            )
                        )
                        continue
                    
                    request_count += 1
                    
                except Exception as e:
                    # Capturar stderr também em caso de exceção
                    stderr_capture = io.StringIO()
                    captured_output = stderr_capture.getvalue()
                    
                    # Verificar se é erro de rate limit
                    if check_rate_limit_in_output(str(e), captured_output):
                        log.warning(f"Rate limit detectado ao coletar {profile}.")
                        log.debug(f"Erro: {e}")
                        if captured_output:
                            log.debug(f"Saída capturada: {captured_output}")
                        request_count += 15  # Penalidade maior força reinício mais rápido
                    
                        pending_updates.append(
                            UpdateOne(
                                {"username": profile},
                                {
                                    "$set": {"status": "not_collected", "processed_by": hostname},
                                    "$currentDate": {"updated_at": True}
                                }
                            )
                        )
                    else:
                        log.error(f"Erro ao coletar dados do perfil {profile}: {e}")
                        if captured_output:
                            log.debug(f"Saída capturada: {captured_output}")
                        request_count += 10 # Penalidade menor para outros erros
                        pending_updates.append(
                            UpdateOne(
                                {"username": profile},
                                {
                                    "$set": {"status": "error", "processed_by": hostname},
                                    "$currentDate": {"updated_at": True}
                                }
                            )
                        )
                    continue
                
                log.info(f"Dados coletados para o perfil: {profile}. Enviando para a API.")
                
                data = {
                    "username": profile_data.username,
                    "full_name": profile_data.full_name,
                    "profile_url": f"https://www.instagram.com/{profile_data.username}/",
                    "userid": profile_data.userid,
                    "biography": profile_data.biography,
                    "external_url": profile_data.external_url,
                    "followers": profile_data.followers,
                    "following": profile_data.followees,
                }

                if api_client.send_json(data):
                    log.info(f"Dados enviados com sucesso para o perfil: {profile}.")
                    
                    pending_updates.append(
                        UpdateOne(
                            {"username": profile},
                            {
                                "$set": {"status": "collected", "processed_by": hostname},
                                "$currentDate": {"updated_at": True}
                            }
                        )
                    )
                else:
                    log.error(f"Falha ao enviar dados para o perfil: {profile}")
                    pending_updates.append(
                        UpdateOne(
                            {"username": profile},
                            {
                                "$set": {"status": "not_collected", "processed_by": hostname},
                                "$currentDate": {"updated_at": True}
                            }
                        )
                    )

                if len(pending_updates) >= 10:
                    send_pending_updates(collection, pending_updates, log)
        if pending_updates:
            send_pending_updates(collection, pending_updates, log)
    except KeyboardInterrupt:
        log.info("Encerrando script...")
    except Exception as e:
        log.error(f"Erro crítico: {e}")
        sys.exit(1)
    finally:
        if pending_updates:
            send_pending_updates(collection, pending_updates, log)
        log.info("Script encerrado.")

if __name__ == "__main__":
    main()