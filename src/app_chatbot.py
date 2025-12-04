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
CHAT_MODEL = "meta-llama/llama-3.3-70b-instruct"

# B. Cliente Elastic
try:
    es = Elasticsearch(
        ["https://192.199.1.38:9200", "https://192.199.1.40:9200", "https://192.199.1.54:9200"],
        api_key=("4Etb6JoBHk-0Ge2TdtLz", "Ag2-mARBGEkGIpcHhBDoOQ"), 
        ca_certs="/home/g4/logstash-9.2.0/config/http_ca.crt",
        request_timeout=30 # Aumentamos tiempo de espera por si la red va lenta
    )
except Exception as e:
    st.sidebar.error(f"Error conexión Elastic: {e}")

# C. Modelo de Embeddings MULTILINGÜE (OBLIGATORIO PARA TU CASO)
@st.cache_resource
def load_embedding_model():
    # Este modelo conecta Español con Inglés matemáticamente
    return SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

try: embedding_model = load_embedding_model()
except: pass

with st.sidebar:
    st.image("https://www.themoviedb.org/assets/2/v4/logos/v2/blue_square_2-d537fb228cf3ed904152326207195c357471de445699156318427438ea96f33d.svg", width=100)
    st.markdown("### CineBot Híbrido")
    st.info("Inteligencia Artificial conectada a TMDb (Internet) y Memoria Local (Elasticsearch).")
    
    st.markdown("---")
    st.caption("⚖️ **Aviso Legal y Ético:**")
    st.caption("1. **Precisión:** La IA puede alucinar. Verifica datos críticos.")
    st.caption("2. **Atribución:** Este producto usa la API de TMDb pero no está avalado por TMDb.")
    st.caption("3. **Privacidad:** No compartas datos personales.")
    st.markdown("---")
    
    if st.button("🗑️ Borrar Historial"):
        st.session_state.messages = []
        st.rerun()

# ==========================================
#   3. HERRAMIENTAS
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
            return {
                "source": "API TMDb",
                "title": data[0]["title"], 
                "overview": data[0]["overview"],
                "date": data[0].get("release_date")
            }
        return "No encontrada."
    except Exception as e: return f"Error API: {e}"

def api_discover_movies(genre_id=None, year=None):
    """Filtra películas por género y año."""
    url = f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&language=es-ES&sort_by=popularity.desc"
    if genre_id: url += f"&with_genres={genre_id}"
    if year: url += f"&primary_release_year={year}"
    try:
        data = requests.get(url).json().get("results", [])[:5]
        return [f"- {m['title']} ({m.get('release_date','')[:4]}): {m['overview'][:100]}..." for m in data]
    except Exception as e: return f"Error API Discover: {e}"

def elastic_semantic_search(concepto):
    """Búsqueda vectorial en sinopsis."""
    try:
        vector = embedding_model.encode(concepto)
        resp = es.search(
            index="peliculas-csv",
            knn={"field": "vector_sinopsis", "query_vector": vector, "k": 3, "num_candidates": 50}
        )
        return [f"{h['_source'].get('title')} (Trama Local)" for h in resp['hits']['hits']]
    except Exception as e:
        st.sidebar.error(f"Error Elastic Trama: {e}") # Mostramos error real
        return "Error técnico en búsqueda local."

def search_script(frase):
    """
    Búsqueda en GUIONES (Multilingüe).
    El usuario pregunta en Español -> Vector Multilingüe -> Match en Inglés.
    """
    try:
        # 1. Vectorizar la frase en español
        vector = embedding_model.encode(frase)
        
        # 2. Buscar en el índice de guiones
        resp = es.search(
            index="guiones-chunks",
            knn={
                "field": "vector", 
                "query_vector": vector, 
                "k": 3, 
                "num_candidates": 50
            }
        )
        
        resultados = []
        for h in resp['hits']['hits']:
            src = h['_source']
            score = h['_score']
            # Filtramos resultados con poca coincidencia (ruido)
            if score > 0.3: 
                resultados.append(f"PELÍCULA: {src['title']}\nGUION (EN): ...{src['chunk_text']}...")
            
        if not resultados:
            return "No encontré diálogos que coincidan suficientemente."
            
        return "\n\n".join(resultados)
        
    except Exception as e:
        # IMPORTANTE: Esto imprimirá el error real en la barra lateral
        st.sidebar.error(f"❌ Error buscando guiones: {e}")
        return f"Error técnico buscando en guiones: {str(e)}"

tools = {
    "api_search_movie": api_search_movie,
    "api_discover_movies": api_discover_movies,
    "elastic_semantic_search": elastic_semantic_search,
    "search_script": search_script
}

# ==========================================
#   4. SYSTEM PROMPT
# ==========================================
SYSTEM_PROMPT = f"""
Eres CineBot.

HERRAMIENTAS:
1. `search_script(frase)`: Úsala para preguntas sobre DIÁLOGOS o ESCENAS ("qué dice Vincent").
   - El texto que encontrarás está en INGLÉS.
   - Tradúcelo y explícaselo al usuario en ESPAÑOL.

2. `elastic_semantic_search(concepto)`: Tramas abstractas ("barco hundido").
3. `api_search_movie(titulo)`: Títulos exactos.
4. `api_discover_movies(genre_id, year)`: Géneros y años. Mapa: {json.dumps(GENRES_MAP)}

RESPONDE SOLO JSON:
{{"tool": "nombre", "parameters": {{"param": "valor"}}}}
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
st.title("🤖 CineBot IA")

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
            with st.spinner("Procesando..."):
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
                
                if not final_msg: final_msg = "Lo siento, no pude generar una respuesta."
                ph.markdown(final_msg)
                st.session_state.messages.append({"role": "assistant", "content": final_msg})
        except Exception as e:
            st.error(f"Error: {e}")
