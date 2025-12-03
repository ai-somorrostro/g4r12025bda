import requests
import csv
import time
from datetime import datetime, timedelta
import os

# --- CONFIGURACIÓN ---
# NOTA: En producción, usar variables de entorno para el token
BEARER_TOKEN = "BEARER_TOKEN" 
LOGSTASH_WATCH_FOLDER = "/home/g4/streamlit/" 

# Fechas: Últimos 7 días (Automático)
today = datetime.now()
last_week = today - timedelta(days=7)
date_gte = last_week.strftime("%Y-%m-%d")
date_lte = today.strftime("%Y-%m-%d")

# Nombre dinámico: peliculas_nuevas_2025-12-09.csv
filename = f"peliculas_nuevas_{today.strftime('%Y-%m-%d')}.csv"
filepath = os.path.join(LOGSTASH_WATCH_FOLDER, filename)

headers = {
    "accept": "application/json",
    "Authorization": f"Bearer {BEARER_TOKEN}"
}

IMAGE_BASE_URL = "https://image.tmdb.org/t/p/"

def get_genre_map():
    url = "https://api.themoviedb.org/3/genre/movie/list?language=es"
    try:
        response = requests.get(url, headers=headers)
        return {g['id']: g['name'] for g in response.json().get('genres', [])}
    except: return {}

# --- PROCESO ---
print(f"🔎 Buscando estrenos entre {date_gte} y {date_lte}...")
genre_map = get_genre_map()

fieldnames = [
    'id', 'title', 'original_title', 'release_date', 'overview',
    'popularity', 'vote_average', 'vote_count', 'runtime',
    'poster_url', 'genre_names', 'director',
    'cast_names', 'cast_images_urls'
]

movies_found = 0

with open(filepath, 'w', newline='', encoding='utf-8') as file:
    writer = csv.DictWriter(file, fieldnames=fieldnames)
    writer.writeheader()

    for page in range(1, 15): 
        url = (f"https://api.themoviedb.org/3/discover/movie?language=es-ES&page={page}"
               f"&primary_release_date.gte={date_gte}"
               f"&primary_release_date.lte={date_lte}"
               f"&sort_by=popularity.desc")
        
        try:
            res = requests.get(url, headers=headers)
            if res.status_code != 200: break
            results = res.json().get('results', [])
            if not results: break

            for basic in results:
                if not basic.get('overview') or not basic.get('poster_path'): continue
                
                m_id = basic['id']
                try:
                    credits = requests.get(f"https://api.themoviedb.org/3/movie/{m_id}/credits?language=es-ES", headers=headers).json()
                    details = requests.get(f"https://api.themoviedb.org/3/movie/{m_id}?language=es-ES", headers=headers).json()
                except: continue

                g_names = [genre_map.get(gid, '') for gid in basic.get('genre_ids', [])]
                cast = credits.get('cast', [])[:10]
                director = next((x['name'] for x in credits.get('crew', []) if x.get('job') == 'Director'), "")
                cast_imgs = [f"{IMAGE_BASE_URL}w185{c['profile_path']}" for c in cast if c.get('profile_path')]
                
                row = {
                    'id': m_id,
                    'title': basic.get('title'),
                    'original_title': basic.get('original_title'),
                    'release_date': basic.get('release_date'),
                    'overview': basic.get('overview'),
                    'popularity': basic.get('popularity'),
                    'vote_average': basic.get('vote_average'),
                    'vote_count': basic.get('vote_count'),
                    'runtime': details.get('runtime', 0),
                    'poster_url': f"{IMAGE_BASE_URL}w500{basic.get('poster_path')}",
                    'genre_names': ", ".join(filter(None, g_names)),
                    'director': director,
                    'cast_names': ", ".join([c['name'] for c in cast]),
                    'cast_images_urls': " | ".join(cast_imgs)
                }
                writer.writerow(row)
                movies_found += 1
            time.sleep(0.2)
        except Exception as e: print(f"Error: {e}")

print(f"✅ Generado: {filename} ({movies_found} películas)")