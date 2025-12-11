import streamlit as st
from elasticsearch import Elasticsearch
import math
from datetime import datetime

# ==========================================
#   1. CONFIGURACIÓN E INICIALIZACIÓN
# ==========================================
st.set_page_config(page_title="Catálogo Peliculas", layout="wide", page_icon="🎬")

# --- GESTIÓN DE MEMORIA (PERSISTENCIA DE FILTROS) ---
current_year = datetime.now().year

if "memoria_filtros" not in st.session_state:
    st.session_state.memoria_filtros = {
        "txt": "",
        "actores": [],
        "categorias": [],
        "anos": (1980, current_year),
        "votos": 5,
        "orden": "Relevancia"
    }

# --- CALLBACKS PARA GUARDAR ESTADO ---
def update_txt(): st.session_state.memoria_filtros["txt"] = st.session_state.w_txt
def update_actores(): st.session_state.memoria_filtros["actores"] = st.session_state.w_actores
def update_cats(): st.session_state.memoria_filtros["categorias"] = st.session_state.w_cats
def update_anos(): st.session_state.memoria_filtros["anos"] = st.session_state.w_anos
def update_votos(): st.session_state.memoria_filtros["votos"] = st.session_state.w_votos
def update_orden(): st.session_state.memoria_filtros["orden"] = st.session_state.w_orden

# --- CONEXIÓN ELASTICSEARCH ---
try:
    es = Elasticsearch(
        [
            "https://192.199.1.38:9200",
            "https://192.199.1.40:9200", 
            "https://192.199.1.54:9200"
        ],
        api_key=("AAMUxZoBGvoQi4223Qq3", "fY1QZrRCqKZY4F8LsqAWRg"), 
        ca_certs="/home/g4/logstash-9.2.0/config/http_ca.crt"
    )
except Exception as e:
    st.error(f"Error crítico: {e}")
    st.stop()

# --- URL DEL CHATBOT ---
URL_CHATBOT = "http://localhost:8502" 

# ==========================================
#   2. FUNCIONES AUXILIARES
# ==========================================

def ir_home():
    if "view" in st.query_params: del st.query_params["view"]
    if "id" in st.query_params: del st.query_params["id"]
    if "name" in st.query_params: del st.query_params["name"]
    st.rerun()

def ir_peli(id):
    st.query_params["view"] = "movie"
    st.query_params["id"] = id
    st.rerun()

def ir_actor(nombre):
    st.query_params["view"] = "actor"
    st.query_params["name"] = nombre.strip()
    st.rerun()

def cambiar_pag(num):
    st.query_params["page"] = num

@st.cache_data
def obtener_generos():
    try:
        resp = es.search(
            index="peliculas-csv", size=0,
            aggs={"lista": {"terms": {"field": "genre_names", "size": 100}}}
        )
        return sorted([b['key'] for b in resp['aggregations']['lista']['buckets']])
    except: return []

@st.cache_data
def obtener_actores_disponibles():
    try:
        resp = es.search(
            index="peliculas-csv", size=0,
            aggs={"lista": {"terms": {"field": "cast_names.keyword", "size": 3000}}}
        )
        return sorted([b['key'] for b in resp['aggregations']['lista']['buckets']])
    except: return []

def mostrar_boton_chatbot():
    st.sidebar.markdown("---")
    st.sidebar.header("💬 Asistente Virtual")
    st.sidebar.info("¿Dudas sobre qué ver? Pregúntale a nuestra IA.")
    st.sidebar.link_button("🤖 Abrir Chatbot IA", URL_CHATBOT, type="primary", use_container_width=True)
    st.sidebar.markdown("---")

# ==========================================
#   3. VISTAS (PANTALLAS)
# ==========================================

def render_movie(id_peli):
    mostrar_boton_chatbot()
    
    if st.button("⬅️ Volver al listado"): ir_home()

    resp = es.search(index="peliculas-csv", query={"term": {"id": id_peli}}, size=1)
    
    if not resp['hits']['hits']:
        st.error("Película no encontrada")
        return

    peli = resp['hits']['hits'][0]['_source']

    c1, c2 = st.columns([1, 3])
    with c1:
        if peli.get('poster_url'): st.image(peli.get('poster_url'), use_container_width=True)
    with c2:
        st.title(peli.get('title'))
        st.caption(f"Título original: {peli.get('original_title')} | Director: **{peli.get('director')}**")
        
        m1, m2, m3 = st.columns(3)
        m1.metric("⭐ Nota", peli.get('vote_average'))
        m2.metric("📅 Fecha", str(peli.get('release_date', ''))[:10])
        m3.metric("⏱️ Duración", f"{peli.get('runtime')} min")
        
        if peli.get('genre_names'): 
            st.info(" | ".join(peli['genre_names']))
        
        st.write(peli.get('overview'))

    st.divider()
    st.subheader("🎭 Reparto")
    
    nombres = peli.get('cast_names', [])
    fotos = peli.get('cast_images_urls', [])
    
    if nombres:
        cols = st.columns(6)
        for i, nom in enumerate(nombres[:12]):
            with cols[i % 6]:
                url = fotos[i] if i < len(fotos) and fotos[i] and fotos[i].startswith("http") else None
                if url: st.image(url, use_container_width=True)
                else: st.markdown("👤")
                
                if st.button(nom, key=f"btn_act_{i}"):
                    ir_actor(nom)

def render_actor(nombre):
    mostrar_boton_chatbot()
    
    if st.button("⬅️ Volver al inicio"): ir_home()
        
    st.title(f"🎞️ Filmografía de: {nombre}")
    
    query = {"match_phrase": {"cast_names": nombre}}
    resp = es.search(index="peliculas-csv", query=query, size=100)
    hits = resp['hits']['hits']
    
    st.success(f"Aparece en **{len(hits)}** películas de nuestra base de datos.")
    
    cols = st.columns(5)
    for idx, hit in enumerate(hits):
        p = hit['_source']
        with cols[idx % 5]:
            with st.container(border=True):
                if p.get('poster_url'): st.image(p.get('poster_url'), use_container_width=True)
                st.caption(p.get('title'))
                if st.button("Ver", key=f"ma_{p['id']}"):
                    ir_peli(p['id'])

def render_home():
    st.sidebar.header("🔍 Filtros")
    
    # 1. Texto
    q_txt = st.sidebar.text_input(
        "Buscar por título...", 
        value=st.session_state.memoria_filtros["txt"],
        on_change=update_txt,
        key="w_txt"
    )
    
    # 2. Actores
    listado_actores = obtener_actores_disponibles()
    q_actores_sel = st.sidebar.multiselect(
        "Filtrar por Reparto (Juntos)", 
        options=listado_actores, 
        default=st.session_state.memoria_filtros["actores"],
        on_change=update_actores,
        key="w_actores",
        placeholder="Ej: Brad Pitt"
    )
    
    # 3. Categorías
    q_cats = st.sidebar.multiselect(
        "Categorías", 
        obtener_generos(),
        default=st.session_state.memoria_filtros["categorias"],
        on_change=update_cats,
        key="w_cats"
    )
    
    # 4. Años
    q_year_range = st.sidebar.slider(
        "Año de estreno", 
        min_value=1950, 
        max_value=current_year, 
        value=st.session_state.memoria_filtros["anos"],
        on_change=update_anos,
        key="w_anos"
    )
    
    # 5. Votos (CORREGIDO: Quitamos el '5' posicional)
    q_vote = st.sidebar.slider(
        "Nota mínima", 0, 10,
        value=st.session_state.memoria_filtros["votos"],
        on_change=update_votos,
        key="w_votos"
    )

    # 6. Orden
    sort_options = {
        "Relevancia": "_score",
        "Más recientes": "release_date:desc",
        "Más antiguas": "release_date:asc",
        "Mejor valoradas": "vote_average:desc",
        "Más populares": "popularity:desc"
    }
    
    lista_opciones = list(sort_options.keys())
    try:
        idx_orden = lista_opciones.index(st.session_state.memoria_filtros["orden"])
    except:
        idx_orden = 0
        
    q_sort = st.sidebar.selectbox(
        "Ordenar por", 
        lista_opciones, 
        index=idx_orden,
        on_change=update_orden,
        key="w_orden"
    )

    mostrar_boton_chatbot()

    # --- Construcción Query ---
    bool_query = {"must": [], "filter": []}
    
    bool_query["filter"].append({"range": {"vote_average": {"gte": q_vote}}})
    
    bool_query["filter"].append({
        "range": {
            "release_date": {
                "gte": f"{q_year_range[0]}-01-01",
                "lte": f"{q_year_range[1]}-12-31"
            }
        }
    })
    
    if q_cats:
        bool_query["filter"].append({"terms": {"genre_names": q_cats}})
        
    if q_actores_sel:
        for actor in q_actores_sel:
            bool_query["must"].append({"term": { "cast_names.keyword": actor }})
            
    if q_txt:
        bool_query["must"].append({
            "multi_match": {
                "query": q_txt,
                "fields": ["title^3", "cast_names", "director", "genre_names"],
                "fuzziness": "AUTO"
            }
        })
    elif not q_actores_sel:
        bool_query["must"].append({"match_all": {}})

    # Paginación
    PAGE_SIZE = 24
    try: page = int(st.query_params.get("page", 1))
    except: page = 1
    if page < 1: page = 1
    
    # Sort Logic
    sort_val = sort_options[q_sort]
    if sort_val == "_score":
        sort_param = ["_score"]
    else:
        field, order = sort_val.split(":")
        sort_param = [{field: {"order": order}}]

    resp = es.search(
        index="peliculas-csv", 
        query={"bool": bool_query}, 
        sort=sort_param, 
        size=PAGE_SIZE, 
        from_=(page-1)*PAGE_SIZE
    )
    
    total = resp['hits']['total']['value']
    hits = resp['hits']['hits']
    max_pages = math.ceil(total / PAGE_SIZE)
    if max_pages == 0: max_pages = 1

    # --- UI ---
    col_t1, col_t2 = st.columns([4, 1])
    with col_t1:
        st.subheader(f"Catálogo ({total} resultados)")
    with col_t2:
        if page > 1:
            st.button("🏠 Ir al Inicio", on_click=cambiar_pag, args=(1,), key="btn_top_home")
    
    cols = st.columns(4)
    for idx, hit in enumerate(hits):
        p = hit['_source']
        with cols[idx % 4]:
            with st.container(border=True):
                if p.get('poster_url'): st.image(p.get('poster_url'), use_container_width=True)
                st.write(f"**{p.get('title')[:35]}**")
                if st.button("Ver Ficha", key=f"home_{p['id']}", use_container_width=True):
                    ir_peli(p['id'])
    
    st.divider()
    
    # Barra Paginación
    c_start, c_prev, c_txt, c_next, c_end = st.columns([1, 1, 2, 1, 1])
    
    with c_start:
        if page > 1:
            st.button("⏮ Inicio", on_click=cambiar_pag, args=(1,), use_container_width=True)
    with c_prev:
        if page > 1:
            st.button("⬅ Anterior", on_click=cambiar_pag, args=(page - 1,), use_container_width=True)
    with c_txt:
        st.markdown(f"<div style='text-align:center; padding-top:5px'><b>Página {page}</b> de {max_pages}</div>", unsafe_allow_html=True)
    with c_next:
        if page < max_pages:
            st.button("Siguiente ➡", on_click=cambiar_pag, args=(page + 1,), use_container_width=True)


# ==========================================
#   4. ROUTER PRINCIPAL
# ==========================================
p = st.query_params
view = p.get("view", "home")

if view == "movie" and p.get("id"):
    render_movie(p.get("id"))
elif view == "actor" and p.get("name"):
    render_actor(p.get("name"))
else:
    render_home()