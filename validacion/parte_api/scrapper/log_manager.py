import logging
import os
from datetime import datetime

class LogManager:
    def __init__(self, name: str = "TMDB-Scraper", log_dir: str = "logs"):
        self.name = name

        # Si `log_dir` es relativo, lo interpretamos respecto al paquete `scrapper` padre
        if not os.path.isabs(log_dir):
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            log_dir = os.path.join(base_dir, log_dir)

        # Aseguramos que la carpeta exista (no falla si ya existe)
        os.makedirs(log_dir, exist_ok=True)
        
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        if self.logger.handlers:
            return

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # Consola
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # Archivo .log en la carpeta `log_dir` pasada (ahora soporte absoluta/relativa)
        log_file = os.path.join(log_dir, f"tmdb_scraper_{datetime.now():%Y-%m-%d}.log")
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def info(self, msg):     self.logger.info(msg)
    def warning(self, msg):  self.logger.warning(msg)
    def error(self, msg, exc=False):   self.logger.error(msg, exc_info=exc)
    def debug(self, msg):    self.logger.debug(msg)
    def success(self, msg):  self.logger.info(f"ÉXITO → {msg}")
    def critical(self, msg): self.logger.critical(f"FALLO → {msg}")