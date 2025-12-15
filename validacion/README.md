# Proyecto RETO 1 - Sistema de Gestion de Peliculas

Este proyecto implementa un sistema completo de ingesta, almacenamiento y exposicion de datos de peliculas, utilizando una arquitectura de microservicios contenerizada con Docker.

## Funcionalidades

### 1. Scrapper (Extraccion de Datos)
- **Modulo de Extraccion**: Obtiene datos de peliculas de TMDB.
- **Almacenamiento**: Guarda los datos en formato JSON en `services/data/films.json`.
- **Logging**: Registra el proceso de extraccion en `services/logs/`.

### 2. API REST (FastAPI)
- **Endpoints CRUD**:
    - `GET /film-data`: Obtener todas las peliculas.
    - `GET /film/{title}`: Buscar pelicula por titulo.
    - `POST /film-data`: Crear nueva pelicula.
    - `PUT /film-data/{title}`: Actualizar pelicula.
    - `DELETE /film-data/{title}`: Eliminar pelicula.
- **Sincronizacion**: Endpoint `/sync-logstash` para enviar datos a ElasticSearch.
- **Documentacion**: Swagger UI disponible en `/docs`.
- **Logging**: Middleware para registrar todas las peticiones HTTP.

### 3. Almacenamiento y Busqueda (Elastic Stack)
- **Elasticsearch**: Motor de busqueda y analitica.
- **Logstash**: Pipeline de procesamiento de datos.

## Tecnologias
- **Lenguaje**: Python 3.9+
- **Framework Web**: FastAPI
- **Contenedores**: Docker & Docker Compose
- **Base de Datos**: Elasticsearch (NoSQL)

## Requisitos Previos
- Docker Desktop instalado y corriendo.
- Git.

## Instalacion y Despliegue

1.  **Clonar el repositorio**:
    ```bash
    git clone https://github.com/ai-somorrostro/g4r12025pia.git
    cd g4r12025pia
    ```

2.  **Iniciar los servicios**:
    ```bash
    docker-compose up -d --build
    ```

## Documentacion de la API
Una vez levantado el servicio, accede a la documentacion interactiva:
- **Swagger UI**: [http://localhost:8001/docs](http://localhost:8001/docs)

## Estructura del Proyecto
```
.
├── services/
│   ├── api/            # Servicio FastAPI
│   ├── scrapper/       # Servicio de extraccion de datos
│   ├── data/           # Volumen de datos (JSON)
│   ├── logs/           # Logs compartidos
│   └── logstash/       # Configuracion de Logstash
├── docker-compose.yml  # Orquestacion de contenedores
└── README.md           # Documentacion
```

## Contribucion
1.  Crear una rama para la nueva funcionalidad (`git checkout -b feature/nueva-funcionalidad`).
2.  Realizar cambios y commits descriptivos.
3.  Subir cambios y crear un Pull Request.




# Funcionamiento del Chatbot y RAG

Este documento detalla la arquitectura lógica, el flujo de datos y los algoritmos utilizados por **CineBot** para procesar el lenguaje natural, recuperar información (RAG) y generar respuestas precisas.

---

## 1. Arquitectura Híbrida (Hybrid RAG)

El chatbot no depende de una única fuente de información. Utiliza una arquitectura de **RAG Agéntico (Agentic RAG)**, donde un Modelo de Lenguaje (LLM) actúa como orquestador para decidir qué "memoria" consultar según la intención del usuario.

### Componentes del Cerebro
1.  **Orquestador (LLM):** `Meta Llama 3.3 70B Instruct`. Seleccionado por su alta capacidad de razonamiento lógico y seguimiento de instrucciones en formato JSON.
2.  **Motor Vectorial (Embeddings):** `paraphrase-multilingual-mpnet-base-v2` (768 dimensiones). Convierte texto a vectores matemáticos.
3.  **Base de Datos Vectorial:** Elasticsearch.
4.  **Datos en Tiempo Real:** API de TMDb.

---

## 2. Mecánica del RAG (Retrieval-Augmented Generation)

El sistema RAG implementado es **Multilingüe y Semántico**. A diferencia de una búsqueda tradicional por palabras clave (SQL `LIKE`), este sistema busca por **significado**.

### Flujo de Vectorización Multilingüe
Una de las características más avanzadas del sistema es su capacidad de cruzar idiomas:

1.  **Entrada:** El usuario pregunta en **Español**: *"¿Qué dice Terminator?"*
2.  **Embedding:** El modelo transforma la frase en un vector numérico de 768 dimensiones.
    *   *Nota:* Este modelo sitúa frases con el mismo significado (aunque estén en distintos idiomas) en puntos cercanos del espacio vectorial.
3.  **Búsqueda (KNN):** Elasticsearch busca los vectores más cercanos ("vecinos") en el índice `guiones-chunks` (que contiene textos en **Inglés**).
4.  **Recuperación:** Encuentra el fragmento original: *"I'll be back"*.
5.  **Generación:** El LLM recibe el fragmento en inglés y genera la respuesta final en español.

---

## 3. Explicación de los "Scores" (Puntuación de Similitud)

Cuando el chatbot utiliza las herramientas de búsqueda vectorial (`search_script` o `elastic_semantic_search`), Elasticsearch devuelve un valor llamado **`_score`**.

### ¿Qué es el Score?
Es una métrica de **Similitud del Coseno** (Cosine Similarity). Representa cuánto se parece el vector de la pregunta del usuario al vector del documento encontrado.

*   **Rango:** 0.0 (Nada parecido) a 1.0 (Idéntico).

### Interpretación en el Sistema
En el código del chatbot, utilizamos estos scores para filtrar "ruido" (resultados irrelevantes):

| Rango de Score | Interpretación | Acción del Chatbot |
| :--- | :--- | :--- |
| **> 0.7** | **Coincidencia Exacta/Muy Alta.** | Es casi seguro la frase o trama que busca el usuario. |
| **0.5 - 0.7** | **Coincidencia Semántica Fuerte.** | El concepto es el mismo, aunque las palabras varíen. |
| **0.3 - 0.5** | **Relación Contextual.** | Puede ser relevante. Se muestra al usuario. |
| **< 0.3** | **Ruido / Irrelevante.** | **Filtrado Automático.** El código descarta estos resultados para evitar alucinaciones. |

*Ejemplo:* Si preguntas "barco hundido", la película *Titanic* tendrá un score alto (ej: 0.75). Una película sobre un submarino podría tener un 0.4. Una comedia romántica en la playa tendría < 0.2.

---

## 4. Tipos de Preguntas y Enrutamiento (Routing)

El `System Prompt` instruye a la IA para clasificar la pregunta del usuario y elegir una de las tres rutas posibles.

### Ruta A: Búsqueda de Diálogos (RAG Profundo)
*   **Intención:** El usuario busca una frase específica, una cita o una escena concreta.
*   **Herramienta:** `search_script(frase)`
*   **Fuente:** Índice `guiones-chunks` (Vectores).
*   **Ejemplo:** *"Busca la escena donde hablan de hamburguesas en Pulp Fiction."*

### Ruta B: Búsqueda de Trama Abstracta (RAG Semántico)
*   **Intención:** El usuario no sabe el título, pero recuerda de qué va la película, o busca por temática/sensación.
*   **Herramienta:** `elastic_semantic_search(concepto)` (antes llamada `elastic_text_search` con vectores).
*   **Fuente:** Índice `peliculas-embeddings` (Vectores de sinopsis).
*   **Ejemplo:** *"Película triste sobre la guerra y un niño."*

### Ruta C: Datos Estructurados (API en Vivo)
*   **Intención:** El usuario pide datos factuales, novedades, filmografías o filtros exactos.
*   **Herramienta:** `api_search_movie`, `api_discover`.
*   **Fuente:** TMDb API (JSON en tiempo real).
*   **Ejemplo:** *"Estrenos de 2024", "¿Quién dirigió Avatar?", "Pelis de Brad Pitt".*

---

## 5. Ciclo de Vida de una Respuesta

1.  **Recepción:** El usuario envía el mensaje.
2.  **Razonamiento:** Llama 3.3 analiza el historial y el prompt. Decide si puede responder de memoria o necesita una herramienta.
3.  **Generación de JSON:** Si necesita herramienta, genera: `{ "tool": "search_script", "parameters": { "frase": "..." } }`.
4.  **Intercepción:** El script de Python detecta el JSON, ejecuta la consulta contra Elasticsearch o la API.
5.  **Inyección de Contexto:** El resultado (con sus scores y textos crudos) se añade al historial del chat como un mensaje del sistema (invisible al usuario).
6.  **Síntesis Final:** Llama 3.3 lee el resultado recuperado y redacta una respuesta natural y amable en español.

---

## 6. Depuración y Transparencia

Para garantizar la confianza en el sistema, la interfaz de usuario incluye mecanismos de **Debug**:

*   **Expander "Datos Técnicos":** Si el usuario despliega los detalles en la respuesta, puede ver:
    *   La herramienta exacta utilizada.
    *   El JSON crudo devuelto.
    *   La tabla con los **Scores de similitud** de cada fragmento encontrado.
    *   El texto original en inglés (en caso de guiones).
