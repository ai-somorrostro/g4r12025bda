import requests
import time
from config import Config

class TMDBExtractor:
    def __init__(self, logger):
        self.log = logger
        self.base_params = {"api_key": Config.TMDB_API_KEY, "language": "es-ES"}

    def fetch_all(self):
        """Orquesta la descarga de todas las categorías de películas"""
        all_movies = []
        
        # 1. Trending Semanal
        self.log.info("1/4 - Descargando trending semanal...")
        movies = self._get_endpoint(f"{Config.BASE_URL}/trending/movie/week", pages=30)
        all_movies.extend(movies)
        self.log.success(f"Trending -> {len(movies)} peliculas")

        # 2. Estrenos Recientes
        self.log.info("2/4 - Descargando estrenos recientes...")
        movies = self._get_endpoint(
            f"{Config.BASE_URL}/discover/movie",
            params={"primary_release_date.gte": "2023-01-01", "sort_by": "primary_release_date.desc"},
            pages=50
        )
        all_movies.extend(movies)
        self.log.success(f"Estrenos recientes -> {len(movies)} peliculas")

        # 3. Más Votadas
        self.log.info("3/4 - Más votadas históricas...")
        movies = self._get_endpoint(
            f"{Config.BASE_URL}/discover/movie",
            params={"sort_by": "vote_count.desc"},
            pages=40
        )
        all_movies.extend(movies)
        self.log.success(f"Mas votadas -> {len(movies)} peliculas")

        # 4. Mejor Valoradas (Top Rated)
        self.log.info("4/4 - Mejor valoradas...")
        movies = self._get_endpoint(f"{Config.BASE_URL}/movie/top_rated", pages=30)
        all_movies.extend(movies)
        self.log.success(f"Mejor valoradas -> {len(movies)} peliculas")

        return self._remove_duplicates(all_movies)

    def _get_endpoint(self, url, params=None, pages=20):
        """Función genérica para paginar resultados de la API"""
        movies = []
        current_params = self.base_params.copy()
        if params:
            current_params.update(params)

        for page in range(1, pages + 1):
            current_params["page"] = page
            try:
                r = requests.get(url, params=current_params, timeout=20)
                r.raise_for_status()
                data = r.json()
                results = data.get("results", [])
                movies.extend(results)
                
                if page % 5 == 0: # Log menos verboso
                    self.log.debug(f"Página {page} → {len(results)} películas")

                if page >= data.get("total_pages", 1):
                    break
                time.sleep(0.18) # Respetar rate limit
            except Exception as e:
                self.log.error(f"Error en página {page}: {e}")
                break
        return movies

    def _remove_duplicates(self, movies):
        """Elimina duplicados basandose en el ID"""
        unique_movies = {m["id"]: m for m in movies}
        return list(unique_movies.values())
