# services/api/main.py
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import json
import os
import logging
from datetime import datetime
import time
import requests

app = FastAPI(title="API de Peliculas", version="1.0")

# ===================== CONFIGURACIÓN DE LOGS =====================
# Ruta al archivo JSON generado por el scrapper
if os.path.exists("/app/data"):
    DATA_DIR = "/app/data"
    LOGS_DIR = "/app/logs"
else:
    DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
    LOGS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs"))

# Crear directorio de logs si no existe
os.makedirs(LOGS_DIR, exist_ok=True)

FILMS_FILE = os.path.join(DATA_DIR, "films.json")

# Configurar logger
log_filename = os.path.join(LOGS_DIR, f"api_{datetime.now():%Y-%m-%d}.log")

# Formato común
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Handler de archivo
file_handler = logging.FileHandler(log_filename, encoding="utf-8")
file_handler.setFormatter(formatter)

# Handler de consola
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# Configurar logger de nuestra app
logger = logging.getLogger("FilmAPI")
logger.setLevel(logging.INFO)
# Evitar duplicar handlers si ya existen
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

# IMPORTANTE: Capturar logs de Uvicorn (lo que sale en terminal) en el archivo
# Esto captura "Uvicorn running on...", "Application startup complete", etc.
for log_name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
    uvicorn_log = logging.getLogger(log_name)
    # Evitar duplicar handlers
    if not any(isinstance(h, logging.FileHandler) and h.baseFilename == log_filename for h in uvicorn_log.handlers):
        uvicorn_log.addHandler(file_handler)

# ===================== MIDDLEWARE DE LOGGING =====================
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware que registra cada petición HTTP"""
    start_time = time.time()
    
    # Información de la petición
    client_ip = request.client.host if request.client else "unknown"
    method = request.method
    path = request.url.path
    
    logger.info(f"-> {method} {path} | IP: {client_ip}")
    
    # Procesar la petición
    try:
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000  # ms
        
        logger.info(f"<- {method} {path} | Status: {response.status_code} | {process_time:.2f}ms")
        
        return response
    except Exception as e:
        process_time = (time.time() - start_time) * 1000
        logger.error(f"Error: {method} {path} | Error: {str(e)} | {process_time:.2f}ms")
        raise

# ===================== ENDPOINTS =====================
@app.get("/health")
def health():
    """Endpoint de salud para verificar que la API funciona"""
    logger.info("Health check ejecutado")
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.get("/film-data")
def get_film_data():
    """Devuelve el último JSON de películas descargado por el scrapper"""
    if not os.path.exists(FILMS_FILE):
        logger.warning(f"Archivo de películas no encontrado: {FILMS_FILE}")
        raise HTTPException(
            status_code=404, 
            detail=f"No se encontró el archivo de películas. Buscando en: {FILMS_FILE}"
        )
    
    try:
        with open(FILMS_FILE, 'r', encoding='utf-8') as f:
            films = json.load(f)
        logger.info(f"Devolviendo {len(films)} películas")
        return {
            "total": len(films),
            "films": films
        }
    except Exception as e:
        logger.error(f"Error al leer archivo de películas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al leer el archivo: {str(e)}")

@app.get("/film/{film_title}")
def get_film_by_title(film_title: str):
    """Obtiene una película específica por su título exacto"""
    if not os.path.exists(FILMS_FILE):
        logger.warning("Archivo de películas no encontrado")
        raise HTTPException(
            status_code=404, 
            detail="No se encontró el archivo de películas"
        )
    
    try:
        with open(FILMS_FILE, 'r', encoding='utf-8') as f:
            films = json.load(f)
        
        # Buscar la película por título exacto
        for film in films:
            if film.get("title", "").strip() == film_title.strip():
                logger.info(f"Película encontrada: {film_title}")
                return {
                    "success": True,
                    "film": film
                }
        
        # Si no se encontró
        logger.warning(f"Película no encontrada: {film_title}")
        raise HTTPException(
            status_code=404, 
            detail=f"No se encontró ninguna película con el título exacto: '{film_title}'"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error buscando película '{film_title}': {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al buscar la película: {str(e)}")

@app.post("/film-data")
def create_film(film_data: dict):
    """Crea/añade una nueva película al catálogo"""
    if not os.path.exists(FILMS_FILE):
        logger.warning("Archivo de películas no encontrado")
        raise HTTPException(
            status_code=404, 
            detail="No se encontró el archivo de películas"
        )
    
    try:
        # Leer el archivo JSON
        with open(FILMS_FILE, 'r', encoding='utf-8') as f:
            films = json.load(f)
        
        # Verificar si se proporcionó un ID
        if "id" not in film_data:
            # Generar un ID único (max_id + 1)
            max_id = max([film.get("id", 0) for film in films], default=0)
            film_data["id"] = max_id + 1
            logger.info(f"ID generado automáticamente: {film_data['id']}")
        else:
            # Verificar que el ID no exista ya
            existing_ids = [film.get("id") for film in films]
            if film_data["id"] in existing_ids:
                logger.warning(f"Intento de crear película con ID duplicado: {film_data['id']}")
                raise HTTPException(
                    status_code=409, 
                    detail=f"Ya existe una película con el ID: {film_data['id']}"
                )
        
        # Agregar la nueva película al array
        films.append(film_data)
        
        # Guardar el archivo actualizado
        with open(FILMS_FILE, 'w', encoding='utf-8') as f:
            json.dump(films, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Película creada: {film_data.get('title', 'Sin título')} (ID: {film_data['id']})") 
        
        return {
            "success": True,
            "message": "Película creada correctamente",
            "created_film": film_data,
            "total_films": len(films)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al crear película: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al crear la película: {str(e)}")

@app.put("/film-data/{film_title}")
def update_film(film_title: str, film_data: dict):
    """Actualiza/modifica los datos de una película por su título"""
    if not os.path.exists(FILMS_FILE):
        logger.warning("Archivo de películas no encontrado")
        raise HTTPException(
            status_code=404, 
            detail="No se encontró el archivo de películas"
        )
    
    try:
        # Leer el archivo JSON
        with open(FILMS_FILE, 'r', encoding='utf-8') as f:
            films = json.load(f)
        
        # Buscar la película por título exacto
        film_found = False
        updated_film = None
        for i, film in enumerate(films):
            if film.get("title", "").strip() == film_title.strip():
                # Actualizar los campos proporcionados (merge)
                films[i].update(film_data)
                updated_film = films[i]
                film_found = True
                break
        
        if not film_found:
            logger.warning(f"Intento de actualizar película inexistente: {film_title}")
            raise HTTPException(
                status_code=404, 
                detail=f"No se encontró ninguna película con el título exacto: '{film_title}'"
            )
        
        # Guardar el archivo actualizado
        with open(FILMS_FILE, 'w', encoding='utf-8') as f:
            json.dump(films, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Película actualizada: {film_title}")
        
        return {
            "success": True,
            "message": f"Película '{film_title}' actualizada correctamente",
            "updated_film": updated_film
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al actualizar película '{film_title}': {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al actualizar la película: {str(e)}")

@app.delete("/film-data/{film_title}")
def delete_film(film_title: str):
    """Elimina una película por nombre exacto"""
    if not os.path.exists(FILMS_FILE):
        logger.warning("Archivo de películas no encontrado")
        raise HTTPException(
            status_code=404, 
            detail="No se encontró el archivo de películas"
        )
    
    try:
        # Leer el archivo JSON
        with open(FILMS_FILE, 'r', encoding='utf-8') as f:
            films = json.load(f)
        
        # Buscar y eliminar la película con título exacto
        initial_count = len(films)
        films_filtered = [
            film for film in films 
            if film.get("title", "").strip() != film_title.strip()
        ]
        
        # Verificar si se eliminó alguna película
        if len(films_filtered) == initial_count:
            logger.warning(f"Intento de eliminar película inexistente: {film_title}")
            raise HTTPException(
                status_code=404, 
                detail=f"No se encontró ninguna película con el título exacto: '{film_title}'"
            )
        
        # Guardar el archivo actualizado
        with open(FILMS_FILE, 'w', encoding='utf-8') as f:
            json.dump(films_filtered, f, ensure_ascii=False, indent=2)
        
        deleted_count = initial_count - len(films_filtered)
        logger.info(f"Película eliminada: {film_title} ({deleted_count} eliminada(s))")
        
        return {
            "success": True,
            "message": f"Película '{film_title}' eliminada correctamente",
            "deleted_count": deleted_count,
            "remaining_films": len(films_filtered)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al eliminar película '{film_title}': {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar la película: {str(e)}")