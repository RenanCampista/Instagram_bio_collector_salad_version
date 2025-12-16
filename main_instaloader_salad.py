import logging
import time
import random
import os
import sys

from pymongo.collection import Collection
from dotenv import load_dotenv
from pymongo import UpdateOne

from src.api_db_client import ApiDbClient
from src.instagram_profile_fetcher import InstagramProfileFetcher
from src.utils import (
    connect_to_mongodb, 
    setup_logging, 
    send_pending_updates,
    reset_stuck_processing_profiles
)


log = logging.getLogger(__name__)
log = setup_logging("logs/bio_collector_instaloader", "bio_collector")

MAX_REQUESTS_PER_RESTART = 50  # Número de requisições antes de reiniciar o container
BATCH_UPDATE_SIZE = 3  # Tamanho do lote para atualizações no MongoDB


def load_env_variables() -> dict:
    load_dotenv()
    config = {
        "MONGO_CONNECTION_STRING": os.getenv("MONGO_CONNECTION_STRING"),
        "MONGO_DB": os.getenv("MONGO_DB"),
        "MONGO_COLLECTION": os.getenv("MONGO_COLLECTION"),
        "API_ROUTE": os.getenv("API_ROUTE"),
        "SECRET_TOKEN": os.getenv("SECRET_TOKEN"),
    }
    return config


def get_profiles_from_database(collection: Collection, log: logging.Logger, limit: int = 100) -> list[str]:
    """Obtém perfis da base de dados e marca como 'processing'."""
    try:
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
        
        final_usernames = []
        
        for username, profile_id in zip(usernames, profile_ids):
            result = collection.find_one_and_update({
                    "_id": profile_id, 
                    "status": "not_collected"
                },
                {
                    "$set": {
                        "status": "processing",
                    },
                },
                return_document=True
            )
            
            if result:  # Se conseguiu fazer o update (não foi pego por outra instância)
                final_usernames.append(username)
        
        if final_usernames:
            log.info(f"Reservados {len(final_usernames)} perfis para processamento nesta instância")
        else:
            log.info("Nenhum perfil disponível - todos já sendo processados por outras instâncias")
        
        return final_usernames
        
    except Exception as e:
        log.error(f"Erro ao obter perfis do MongoDB: {e}")
        return []


def handle_rate_limit_restart():
    """Reinicia o container quando atinge rate limits."""
    sys.exit(2) # restart container


def main():
    config = load_env_variables()
    
    api_client = ApiDbClient(config["API_ROUTE"], config["SECRET_TOKEN"], log)
    profile_fetcher = InstagramProfileFetcher(log)
    
    try:
        client = connect_to_mongodb(config["MONGO_CONNECTION_STRING"], log)
        database = client[config["MONGO_DB"]]
        collection = database[config["MONGO_COLLECTION"]]
        
        # Resetar perfis travados em 'processing' (de instâncias que crasharam/reiniciaram)
        reset_stuck_processing_profiles(collection, log)

        request_count = 0
        pending_updates = []
        while True:
            profiles = get_profiles_from_database(
                collection=collection, 
                log=log
            )
            
            if not profiles:
                log.info("Não há mais perfis para processar. Encerrando o script.")
                break
            
            for profile in profiles:                
                time.sleep(random.uniform(2, 5))  # Espera entre requisições
                
                # Verificar se deve reiniciar por número de requisições
                if request_count >= MAX_REQUESTS_PER_RESTART:
                    log.info(f"Processadas {request_count} requisições - reiniciando para novo IP")
                    send_pending_updates(collection, pending_updates, log)
                    handle_rate_limit_restart()
                
                profile_data, status, penalty = profile_fetcher.fetch_profile(profile)
                request_count += penalty # Incrementa contagem de requisições
                
                # Se coleta foi bem-sucedida, enviar para API
                if status == "collected" and profile_data:
                    log.info(f"Dados coletados para o perfil: {profile}. Enviando para a API.")
                    
                    if api_client.send_json(profile_data):
                        log.info(f"Dados enviados com sucesso para o perfil: {profile}.")
                    else:
                        log.error(f"Falha ao enviar dados para o perfil: {profile}")
                        status = "not_collected"
                
                # Atualizar status no MongoDB
                pending_updates.append(
                    UpdateOne(
                        {"username": profile},
                        {
                            "$set": {"status": status},
                            "$currentDate": {"updated_at": True}
                        }
                    )
                )
                
                # Enviar batch se atingir o limite
                if len(pending_updates) >= BATCH_UPDATE_SIZE:
                    send_pending_updates(collection, pending_updates, log)
        if pending_updates:
            send_pending_updates(collection, pending_updates, log)
    except Exception as e:
        log.error(f"Erro crítico: {e}")
        sys.exit(1)
    finally:
        if pending_updates:
            send_pending_updates(collection, pending_updates, log)
        log.info("Script encerrado.")

if __name__ == "__main__":
    main()