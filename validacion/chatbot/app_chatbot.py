import streamlit as st
import json
import requests
import os
import re
from openai import OpenAI
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer

# ==========================================
#   1. CONFIGURACIÓN
# ==========================================
load_dotenv()
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

st.set_page_config(page_title="CineBot IA", page_icon="🤖", layout="centered")

if not TMDB_API_KEY or not OPENROUTER_API_KEY:
    st.error("❌ Faltan claves API en el archivo .env")
    st.stop()

# ==========================================
#   2. CONEXIONES
# ==========================================

# A. Cliente LLM
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
CHAT_MODEL = "meta-llama/llama-3.3-70b-instruct:"

# B. Cliente Elastic (Conexión a los 3 nodos)
try:
    es = Elasticsearch(
        ["https://192.199.1.38:9200", "https://192.199.1.40:9200", "https://192.199.1.54:9200"],
        api_key=("4Etb6JoBHk-0Ge2TdtLz", "Ag2-mARBGEkGIpcHhBDoOQ"), 
        ca_certs="/home/g4/logstash-9.2.0/config/http_ca.crt",
        request_timeout=30
    )
except Exception as e:
    st.error(f"Error conectando a Elastic: {e}")

# C. Modelo de Embeddings (ACTUALIZADO A 768 DIMS)
@st.cache_resource
def load_embedding_model():
    # Este modelo genera vectores de 768 dimensiones, coincidiendo con tu índice nuevo
    return SentenceTransformer('sentence-transformers/paraphrase-multilingual-mpnet-base-v2')

try: embedding_model = load_embedding_model()
except: pass

# ==========================================
#   3. HERRAMIENTAS (TOOLS)
# ==========================================

GENRES_MAP = {
    "Action": 28, "Adventure": 12, "Animation": 16, "Comedy": 35, "Crime": 80,
    "Documentary": 99, "Drama": 18, "Horror": 27, "Sci-Fi": 878, "Romance": 10749
}

def api_search_movie(titulo):
    """Busca título exacto en TMDb."""
    url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={titulo}&language=es-ES"
    try:
        data = requests.get(url).json().get("results", [])[:1]
        if data:
            return f"TÍTULO: {data[0]['title']} | SINOPSIS: {data[0]['overview']} | FECHA: {data[0].get('release_date', 'N/A')}"
        return "No encontrada."
    except Exception as e: return f"Error API: {e}"

def api_discover_movies(genre_id=None, year=None):
    """Filtra en TMDb."""
    url = f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&language=es-ES&sort_by=popularity.desc"
    if genre_id: url += f"&with_genres={genre_id}"
    if year: url += f"&primary_release_year={year}"
    try:
        data = requests.get(url).json().get("results", [])[:5]
        return [f"- {m['title']} ({m.get('release_date','')[:4]}): {m['overview'][:100]}..." for m in data]
    except Exception as e: return f"Error API Discover: {e}"

def elastic_text_search(concepto):
    """Búsqueda de Texto (BM25) en peliculas-csv."""
    try:
        resp = es.search(
            index="peliculas-csv", 
            query={
                "multi_match": {
                    "query": concepto,
                    "fields": ["overview^3", "title", "genre_names"],
                    "fuzziness": "AUTO"
                }
            },
            size=5
        )
        results = []
        for hit in resp['hits']['hits']:
            src = hit['_source']
            results.append(f"{src.get('title')} (Sinopsis: {src.get('overview')[:200]}...)")
        return results if results else "No encontré películas con esa trama en el catálogo local."
    except Exception as e: 
        return f"Error técnico buscando trama: {e}"

def search_script(frase):
    """
    Búsqueda Vectorial (768 dims) en Guiones.
    """
    try:
        # Generar vector de 768 dimensiones
        vector = embedding_model.encode(frase)
        
        resp = es.search(
            index="guiones-chunks",
            knn={
                "field": "vector", 
                "query_vector": vector, 
                "k": 3, 
                "num_candidates": 50
            }
        )
        results = []
        for h in resp['hits']['hits']:
            src = h['_source']
            if h['_score'] > 0.3: # Filtro de calidad
                results.append(f"PELÍCULA: {src['title']}\nGUION (EN): ...{src['chunk_text']}...")
            
        return "\n\n".join(results) if results else "No encontré ese diálogo exacto."
    except Exception as e: 
        st.sidebar.error(f"Error Guiones: {e}")
        return f"Error técnico buscando guiones: {str(e)}"

tools = {
    "api_search_movie": api_search_movie,
    "api_discover_movies": api_discover_movies,
    "elastic_text_search": elastic_text_search,
    "search_script": search_script
}

# ==========================================
#   4. SYSTEM PROMPT
# ==========================================
SYSTEM_PROMPT = f"""
Eres CineBot. Usa tus herramientas inteligentemente:

1. `search_script(frase)`: Úsala para buscar DIÁLOGOS, FRASES CÉLEBRES o ESCENAS CONCRETAS.
   - La base de datos de guiones está en inglés. Traduce el resultado al español para el usuario.

2. `elastic_text_search(concepto)`: Úsala para buscar películas por TRAMA o SINOPSIS en el catálogo local.
   
3. `api_search_movie(titulo)`: Si te dan el TÍTULO exacto y quieren datos oficiales.

4. `api_discover_movies(genre_id, year)`: Para filtros (Años 80, Terror, etc).
   - Mapa Géneros: {json.dumps(GENRES_MAP)}

RESPUESTA JSON OBLIGATORIA:
{{"tool": "nombre_herramienta", "parameters": {{"param": "valor"}}}}
"""

def extract_json(text):
    try:
        if "```json" in text: text = text.split("```json")[1].split("```")[0]
        start, end = text.find('{'), text.rfind('}')
        if start != -1 and end != -1: return json.loads(text[start:end+1])
    except: pass
    return None

# ==========================================
#   5. INTERFAZ
# ==========================================
st.title("🤖 CineBot IA (Pro)")

if "messages" not in st.session_state: st.session_state.messages = []

for msg in st.session_state.messages:
    if msg["role"] in ["user", "assistant"]:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

if prompt := st.chat_input("Tu consulta..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        ph = st.empty()
        history = [{"role": "system", "content": SYSTEM_PROMPT}] + st.session_state.messages
        
        try:
            with st.spinner("Pensando..."):
                max_loops = 3
                loop = 0
                final_msg = ""
                
                while loop < max_loops:
                    loop += 1
                    resp = client.chat.completions.create(model=CHAT_MODEL, messages=history, temperature=0.1)
                    content = resp.choices[0].message.content
                    tool_data = extract_json(content)
                    
                    if tool_data:
                        func = tool_data.get("tool")
                        args = tool_data.get("parameters") or {}
                        ph.markdown(f"🔎 *Ejecutando: {func} {args}...*")
                        
                        if func in tools:
                            res = tools[func](**args)
                            history.append({"role": "assistant", "content": content})
                            history.append({"role": "system", "content": f"DATOS: {json.dumps(res)}"})
                        else:
                            final_msg = "Error: Herramienta desconocida."
                            break
                    else:
                        final_msg = content
                        break
                
                if not final_msg: final_msg = "Lo siento, no pude responder."
                ph.markdown(final_msg)
                st.session_state.messages.append({"role": "assistant", "content": final_msg})
        except Exception as e:
            st.error(f"Error: {e}")