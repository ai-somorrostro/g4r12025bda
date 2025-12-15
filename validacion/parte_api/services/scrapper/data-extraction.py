import time
from log_manager import LogManager
from config import Config
from modules.extractor import TMDBExtractor
from modules.storage import StorageManager

# Inicializar Logger
log = LogManager("TMDB-Scraper", log_dir=Config.LOGS_DIR)

def run_scraper():
    """Funcion principal de ejecucion del scraper"""
    Config.ensure_directories()
    
    extractor = TMDBExtractor(log)
    storage = StorageManager(log)
    
    log.info("=== INICIO CICLO DE EXTRACCIÓN ===")
    start_time = time.time()
    
    # 1. Extraer datos
    movies = extractor.fetch_all()
    
    # 2. Guardar datos
    if movies:
        storage.save_data(movies)
        
        duration = (time.time() - start_time) / 60
        log.success(f"Ciclo completado en {duration:.1f} minutos. Total: {len(movies)} películas.")
    else:
        log.warning("No se obtuvieron películas en este ciclo.")

if __name__ == "__main__":
    log.info("=== INICIO SERVICIO SCRAPER (Modo Continuo) ===")
    log.info(f"Intervalo configurado: {Config.INTERVAL_MINUTES} minutos")
    
    cycle = 1
    while True:
        try:
            log.info(f"[Ciclo {cycle}] Iniciando...")
            run_scraper()
            
            log.info(f"Esperando {Config.INTERVAL_MINUTES} minutos...")
            time.sleep(Config.INTERVAL_MINUTES * 60)
            cycle += 1
            
        except KeyboardInterrupt:
            log.warning("Servicio detenido por el usuario.")
            break
        except Exception as e:
            log.error(f"Error crítico en ciclo {cycle}: {e}", exc=True)
            log.info(f"Reintentando en {Config.INTERVAL_MINUTES} minutos...")
            time.sleep(Config.INTERVAL_MINUTES * 60)
