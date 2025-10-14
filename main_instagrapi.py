import logging
import time
import random
import os
import argparse

from instagrapi import Client
from instagrapi.exceptions import PleaseWaitFewMinutes
from dotenv import load_dotenv
from pymongo import UpdateOne

from src.utils import connect_to_mongodb, get_profiles_from_db, setup_logging, send_pending_updates
from src.api_db_client import ApiDbClient

log = logging.getLogger(__name__)
log = setup_logging("logs/bio_collector_instagrapi", "bio_collector")


def load_env_variables(account_select: str):
    load_dotenv()
    config = {
        "MONGO_CONNECTION_STRING": os.getenv("MONGO_CONNECTION_STRING"),
        "MONGO_DB": os.getenv("MONGO_DB"),
        "MONGO_COLLECTION": os.getenv("MONGO_COLLECTION"),
        "API_ROUTE": os.getenv("API_ROUTE"),
        "SECRET_TOKEN": os.getenv("SECRET_TOKEN"),
        "ACCOUNT": os.getenv(f"ACCOUNT_{account_select}")
    }
    return config


def main():
    """Main function to collect Instagram profile data and send it to an API."""
    parser = argparse.ArgumentParser(description="Coletor de biografias do Instagram")
    parser.add_argument("--account_select", help="Seleção da conta para login")
    config = load_env_variables(parser.parse_args().account_select)

    # Initialize Instagrapi Client
    cl = Client()
    cl.delay_range = [2, 5]  # Random delay between requests
    
    try:
        cl.login_by_sessionid(config["ACCOUNT"])
        log.info("Login realizado com sucesso!")
    except Exception as e:
        log.warning(f"Falha no login: {e}.")
        return
    
    api_client = ApiDbClient(config["API_ROUTE"], config["SECRET_TOKEN"], log)
    
    try:
        client = connect_to_mongodb(config["MONGO_CONNECTION_STRING"], log)
        database = client[config["MONGO_DB"]]
        collection = database[config["MONGO_COLLECTION"]]

        request_count = 0
        # Lista para acumular atualizações em batch
        pending_updates = []
        
        while True:
            profiles = get_profiles_from_db(collection, log)
            
            if not profiles:
                log.info("Não há mais perfis para processar. Encerrando o script.")
                break
            

            for profile in profiles:
                time.sleep(random.uniform(2, 5)) # Sleep aleatório entre 2 e 5 segundos
                
                if request_count >= 120:
                    send_pending_updates(collection, pending_updates, log)
                    request_count = 0
                    
                try:
                    log.info(f"Coletando dados do perfil: {profile}")
                    # Using instagrapi to get user info by username
                    user_id = cl.user_id_from_username(profile.strip())
                    profile_data = cl.user_info(user_id)
                    request_count += 1
                except PleaseWaitFewMinutes as e:
                    log.error(f"Rate limit atingido para o perfil {profile}: {e}")
                    request_count += 50  # Penalidade maior para erros de rate limit
                    pending_updates.append(
                        UpdateOne(
                            {"username": profile},
                            {
                                "$set": {"status": "error"},
                                "$currentDate": {"updated_at": True}
                            }
                        )
                    )
                    continue
                except Exception as e:
                    log.error(f"Erro ao coletar dados do perfil {profile}: {e}")
                    # Adicionar atualização ao batch
                    pending_updates.append(
                        UpdateOne(
                            {"username": profile},
                            {
                                "$set": {"status": "error"},
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
                    "userid": str(profile_data.pk),
                    "biography": profile_data.biography,
                    "external_url": profile_data.external_url,
                    "followers": profile_data.follower_count,
                    "following": profile_data.following_count,
                }
                
                if api_client.send_json(data):
                    log.info(f"Dados enviados com sucesso para o perfil: {profile}.")
                    # Adicionar atualização ao batch
                    pending_updates.append(
                        UpdateOne(
                            {"username": profile},
                            {
                                "$set": {"status": "collected"},
                                "$currentDate": {"updated_at": True}
                            }
                        )
                    )
                else:
                    log.error(f"Falha ao enviar dados para o perfil: {profile}.")
                    # Adicionar atualização ao batch
                    pending_updates.append(
                        UpdateOne(
                            {"username": profile},
                            {
                                "$set": {"status": "error"},
                                "$currentDate": {"updated_at": True}
                            }
                        )
                    ) 
    except Exception as e:
        log.error(f"Erro geral no script: {e}")
    finally:
        log.info("Encerrando script...")
        try:
            send_pending_updates(collection, pending_updates, log)
        except Exception as update_error:
            log.error(f"Erro ao enviar atualizações finais: {update_error}")

        try:
            client.close()
            log.info("Conexão MongoDB fechada.")
        except Exception as db_error:
            log.error(f"Erro ao fechar conexão MongoDB: {db_error}")
            
            
if __name__ == "__main__":
    main()
    