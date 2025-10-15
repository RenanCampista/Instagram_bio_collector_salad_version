import os
import hashlib


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


def should_process_profile(profile_username, instance_id, instance_count):
    """
    Determina se esta instância deve processar o perfil específico.
    Usa hash do username para distribuir uniformemente.
    """
    if instance_count <= 1:
        return True
    
    # Hash do username do perfil
    profile_hash = int(hashlib.md5(profile_username.encode()).hexdigest(), 16)
    
    # Determinar qual instância deve processar este perfil
    assigned_instance = profile_hash % instance_count
    
    return assigned_instance == (instance_id % instance_count)


def log_instance_info(log, instance_id, instance_count, hostname):
    """
    Log das informações da instância para debugging.
    """
    log.info(f"Informações da Instância:")
    log.info(f"   - Hostname: {hostname}")
    log.info(f"   - Instance ID: {instance_id}")
    log.info(f"   - Total de Instâncias: {instance_count}")
    log.info(f"   - Processará ~{100/instance_count:.1f}% dos perfis")


def get_distributed_profiles_query(instance_id, instance_count):
    """
    Cria query MongoDB que distribui perfis entre instâncias.
    """
    if instance_count <= 1:
        return {"status": "pending"}
    
    # Query que usa modulo para distribuir perfis
    # Nota: Isso assume que você tem um campo numérico para distribuição
    # Se não tiver, você pode usar o _id do MongoDB
    
    return {
        "status": "pending",
        "$where": f"this.username.charCodeAt(0) % {instance_count} === {instance_id % instance_count}"
    }


# Configurações específicas do SaladCloud
SALAD_CONFIG = {
    "max_requests_per_restart": 120,  # requisições antes de reiniciar para novo IP
    "sleep_range": (2, 5),            # segundos entre requisições  
    "restart_delay": 5,               # segundos antes de reiniciar
    "batch_size": 50,                 # tamanho do batch para MongoDB
    "health_check_interval": 300,     # 5 minutos
}