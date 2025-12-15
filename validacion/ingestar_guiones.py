import pickle
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
import sys
import warnings

# Suprimimos advertencias de SSL si usamos certificados autofirmados
from elasticsearch.exceptions import ElasticsearchWarning
warnings.simplefilter('ignore', ElasticsearchWarning)

# Configuración
PKL_PATH = "/home/g4/streamlit/guiones_vectorizados_768.pkl"

# --- CONEXIÓN ELASTIC (Usuario/Contraseña) ---
es = Elasticsearch(
    ["https://127.0.0.1:9200"],
    
    # CAMBIO AQUÍ: Usamos basic_auth en vez de api_key
    basic_auth=("elastic", "TU_CONTRASEÑA"), 
    
    ca_certs="/home/g4/logstash-9.2.0/config/http_ca.crt",
    verify_certs=False, # Descomenta esto si te da error de certificado SSL
    request_timeout=60
)

print(" Cargando archivo PKL en memoria...")
try:
    with open(PKL_PATH, 'rb') as f:
        datos = pickle.load(f)
except FileNotFoundError:
    print(f" Error: No encuentro el archivo en {PKL_PATH}")
    sys.exit(1)

print(f" Subiendo {len(datos)} fragmentos a Elasticsearch...")

def generar_acciones():
    for d in datos:
        yield {
            "_index": "guiones-chunks",
            "_source": {
                "movie_id": d["movie_id"],
                "title": d["title"],
                "chunk_id": d["chunk_id"],
                "chunk_text": d["chunk_text"],
                "vector": d["vector"].tolist() 
            }
        }

try:
    success, failed = bulk(es, generar_acciones(), chunk_size=500)
    print(f" Subida completada.")
    print(f"   Correctos: {success}")
    print(f"   Fallidos: {failed}")
except Exception as e:
    print(f" Error conectando o subiendo datos: {e}")
