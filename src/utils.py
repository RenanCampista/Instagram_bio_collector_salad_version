import logging
from datetime import datetime
import os
import hashlib

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
        # Verificar e resetar perfis que ficaram com status "processing"
        processing_count = collection.count_documents({"status": "processing"})
        if processing_count > 0:
            reset_result = collection.update_many(
                {"status": "processing"},
                {
                    "$set": {"status": "not_collected"},
                    "$unset": {"processing_by": "", "instance_id": "", "processing_started_at": ""},
                    "$currentDate": {"updated_at": True}
                }
            )
        
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
            pending_updates.clear()  # Limpar para evitar reenvio
        return False


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
    

def get_instance_info():
    """
    Obtém informações da instância atual para distribuição de trabalho.
    """
    # Usar hostname como identificador único da instância
    hostname = os.getenv('HOSTNAME', os.getenv('COMPUTERNAME', 'unknown'))
    
    # Criar ID numérico baseado no hostname
    instance_id = int(hashlib.md5(hostname.encode()).hexdigest(), 16) % 1000
    
    # Número total de instâncias (configurável via ambiente)
    instance_count = int(os.getenv('INSTANCE_COUNT', '1'))
    
    return instance_id, instance_count, hostname


# Configurações específicas do SaladCloud
SALAD_CONFIG = {
    "max_requests_per_restart": 120,  # requisições antes de reiniciar para novo IP
    "sleep_range": (2, 5),            # segundos entre requisições  
    "restart_delay": 5,               # segundos antes de reiniciar
    "batch_size": 50,                 # tamanho do batch para MongoDB
    "health_check_interval": 300,     # 5 minutos
}