import json
import pandas as pd
from config import Config

class StorageManager:
    def __init__(self, logger):
        self.log = logger

    def save_data(self, movies):
        """Guarda los datos en JSON y CSV"""
        self.save_json(movies)
        self.save_csv(movies)

    def save_json(self, movies):
        """Guarda en archivo JSON"""
        try:
            with open(Config.JSON_FILE, 'w', encoding='utf-8') as f:
                json.dump(movies, f, ensure_ascii=False, indent=2)
            self.log.info(f"JSON guardado: {Config.JSON_FILE}")
        except Exception as e:
            self.log.error(f"Error guardando JSON: {e}")

    def save_csv(self, movies):
        """Guarda en archivo CSV usando pandas"""
        try:
            df = pd.DataFrame(movies)
            df.to_csv(Config.CSV_FILE, index=False, encoding='utf-8')
            self.log.info(f"CSV guardado: {Config.CSV_FILE}")
        except Exception as e:
            self.log.error(f"Error guardando CSV: {e}")
