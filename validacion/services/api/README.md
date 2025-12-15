FastAPI Movies API

Este pequeño servicio expone `films.json` que está en `services/data/films.json` y proporciona documentación OpenAPI/Swagger automática.

Rutas principales:
- `GET /` : Mensaje raíz
- `GET /films?limit=<n>` : Devuelve hasta `n` películas (por defecto 100)
- `GET /films/{film_id}` : Devuelve una película por su `id`

Ejecutar localmente (desde PowerShell) — instala las dependencias primero:

```powershell
python -m pip install -r "services\api\requirements.txt"
uvicorn services.api.main:app --reload --host 127.0.0.1 --port 8000
```

Documentación automática:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

Notas:
- El servidor lee `services/data/films.json`. Asegúrate de que exista y tenga formato JSON válido.
- Si prefieres usar Flask, puedo adaptar este ejemplo a Flask + `flask-restx` o `flask-smorest`.
