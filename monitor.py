#!/usr/bin/env python3
"""
Script de monitoramento para o Instagram Bio Collector no SaladCloud
Conecta ao MongoDB e mostra estatísticas em tempo real
"""

import os
import time
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

def get_collection_stats(collection):
    """Obtém estatísticas da coleção"""
    pipeline = [
        {
            "$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }
        }
    ]
    
    stats = {}
    for result in collection.aggregate(pipeline):
        stats[result["_id"]] = result["count"]
    
    return stats

def get_recent_activity(collection, hours=1):
    """Obtém atividade recente (últimas X horas)"""
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    
    recent_count = collection.count_documents({
        "updated_at": {"$gte": cutoff_time},
        "status": {"$in": ["collected", "error"]}
    })
    
    return recent_count

def get_instance_stats(collection):
    """Obtém estatísticas por instância"""
    pipeline = [
        {
            "$match": {
                "processed_by": {"$exists": True}
            }
        },
        {
            "$group": {
                "_id": {
                    "instance": "$processed_by",
                    "status": "$status"
                },
                "count": {"$sum": 1}
            }
        }
    ]
    
    instance_stats = {}
    for result in collection.aggregate(pipeline):
        instance = result["_id"]["instance"]
        status = result["_id"]["status"]
        
        if instance not in instance_stats:
            instance_stats[instance] = {}
        
        instance_stats[instance][status] = result["count"]
    
    return instance_stats

def print_dashboard(stats, recent_activity, instance_stats):
    """Imprime dashboard no console"""
    os.system('cls' if os.name == 'nt' else 'clear')
    
    print("INSTAGRAM BIO COLLECTOR - SALADCLOUD MONITOR")
    print("=" * 60)
    print(f"Atualizado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Estatísticas gerais
    print("ESTATÍSTICAS GERAIS:")
    total = sum(stats.values())
    print(f"   Total de perfis: {total:,}")
    
    for status, count in stats.items():
        percentage = (count / total * 100) if total > 0 else 0
        symbol = "[OK]" if status == "collected" else "[--]" if status == "pending" else "[ER]"
        print(f"   {symbol} {status.title()}: {count:,} ({percentage:.1f}%)")
    
    print()
    print(f"Atividade (última 1h): {recent_activity:,} perfis processados")
    
    if recent_activity > 0:
        rate_per_hour = recent_activity
        rate_per_minute = rate_per_hour / 60
        estimated_completion = stats.get("pending", 0) / rate_per_hour if rate_per_hour > 0 else float('inf')
        
        print(f"Taxa atual: {rate_per_minute:.1f} perfis/min")
        if estimated_completion != float('inf'):
            print(f"Tempo estimado para conclusão: {estimated_completion:.1f} horas")
    
    # Estatísticas por instância
    if instance_stats:
        print()
        print("ESTATÍSTICAS POR INSTÂNCIA:")
        print("-" * 40)
        
        for instance, inst_stats in instance_stats.items():
            total_inst = sum(inst_stats.values())
            collected_inst = inst_stats.get("collected", 0)
            error_inst = inst_stats.get("error", 0)
            success_rate = (collected_inst / total_inst * 100) if total_inst > 0 else 0
            
            print(f"{instance[:20]}:")
            print(f"   Total: {total_inst:,} | Sucesso: {success_rate:.1f}% | Erros: {error_inst:,}")
    
    print()
    print("Atualizando a cada 30 segundos... (Ctrl+C para sair)")

def main():
    """Função principal do monitor"""
    config = load_env_variables()
    
    if not all(config.values()):
        print("ERRO: Configuração incompleta. Verifique as variáveis de ambiente.")
        return
    
    try:
        client = MongoClient(config["MONGO_CONNECTION_STRING"])
        db = client[config["MONGO_DB"]]
        collection = db[config["MONGO_COLLECTION"]]
        
        print("Conectado ao MongoDB com sucesso!")
        time.sleep(2)
        
        while True:
            try:
                stats = get_collection_stats(collection)
                recent_activity = get_recent_activity(collection, hours=1)
                instance_stats = get_instance_stats(collection)
                
                print_dashboard(stats, recent_activity, instance_stats)
                
                time.sleep(30)  # Atualizar a cada 30 segundos
                
            except KeyboardInterrupt:
                print("\n\nMonitoramento encerrado pelo usuário.")
                break
            except Exception as e:
                print(f"\nErro durante monitoramento: {e}")
                time.sleep(5)
                
    except Exception as e:
        print(f"Erro ao conectar ao MongoDB: {e}")
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    main()