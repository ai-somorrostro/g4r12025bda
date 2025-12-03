import streamlit as st
import json
import requests
import os
import re
from openai import OpenAI
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer

# --- 1. CONFIGURACIÓN ---
load_dotenv()
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

st.set_page_config(page_title="CineBot Todoterreno", page_icon="🤠", layout="centered")

if not TMDB_API_KEY or not OPENROUTER_API_KEY:
    st.error("❌ Faltan claves API.")
    st.stop()

# --- 2. BARRA LATERAL (POLÍTICAS Y LEGAL) ---
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

# --- 3. CONEXIONES ---
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
MODEL_NAME = "meta-llama/llama-3.3-70b-instruct"

# Conexión a Elastic (Local)
try:
    es = Elasticsearch(
        "https://192.199.1.40:9200",
        basic_auth=("elastic", "NVXTjg51rlb69J2euNbB"), 
        ca_certs="/home/g4/logstash-9.2.0/config/http_ca.crt"
    )
except: pass

# Modelo de Embeddings
@st.cache_resource
def load_embedding_model():
    return SentenceTransformer('all-MiniLM-L6-v2')

try: embedding_model = load_embedding_model()
except: pass

# --- 4. MAPA DE GÉNEROS ---
GENRES_MAP = {
    "Action": 28, "Adventure": 12, "Animation": 16, "Comedy": 35, "Crime": 80,
    "Documentary": 99, "Drama": 18, "Family": 10751, "Fantasy": 14, "History": 36,
    "Horror": 27, "Music": 10402, "Mystery": 9648, "Romance": 10749,
    "Sci-Fi": 878, "Thriller": 53, "War": 10752, "Western": 37
}

# --- 5. HERRAMIENTAS ---

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
        if not data: return "No se encontraron películas con esos filtros."
        
        # Formateamos la respuesta para que la IA la entienda fácil
        return [f"- {m['title']} ({m.get('release_date','')[:4]}): {m['overview'][:100]}..." for m in data]
    except Exception as e: return f"Error API Discover: {e}"

def elastic_semantic_search(concepto):
    """Búsqueda vectorial local."""
    try:
        vector = embedding_model.encode(concepto)
        resp = es.search(
            index="peliculas-embeddings",
            knn={"field": "vector_sinopsis", "query_vector": vector, "k": 3, "num_candidates": 50}
        )
        results = []
        for hit in resp['hits']['hits']:
            results.append(f"{hit['_source'].get('title')} (Local)")
        return results if results else "Sin coincidencias locales."
    except: return "Error Elastic (Índice no disponible)."

tools = {
    "api_search_movie": api_search_movie,
    "api_discover_movies": api_discover_movies,
    "elastic_semantic_search": elastic_semantic_search
}

# --- 6. SYSTEM PROMPT ---
SYSTEM_PROMPT = f"""
Eres CineBot. Usa las herramientas para responder.

HERRAMIENTAS:
1. `elastic_semantic_search(concepto)`: Para tramas abstractas ("barco hundido").
2. `api_search_movie(titulo)`: Para títulos exactos.
3. `api_discover_movies(genre_id, year)`: Para géneros y años.

MAPA GÉNEROS: {json.dumps(GENRES_MAP)}

SI TE PIDEN "WESTERN DE LOS 80":
- Western es ID 37.
- "De los 80" es una década. Elige un año representativo (ej: 1985) o busca sin año si fallas.
- Llama a: `api_discover_movies(genre_id=37, year=1985)`

RESPUESTA JSON OBLIGATORIA PARA HERRAMIENTAS:
{{"tool": "nombre", "parameters": {{"param": "valor"}}}}
"""

def extract_json(text):
    try:
        if "```json" in text: text = text.split("```json")[1].split("```")[0]
        start, end = text.find('{'), text.rfind('}')
        if start != -1 and end != -1: return json.loads(text[start:end+1])
    except: pass
    return None

# --- 7. INTERFAZ ---
st.title("CineBot")

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
                    resp = client.chat.completions.create(model=MODEL_NAME, messages=history, temperature=0.1)
                    content = resp.choices[0].message.content
                    tool_data = extract_json(content)
                    
                    if tool_data:
                        func = tool_data["tool"]
                        args = tool_data.get("parameters", {})
                        ph.markdown(f"🔎 *Ejecutando: {func} {args}...*")
                        
                        if func in tools:
                            res = tools[func](**args)
                            history.append({"role": "assistant", "content": content})
                            history.append({"role": "system", "content": f"DATOS: {json.dumps(res)}"})
                        else:
                            final_msg = "Error: Intenté usar una herramienta que no existe."
                            break
                    else:
                        final_msg = content
                        break
                
                # CONTROL DE ERRORES: Si final_msg está vacío, avisamos
                if not final_msg:
                    final_msg = "Lo siento, obtuve los datos pero no supe generar una respuesta final. Inténtalo de nuevo."

                ph.markdown(final_msg)
                st.session_state.messages.append({"role": "assistant", "content": final_msg})
        except Exception as e:
            st.error(f"Error: {e}")
