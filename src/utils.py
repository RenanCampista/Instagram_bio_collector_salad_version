import logging
from datetime import datetime
import os

from pymongo import MongoClient, errors, UpdateOne
from pymongo.collection import Collection


def setup_logging(log_dir: str, log_name: str) -> logging.Logger:
    """Configures logging with daily log files."""
    # Criar diretório se não existir
    os.makedirs(log_dir, exist_ok=True)
    
    # Gerar nome do arquivo com data atual
    current_date = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(log_dir, f"{log_name}_{current_date}.log")
    
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding='utf-8')
        ],
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    logger = logging.getLogger(__name__)
    logger.info(f"Log iniciado: {log_file}")
    return logger


def send_pending_updates(collection: Collection, pending_updates: list[UpdateOne], log: logging.Logger) -> bool:
    """Envia atualizações pendentes para o MongoDB."""
    try:
        # Enviar atualizações pendentes
        if pending_updates:
            log.info(f"Enviando {len(pending_updates)} atualizações para o MongoDB...")
            result = collection.bulk_write(pending_updates, ordered=False)
            log.info(f"Batch enviado: {result.modified_count} documentos atualizados.")
            pending_updates.clear()
            return True
        return True
    except Exception as batch_error:
        log.error(f"Erro ao enviar batch de atualizações: {batch_error}")
        if pending_updates:
            pending_updates.clear()
        return False


def reset_stuck_processing_profiles(collection: Collection, log: logging.Logger) -> int:
    """
    Reseta perfis que ficaram travados com status 'processing'.
    Deve ser chamado APENAS no início do script, antes de começar a processar.
    """
    try:
        processing_count = collection.count_documents({"status": "processing"})
        
        if processing_count > 0:
            log.info(f"Encontrados {processing_count} perfis travados em 'processing'. Resetando...")
            result = collection.update_many(
                {"status": "processing"},
                {
                    "$set": {"status": "not_collected"},
                    "$currentDate": {"updated_at": True}
                }
            )
            log.info(f"Resetados {result.modified_count} perfis travados.")
            return result.modified_count
        else:
            log.info("Nenhum perfil travado encontrado.")
            return 0
            
    except Exception as e:
        log.error(f"Erro ao resetar perfis travados: {e}")
        return 0


def connect_to_mongodb(connection_string: str, log: logging.Logger) -> MongoClient:
    """Connects to a MongoDB database using a given connection string."""
    try:
        log.info("Conectando ao banco de dados MongoDB...")
        client = MongoClient(
            connection_string, 
            serverSelectionTimeoutMS=20000,
            socketTimeoutMS=60000,
            connectTimeoutMS=20000,
            maxPoolSize=10
        )
        client.admin.command('ping')
        log.info("Conectado ao banco de dados MongoDB.")
        return client
    except errors.ServerSelectionTimeoutError as err:
        log.error(f"Erro ao conectar ao banco de dados MongoDB: {err}")
        raise
    