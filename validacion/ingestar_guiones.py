import pickle
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
import sys

# Configuración
PKL_PATH = "/home/g4/streamlit/guiones_vectorizados_768.pkl"

# Conexión Elastic
# Conexión Elastic
es = Elasticsearch(
    ["https://192.199.1.38:9200", "https://192.199.1.40:9200", "https://192.199.1.54:9200"],
    api_key=("gWMV35oBc7daF0WmrpBl", "KQuuWHwe-FNUEuSo6ybl7A"), 
    ca_certs="/home/g4/logstash-9.2.0/config/http_ca.crt",
    request_timeout=60  # <--- ESTE ERA EL ERROR. Cambia 'timeout' por 'request_timeout'
)

print("⏳ Cargando archivo PKL en memoria (esto puede tardar unos segundos)...")
with open(PKL_PATH, 'rb') as f:
    datos = pickle.load(f)

print(f"🚀 Subiendo {len(datos)} fragmentos a Elasticsearch...")

# Preparamos el generador para Bulk
def generar_acciones():
    for d in datos:
        yield {
            "_index": "guiones-chunks",
            "_source": {
                "movie_id": d["movie_id"],
                "title": d["title"],
                "chunk_id": d["chunk_id"],
                "chunk_text": d["chunk_text"],
                "vector": d["vector"].tolist() # Convertir numpy a lista normal para Elastic
            }
        }

# Subida masiva
success, failed = bulk(es, generar_acciones(), chunk_size=500)

print(f"✅ Subida completada.")
print(f"   Correctos: {success}")
print(f"   Fallidos: {failed}")