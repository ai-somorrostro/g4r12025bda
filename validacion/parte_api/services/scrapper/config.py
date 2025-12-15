import os

class Config:
    # Configuracion de TMDB
    TMDB_API_KEY = os.getenv("TMDB_API_KEY", "7a3fe81983e3595f4ed4a0c67777af0b")
    BASE_URL = "https://api.themoviedb.org/3"
    
    # Rutas
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    LOGS_DIR = os.path.join(BASE_DIR, "logs")
    
    # Archivos
    JSON_FILE = os.path.join(DATA_DIR, "films.json")
    CSV_FILE = os.path.join(DATA_DIR, "films.csv")
    
    # Ejecucion
    INTERVAL_MINUTES = int(os.getenv("INTERVAL_MINUTES", 10))

    @staticmethod
    def ensure_directories():
        os.makedirs(Config.DATA_DIR, exist_ok=True)
        os.makedirs(Config.LOGS_DIR, exist_ok=True)
