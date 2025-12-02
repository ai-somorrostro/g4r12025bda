import streamlit as st
import streamlit.components.v1 as components
import json
import requests
import os
import math
import time
from openai import OpenAI
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer

# ==========================================
#   1. CONFIGURACIÓN E INICIALIZACIÓN
# ==========================================
st.set_page_config(page_title="Cine App & Chatbot", layout="wide", page_icon="🎬")
load_dotenv()

# --- CLAVES API ---
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not TMDB_API_KEY or not OPENROUTER_API_KEY:
    st.error("❌ Faltan claves API en el archivo .env")
    st.stop()

# --- CLIENTES ---
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
CHAT_MODEL = "meta-llama/llama-3.3-70b-instruct:free"

# Inicializar Elastic de forma segura
es = None
try:
    es = Elasticsearch(
        ["https://192.199.1.38:9200", "https://192.199.1.40:9200", "https://192.199.1.54:9200"],
        api_key=("AAMUxZoBGvoQi4223Qq3", "fY1QZrRCqKZY4F8LsqAWRg"), 
        ca_certs="/home/g4/logstash-9.2.0/config/http_ca.crt"
    )
except Exception as e:
    st.error(f"Error crítico Elastic: {e}")
    st.stop()

# Inicializar Embeddings de forma segura
embedding_model = None
try:
    @st.cache_resource
    def load_model():
        return SentenceTransformer('all-MiniLM-L6-v2')
    embedding_model = load_model()
except:
    pass

# ==========================================
#   2. ESTILOS CSS (BOTÓN FLOTANTE)
# ==========================================
st.markdown("""
<style>
    div[data-testid="stPopover"] {
        position: fixed !important;
        bottom: 30px !important;
        right: 30px !important;
        z-index: 999999 !important;
        width: auto !important;
        background-color: transparent !important;
    }
    div[data-testid="stPopover"] > button {
        width: 70px !important;
        height: 70px !important;
        border-radius: 50% !important;
        background-color: #FF4B4B !important;
        color: white !important;
        border: 2px solid white !important;
        box-shadow: 0px 4px 20px rgba(0,0,0,0.4) !important;
        font-size: 30px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        padding: 0 !important;
        min-width: 70px !important;
        max-width: 70px !important;
    }
    div[data-testid="stPopover"] > button:hover {
        background-color: #FF2B2B !important;
        transform: scale(1.1) !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
#   3. LÓGICA DEL CHATBOT
# ==========================================

GENRES_MAP = {
    "Action": 28, "Adventure": 12, "Animation": 16, "Comedy": 35, "Crime": 80,
    "Documentary": 99, "Drama": 18, "Horror": 27, "Sci-Fi": 878, "Romance": 10749
}

def bot_api_search_movie(titulo):
    url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={titulo}&language=es-ES"
    try:
        data = requests.get(url).json().get("results", [])[:1]
        if data: return {"title": data[0]["title"], "overview": data[0]["overview"], "date": data[0].get("release_date")}
        return "No encontrada."
    except: return "Error API."

def bot_api_discover(genre_id=None, year=None):
    url = f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&language=es-ES&sort_by=popularity.desc"
    if genre_id: url += f"&with_genres={genre_id}"
    if year: url += f"&primary_release_year={year}"
    try:
        data = requests.get(url).json().get("results", [])[:5]
        return [f"{m['title']} ({m.get('release_date','')[:4]})" for m in data]
    except: return "Error API."

def bot_elastic_search(concepto):
    """Herramienta Vectorial: Busca por significado."""
    # PROTECCIÓN: Si el modelo no cargó, devolvemos error controlado
    if embedding_model is None:
        return "Error: El modelo de búsqueda semántica no está cargado."
        
    try:
        vector = embedding_model.encode(concepto)
        resp = es.search(
            index="peliculas-embeddings", 
            knn={
                "field": "vector_sinopsis", 
                "query_vector": vector, 
                "k": 3, 
                "num_candidates": 50
            }
        )
        # Formateamos respuesta
        return [
            f"TÍTULO: {h['_source']['title']} | SINOPSIS: {h['_source']['overview'][:200]}..." 
            for h in resp['hits']['hits']
        ]
    except Exception as e:
        return f"Error Elastic: {str(e)}"

chatbot_tools = {
    "api_search_movie": bot_api_search_movie,
    "api_discover": bot_api_discover,
    "elastic_semantic_search": bot_elastic_search
}

SYSTEM_PROMPT = f"""
Eres CineBot. Ayuda al usuario con cine.
HERRAMIENTAS:
1. `elastic_semantic_search(concepto)`: Tramas abstractas ("barco hundido").
2. `api_search_movie(titulo)`: Títulos exactos.
3. `api_discover(genre_id, year)`: Géneros y años. Mapa: {json.dumps(GENRES_MAP)}

RESPONDE SOLO JSON PARA USAR HERRAMIENTA:
{{"tool": "nombre", "parameters": {{"param": "valor"}}}}
"""

def extract_json(text):
    try:
        if "```json" in text: text = text.split("```json")[1].split("```")[0]
        start, end = text.find('{'), text.rfind('}')
        if start != -1 and end != -1: return json.loads(text[start:end+1])
    except: pass
    return None

def generar_respuesta_animada(chat_container):
    history = [{"role": "system", "content": SYSTEM_PROMPT}] + st.session_state.chat_history
    final_response = "Lo siento, error desconocido."
    
    with chat_container:
        status = st.status("🧠 Pensando...", expanded=True)
        try:
            max_loops = 3
            loop = 0
            while loop < max_loops:
                loop += 1
                resp = client.chat.completions.create(model=CHAT_MODEL, messages=history, temperature=0.1)
                content = resp.choices[0].message.content
                tool_data = extract_json(content)
                
                if tool_data:
                    func = tool_data.get("tool")
                    # PROTECCIÓN: Si parameters es None, usamos {}
                    args = tool_data.get("parameters") or {}
                    
                    status.write(f"🔎 Consultando: `{func}`...")
                    
                    if func in chatbot_tools:
                        # Ejecutamos herramienta
                        res = chatbot_tools[func](**args)
                        
                        history.append({"role": "assistant", "content": content})
                        history.append({"role": "system", "content": f"RESULTADO: {json.dumps(res)}"})
                    else:
                        final_response = "Error: Herramienta desconocida."
                        break
                else:
                    final_response = content
                    break
            
            status.update(label="¡Listo!", state="complete", expanded=False)
            st.session_state.chat_history.append({"role": "assistant", "content": final_response})
            st.rerun() 
            
        except Exception as e:
            status.update(label="Error", state="error")
            st.error(f"Error detallado: {e}")

def render_chatbot_bubble():
    if "chat_history" not in st.session_state: st.session_state.chat_history = []
    
    with st.popover("🤖", help="Chatbot"):
        st.caption("### 💬 CineBot IA")
        
        chat_container = st.container(height=400)
        with chat_container:
            if not st.session_state.chat_history:
                st.info("👋 ¡Hola! Soy CineBot. Pregúntame sobre películas.")
            
            for msg in st.session_state.chat_history:
                if msg["role"] == "user":
                    with st.chat_message("user"): st.write(msg['content'])
                elif msg["role"] == "assistant":
                    with st.chat_message("assistant"): st.write(msg['content'])

        with st.form(key="chat_form", clear_on_submit=True):
            cols = st.columns([4, 1])
            with cols[0]:
                user_input = st.text_input("Escribe...", key="user_msg_input", label_visibility="collapsed")
            with cols[1]:
                submit_btn = st.form_submit_button("➤")
            
            if submit_btn and user_input:
                with chat_container:
                    with st.chat_message("user"): st.write(user_input)
                
                st.session_state.chat_history.append({"role": "user", "content": user_input})
                generar_respuesta_animada(chat_container)

        if st.button("🗑️ Limpiar", key="del_chat", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()

# ==========================================
#   4. LÓGICA APP CATÁLOGO
# ==========================================

def subir_arriba():
    js = '''<script>
        var doc = window.parent.document;
        var container = doc.querySelector('[data-testid="stAppViewContainer"]');
        if (container) {{ container.scrollTop = 0; }}
    </script>'''
    components.html(js, height=0)

def ir_home(): st.query_params.clear(); st.rerun()
def ir_peli(id): st.query_params["view"]="movie"; st.query_params["id"]=id; st.rerun()
def ir_actor(nombre): st.query_params["view"]="actor"; st.query_params["name"]=nombre.strip(); st.rerun()
def cambiar_pag(num): st.query_params["page"]=num

@st.cache_data
def obtener_generos():
    try:
        resp = es.search(index="peliculas-csv", size=0, aggs={"lista": {"terms": {"field": "genre_names", "size": 100}}})
        return sorted([b['key'] for b in resp['aggregations']['lista']['buckets']])
    except: return []

@st.cache_data
def obtener_actores_disponibles():
    try:
        resp = es.search(index="peliculas-csv", size=0, aggs={"lista": {"terms": {"field": "cast_names.keyword", "size": 3000}}})
        return sorted([b['key'] for b in resp['aggregations']['lista']['buckets']])
    except: return []

# --- VISTAS ---
def render_movie(id_peli):
    subir_arriba()
    if st.button("⬅️ Volver"): ir_home()
    resp = es.search(index="peliculas-csv", query={"term": {"id": id_peli}}, size=1)
    if not resp['hits']['hits']: st.error("No encontrada"); return
    peli = resp['hits']['hits'][0]['_source']
    
    c1, c2 = st.columns([1, 3])
    with c1: 
        if peli.get('poster_url'): st.image(peli['poster_url'])
    with c2:
        st.title(peli.get('title'))
        st.caption(f"Original: {peli.get('original_title')} | Dir: {peli.get('director')}")
        st.info(f"⭐ {peli.get('vote_average')} | 📅 {str(peli.get('release_date',''))[:10]}")
        if peli.get('genre_names'): st.write(f"🏷️ {', '.join(peli['genre_names'])}")
        st.write(peli.get('overview'))
    
    st.divider()
    st.subheader("Reparto")
    names = peli.get('cast_names', [])
    fotos = peli.get('cast_images_urls', [])
    if names:
        cols = st.columns(6)
        for i, nom in enumerate(names[:12]):
            with cols[i%6]:
                img = fotos[i] if i<len(fotos) and fotos[i].startswith("http") else None
                if img: st.image(img)
                if st.button(nom, key=f"act_{i}"): ir_actor(nom)

def render_actor(nombre):
    subir_arriba()
    if st.button("⬅️ Inicio"): ir_home()
    st.title(f"🎞️ {nombre}")
    resp = es.search(index="peliculas-csv", query={"match_phrase": {"cast_names": nombre}}, size=50)
    hits = resp['hits']['hits']
    st.success(f"{len(hits)} películas encontradas.")
    cols = st.columns(5)
    for idx, hit in enumerate(hits):
        p = hit['_source']
        with cols[idx%5]:
            if p.get('poster_url'): st.image(p['poster_url'])
            st.caption(p.get('title'))
            if st.button("Ver", key=f"mov_{p['id']}"): ir_peli(p['id'])

def render_home():
    subir_arriba()
    st.sidebar.header("🔍 Filtros Catálogo")
    
    q_actores = st.sidebar.multiselect("Actores (Juntos)", obtener_actores_disponibles())
    q_cats = st.sidebar.multiselect("Categorías", obtener_generos())
    q_txt = st.sidebar.text_input("Título...")
    q_vote = st.sidebar.slider("Votos", 0, 10, 5)
    
    query = {"bool": {"must": [], "filter": [{"range": {"vote_average": {"gte": q_vote}}}]}}
    if q_cats: query["bool"]["filter"].append({"terms": {"genre_names": q_cats}})
    if q_actores:
        for a in q_actores: query["bool"]["must"].append({"term": {"cast_names.keyword": a}})
    if q_txt:
        query["bool"]["must"].append({"multi_match": {"query": q_txt, "fields": ["title^3", "director", "overview"], "fuzziness": "AUTO"}})
    elif not q_actores:
        query["bool"]["must"].append({"match_all": {}})
        
    page = int(st.query_params.get("page", 1))
    resp = es.search(index="peliculas-csv", query=query, size=24, from_=(page-1)*24)
    hits = resp['hits']['hits']
    total = resp['hits']['total']['value']
    max_pages = math.ceil(total / 24)
    if max_pages == 0: max_pages = 1
    
    c_head1, c_head2 = st.columns([4,1])
    with c_head1: st.subheader(f"Catálogo ({total})")
    with c_head2: 
        if page > 1: st.button("🏠 Inicio", on_click=cambiar_pag, args=(1,), key="top_home")

    cols = st.columns(4)
    for idx, hit in enumerate(hits):
        p = hit['_source']
        with cols[idx%4]:
            with st.container(border=True):
                if p.get('poster_url'): st.image(p['poster_url'])
                st.write(f"**{p.get('title')[:30]}**")
                if st.button("Ficha", key=f"h_{p['id']}"): ir_peli(p['id'])
    
    st.divider()
    c1, c2, c3 = st.columns([1,2,1])
    with c1: 
        if page>1: st.button("Anterior", on_click=cambiar_pag, args=(page-1,))
    with c2: st.markdown(f"<div style='text-align:center'>Página {page} / {max_pages}</div>", unsafe_allow_html=True)
    with c3: 
        if page<max_pages: st.button("Siguiente", on_click=cambiar_pag, args=(page+1,))

# ==========================================
#   5. EJECUCIÓN PRINCIPAL
# ==========================================
p = st.query_params
view = p.get("view", "home")

if view == "movie" and p.get("id"): render_movie(p.get("id"))
elif view == "actor" and p.get("name"): render_actor(p.get("name"))
else: render_home()

render_chatbot_bubble()