#!/usr/bin/env python3
"""
Script utilitário para resetar perfis travados em 'processing'
Use este script se algumas instâncias falharem e deixarem perfis em estado 'processing'
"""

import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pymongo import MongoClient

def load_env_variables():
    load_dotenv()
    return {
        "MONGO_CONNECTION_STRING": os.getenv("MONGO_CONNECTION_STRING"),
        "MONGO_DB": os.getenv("MONGO_DB"),
        "MONGO_COLLECTION": os.getenv("MONGO_COLLECTION"),
    }

def reset_stuck_processing_profiles(minutes_stuck=30):
    """
    Reseta perfis que estão em 'processing' há mais de X minutos para 'not_collected'
    """
    config = load_env_variables()
    
    if not all(config.values()):
        print("ERRO: Configuração incompleta. Verifique as variáveis de ambiente.")
        return
    
    try:
        client = MongoClient(config["MONGO_CONNECTION_STRING"])
        db = client[config["MONGO_DB"]]
        collection = db[config["MONGO_COLLECTION"]]
        
        # Calcular tempo limite
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes_stuck)
        
        # Encontrar perfis travados em processing
        query = {
            "status": "processing",
            "processing_started_at": {"$lt": cutoff_time}
        }
        
        stuck_count = collection.count_documents(query)
        
        if stuck_count == 0:
            print(f"Nenhum perfil encontrado travado em 'processing' há mais de {minutes_stuck} minutos.")
            return
        
        print(f"Encontrados {stuck_count} perfis travados em 'processing' há mais de {minutes_stuck} minutos.")
        
        # Confirmar com usuário
        response = input("Deseja resetar estes perfis para 'not_collected'? (y/n): ")
        
        if response.lower() in ['y', 'yes', 's', 'sim']:
            # Resetar perfis
            result = collection.update_many(
                query,
                {
                    "$set": {"status": "not_collected"},
                    "$unset": {
                        "processing_by": "",
                        "instance_id": "",
                        "processing_started_at": ""
                    },
                    "$currentDate": {"reset_at": True}
                }
            )
            
            print(f"✅ {result.modified_count} perfis foram resetados de 'processing' para 'not_collected'.")
        else:
            print("Operação cancelada.")
            
    except Exception as e:
        print(f"Erro ao resetar perfis: {e}")
    finally:
        if 'client' in locals():
            client.close()

def show_processing_stats():
    """Mostra estatísticas dos perfis em processing"""
    config = load_env_variables()
    
    if not all(config.values()):
        print("ERRO: Configuração incompleta. Verifique as variáveis de ambiente.")
        return
    
    try:
        client = MongoClient(config["MONGO_CONNECTION_STRING"])
        db = client[config["MONGO_DB"]]
        collection = db[config["MONGO_COLLECTION"]]
        
        # Estatísticas por instância
        pipeline = [
            {
                "$match": {"status": "processing"}
            },
            {
                "$group": {
                    "_id": {
                        "processing_by": "$processing_by",
                        "instance_id": "$instance_id"
                    },
                    "count": {"$sum": 1},
                    "oldest": {"$min": "$processing_started_at"},
                    "newest": {"$max": "$processing_started_at"}
                }
            }
        ]
        
        results = list(collection.aggregate(pipeline))
        
        if not results:
            print("Nenhum perfil em 'processing' encontrado.")
            return
        
        print("\n📊 PERFIS EM PROCESSING:")
        print("=" * 60)
        
        total_processing = 0
        for result in results:
            instance_info = result["_id"]
            count = result["count"]
            oldest = result["oldest"]
            newest = result["newest"]
            
            total_processing += count
            
            hostname = instance_info.get("processing_by", "Unknown")
            instance_id = instance_info.get("instance_id", "Unknown")
            
            # Calcular há quanto tempo o mais antigo está processando
            if oldest:
                time_diff = datetime.utcnow() - oldest
                minutes_ago = int(time_diff.total_seconds() / 60)
            else:
                minutes_ago = 0
            
            print(f"Instância: {hostname[:30]}")
            print(f"  ID: {instance_id}")
            print(f"  Processando: {count} perfis")
            print(f"  Mais antigo: {minutes_ago} minutos atrás")
            print()
        
        print(f"Total em processing: {total_processing}")
        
    except Exception as e:
        print(f"Erro ao obter estatísticas: {e}")
    finally:
        if 'client' in locals():
            client.close()

def main():
    """Menu principal"""
    while True:
        print("\n🔧 UTILITÁRIO DE RESET DE PERFIS")
        print("=" * 40)
        print("1. Mostrar estatísticas de perfis em 'processing'")
        print("2. Resetar perfis travados (30+ minutos)")
        print("3. Resetar perfis travados (tempo customizado)")
        print("4. Sair")
        
        choice = input("\nEscolha uma opção (1-4): ").strip()
        
        if choice == "1":
            show_processing_stats()
        elif choice == "2":
            reset_stuck_processing_profiles(30)
        elif choice == "3":
            try:
                minutes = int(input("Quantos minutos em 'processing' considerar como travado? "))
                reset_stuck_processing_profiles(minutes)
            except ValueError:
                print("Por favor, digite um número válido.")
        elif choice == "4":
            print("Saindo...")
            break
        else:
            print("Opção inválida. Tente novamente.")

if __name__ == "__main__":
    main()