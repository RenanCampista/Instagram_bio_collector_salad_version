import logging
import time
import random
import os
import argparse

from instaloader import Instaloader, Profile
from dotenv import load_dotenv
from pymongo import UpdateOne

from src.utils import connect_to_mongodb, get_profiles_from_db, setup_logging, send_pending_updates
from src.api_db_client import ApiDbClient
from src.vpn_handler import VpnHandler
from src.salad_utils import (
    get_instance_info, 
    should_process_profile, 
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


def get_profiles_from_db_distributed(collection, instance_id, instance_count, log, limit=100):
    """
    Obtém perfis do MongoDB com distribuição entre instâncias.
    """
    try:
        # Query básica para perfis pendentes
        base_query = {"status": "pending"}
        
        # Se múltiplas instâncias, usar distribuição
        if instance_count > 1:
            # Usar skip baseado no instance_id para distribuir
            skip_amount = (instance_id % instance_count) * limit
            profiles_cursor = collection.find(base_query).skip(skip_amount).limit(limit)
        else:
            profiles_cursor = collection.find(base_query).limit(limit)
        
        profiles = [profile["username"] for profile in profiles_cursor]
        
        if profiles:
            log.info(f"Obtidos {len(profiles)} perfis para processar (Instância {instance_id})")
        else:
            log.info("Nenhum perfil pendente encontrado para esta instância")
        
        return profiles
        
    except Exception as e:
        log.error(f"Erro ao obter perfis do MongoDB: {e}")
        return []


def main():
    """Main function to collect Instagram profile data and send it to an API."""
    config = load_env_variables()
    
    # Obter informações da instância para distribuição de trabalho
    instance_id, instance_count, hostname = get_instance_info()
    
    parser = argparse.ArgumentParser(description="Instagram Bio Collector with VPN")
    parser.add_argument("vpn_service", choices=["protonvpn", "nordvpn"], help="VPN service to use")
    args = parser.parse_args()

    vpn_dir = f"vpn_files/{args.vpn_service}"
    credentials_file = f"{args.vpn_service}_credentials.txt"
    
    # Log informações da instância
    log_instance_info(log, instance_id, instance_count, hostname)
    
    L = Instaloader()
    L.context.sleep = True # Enable built-in sleep to handle rate limits
    
    api_client = ApiDbClient(config["API_ROUTE"], config["SECRET_TOKEN"], log)
    
    try:
        client = connect_to_mongodb(config["MONGO_CONNECTION_STRING"], log)
        database = client[config["MONGO_DB"]]
        collection = database[config["MONGO_COLLECTION"]]

        vpn = VpnHandler(vpn_dir, credentials_file, log)
        vpn.load_server_list()
        request_count = 0
        vpn_connected = False
        
        # Lista para acumular atualizações em batch
        pending_updates = []
        
        # Contador para estatísticas
        profiles_processed = 0
        profiles_success = 0
        
        while True:
            # Usar função distribuída para obter perfis
            profiles = get_profiles_from_db_distributed(
                collection, instance_id, instance_count, log
            )
            
            if not profiles:
                log.info("Não há mais perfis para processar. Encerrando o script.")
                break
            
            # Conectar VPN apenas antes de começar a coletar perfis do Instagram
            if not vpn_connected:
                vpn.connect_to_next_server()
                vpn_connected = True
            
            for profile in profiles:
                # Verificar se esta instância deve processar este perfil
                if not should_process_profile(profile, instance_id, instance_count):
                    continue
                
                profiles_processed += 1
                
                # Sleep aleatório entre requisições
                sleep_time = random.uniform(*SALAD_CONFIG["sleep_range"])
                time.sleep(sleep_time)
                
                if request_count >= SALAD_CONFIG["max_requests_per_vpn_change"]:
                    log.info(f"Atingidas {request_count} requisições. Trocando servidor VPN...")
                    vpn.disconnect()
                    vpn_connected = False
                    
                    log.info(f"Aguardando {SALAD_CONFIG['vpn_change_delay']} segundos antes de reconectar...")
                    time.sleep(SALAD_CONFIG["vpn_change_delay"])
                    
                    send_pending_updates(collection, pending_updates, log)

                    vpn.connect_to_next_server()
                    vpn_connected = True
                    request_count = 0
                    
                try:
                    log.info(f"Coletando dados do perfil: {profile} (Instância {instance_id})")
                    profile_data = Profile.from_username(L.context, profile.strip())
                    request_count += 1
                except Exception as e:
                    log.error(f"Erro ao coletar dados do perfil {profile}: {e}")
                    # Adicionar atualização ao batch
                    if "Please wait a few minutes before you try again." in str(e):
                        request_count += 50  # Penalidade maior para erros de rate limit
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
                    "processed_by": hostname,  # Adicionar info da instância
                    "instance_id": instance_id
                }
                
                if api_client.send_json(data):
                    log.info(f"Dados enviados com sucesso para o perfil: {profile}.")
                    profiles_success += 1
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
                    log.error(f"Falha ao enviar dados para o perfil: {profile}.")
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
                
                # Enviar batch se atingir o limite
                if len(pending_updates) >= SALAD_CONFIG["batch_size"]:
                    send_pending_updates(collection, pending_updates, log)
                
                # Log de progresso a cada 10 perfis
                if profiles_processed % 10 == 0:
                    success_rate = (profiles_success / profiles_processed) * 100 if profiles_processed > 0 else 0
                    log.info(f"Progresso: {profiles_processed} processados, {profiles_success} sucessos ({success_rate:.1f}%)")
                    
    except Exception as e:
        log.error(f"Erro geral no script: {e}")
    finally:
        log.info("Encerrando script...")
        
        # Estatísticas finais
        if profiles_processed > 0:
            success_rate = (profiles_success / profiles_processed) * 100
            log.info(f"Estatísticas Finais (Instância {instance_id}):")
            log.info(f"   - Perfis Processados: {profiles_processed}")
            log.info(f"   - Sucessos: {profiles_success}")
            log.info(f"   - Taxa de Sucesso: {success_rate:.1f}%")
        
        try:
            if vpn_connected:
                vpn.disconnect()
                log.info("VPN desconectada.")
        except Exception as vpn_error:
            log.error(f"Erro ao desconectar VPN: {vpn_error}")
        
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