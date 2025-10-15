import logging
import time
import random
import os
import sys
import signal

from instaloader import Instaloader, Profile
from dotenv import load_dotenv
from pymongo import UpdateOne

from src.utils import connect_to_mongodb, setup_logging, send_pending_updates
from src.api_db_client import ApiDbClient
from src.salad_utils import (
    get_instance_info, 
    log_instance_info,
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


def get_profiles_from_db_distributed(collection, instance_id, instance_count, hostname, log, limit=100):
    """
    Obtém perfis do MongoDB com distribuição entre instâncias e marca como 'processing'.
    """
    try:
        # Query básica para perfis não coletados
        base_query = {"status": "not_collected"}
        
        # Se múltiplas instâncias, usar distribuição
        if instance_count > 1:
            # Usar skip baseado no instance_id para distribuir
            skip_amount = (instance_id % instance_count) * limit
            profiles_cursor = collection.find(base_query).skip(skip_amount).limit(limit)
        else:
            profiles_cursor = collection.find(base_query).limit(limit)
        
        # Converter cursor para lista
        profiles_docs = list(profiles_cursor)
        
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
        
        # Atualizar status para 'processing' em lote usando findAndModify atômico
        # Isso garante que apenas uma instância pegue cada perfil
        final_usernames = []
        
        for username, profile_id in zip(usernames, profile_ids):
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
    """
    Reinicia o container quando atinge rate limits.
    Isso força o SaladCloud a criar nova instância com novo IP.
    """
    log.info("Rate limit atingido - reiniciando container para novo IP")
    log.info("SaladCloud criará nova instância automaticamente")
    
    # Exit code 2 = restart container
    sys.exit(2)


def check_rate_limit_in_error(error_message):
    """
    Verifica se o erro é relacionado a rate limit.
    """
    rate_limit_indicators = [
        "Please wait a few minutes before you try again",
        "429",
        "Too Many Requests", 
        "rate limit",
        "Temporary failure in name resolution"
    ]
    
    return any(indicator in str(error_message) for indicator in rate_limit_indicators)


def main():
    """Main function to collect Instagram profile data without VPN."""
    config = load_env_variables()
    
    # Obter informações da instância para distribuição de trabalho
    instance_id, instance_count, hostname = get_instance_info()
    
    # Log informações da instância
    log_instance_info(log, instance_id, instance_count, hostname)
    
    # Mostrar IP atual (sem VPN)
    try:
        import requests
        current_ip = requests.get("https://api.ipify.org", timeout=5).text
        log.info(f"IP atual da instância: {current_ip}")
    except:
        log.info("IP atual: Não foi possível determinar")

    L = Instaloader()
    L.context.sleep = True # Enable built-in sleep to handle rate limits
    
    api_client = ApiDbClient(config["API_ROUTE"], config["SECRET_TOKEN"], log)
    
    try:
        client = connect_to_mongodb(config["MONGO_CONNECTION_STRING"], log)
        database = client[config["MONGO_DB"]]
        collection = database[config["MONGO_COLLECTION"]]

        request_count = 0
        
        # Lista para acumular atualizações em batch
        pending_updates = []
        
        # Contador para estatísticas
        profiles_processed = 0
        profiles_success = 0
        
        # Contador de erros de rate limit consecutivos
        consecutive_rate_limit_errors = 0
        
        while True:
            # Usar função distribuída para obter perfis
            profiles = get_profiles_from_db_distributed(
                collection, instance_id, instance_count, hostname, log
            )
            
            if not profiles:
                log.info("Não há mais perfis para processar. Encerrando o script.")
                break
            
            for profile in profiles:                
                profiles_processed += 1
                
                # Sleep aleatório entre requisições
                sleep_time = random.uniform(*SALAD_CONFIG["sleep_range"])
                time.sleep(sleep_time)
                
                # Verificar se deve reiniciar por número de requisições
                if request_count >= SALAD_CONFIG["max_requests_per_restart"]:
                    log.info(f"🔄 Processadas {request_count} requisições - reiniciando para novo IP")
                    send_pending_updates(collection, pending_updates, log)
                    handle_rate_limit_restart()
                    
                try:
                    log.info(f"Coletando dados do perfil: {profile} (Instância {instance_id})")
                    profile_data = Profile.from_username(L.context, profile.strip())
                    request_count += 1
                    consecutive_rate_limit_errors = 0  # Reset contador de erros
                except Exception as e:
                    log.error(f"Erro ao coletar dados do perfil {profile}: {e}")
                    
                    # Verificar se é erro de rate limit
                    if check_rate_limit_in_error(str(e)):
                        consecutive_rate_limit_errors += 1
                        log.warning(f"Rate limit detectado (erro #{consecutive_rate_limit_errors})")
                        
                        # Após 3 erros consecutivos de rate limit, reiniciar
                        if consecutive_rate_limit_errors >= 3:
                            log.info("Múltiplos rate limits detectados - reiniciando container")
                            send_pending_updates(collection, pending_updates, log)
                            handle_rate_limit_restart()
                        
                        request_count += 10  # Penalidade para rate limit
                    
                    # Adicionar atualização ao batch
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
                    "biography": profile_data.biography,
                    "external_url": profile_data.external_url,
                    "followers": profile_data.followers,
                    "followees": profile_data.followees,
                    "mediacount": profile_data.mediacount,
                    "is_verified": profile_data.is_verified,
                    "is_private": profile_data.is_private,
                    "is_business_account": profile_data.is_business_account,
                    "profile_pic_url": profile_data.profile_pic_url
                }

                # Enviar dados para API
                success = api_client.send_json(data)
                
                if success:
                    profiles_success += 1
                    log.info(f"Dados enviados com sucesso para o perfil: {profile}.")
                    
                    # Adicionar atualização ao batch
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
                                "$set": {"status": "error", "processed_by": hostname},
                                "$currentDate": {"updated_at": True}
                            }
                        )
                    )

                # Enviar updates em lotes de 10
                if len(pending_updates) >= 10:
                    send_pending_updates(collection, pending_updates, log)

        # Enviar updates finais
        if pending_updates:
            send_pending_updates(collection, pending_updates, log)

    except KeyboardInterrupt:
        log.info("Encerrando script...")
    except Exception as e:
        log.error(f"Erro crítico: {e}")
        sys.exit(1)
    finally:
        # Estatísticas finais
        log.info(f"Estatísticas Finais (Instância {instance_id}):")
        log.info(f"   - Perfis Processados: {profiles_processed}")
        log.info(f"   - Sucessos: {profiles_success}")
        if profiles_processed > 0:
            success_rate = (profiles_success / profiles_processed) * 100
            log.info(f"   - Taxa de Sucesso: {success_rate:.1f}%")
        
        # Enviar updates finais se houver
        if pending_updates:
            send_pending_updates(collection, pending_updates, log)
            
        log.info("Conexão MongoDB fechada.")


if __name__ == "__main__":
    main()