# Sistema de Análisis de Cine con Big Data, IA y RAG Híbrido

Este repositorio contiene la implementación completa de una arquitectura de Big Data distribuida para la ingesta, procesamiento y visualización de datos cinematográficos. El sistema integra un **Cluster de Elasticsearch de 3 nodos**, pipelines ETL automatizados con **Logstash**, monitorización con **Metricbeat** y una interfaz de usuario en **Streamlit** que incluye un Chatbot con **Inteligencia Artificial Híbrida** (RAG Vectorial + API en tiempo real).

---

## Arquitectura del Sistema

El despliegue se ha realizado sobre **3 Máquinas Virtuales (Linux)** para garantizar Alta Disponibilidad (HA) y tolerancia a fallos.

| Nodo | IP | Roles Elasticsearch | Servicios Adicionales |
| :--- | :--- | :--- | :--- |
| **VM 1** | `192.199.1.38` | Master, Data, Ingest | **Kibana** (Visualización) |
| **VM 2** | `192.199.1.40` | Master, Data, Ingest | **Logstash** (ETL), **Streamlit** (App), Scripts Python |
| **VM 3** | `192.199.1.54` | Master, Data, Ingest | **Metricbeat** (Monitorización Cluster) |

---

## 1. Cluster de Elasticsearch (Configuración y Pasos)

Se ha configurado un cluster tolerante a fallos. Si un nodo cae, el sistema sigue operativo (Quórum 2/3).

### Pasos de Implementación:
1.  **Configuración de Nodos (`elasticsearch.yml`):**
    *   Se definió el nombre del cluster `cluster-reto1`.
    *   Se configuró `discovery.seed_hosts` con las 3 IPs para permitir el descubrimiento mutuo.
    *   Se habilitó `xpack.security` para cifrado y autenticación.
2.  **Seguridad y API Keys:**
    *   Se generaron certificados SSL automáticos en el primer arranque.
    *   **Gestión de Accesos:** Se crearon **API Keys** específicas para reemplazar el uso del superusuario `elastic` en las aplicaciones:
        *   *Key Ingesta:* Permisos de escritura para Logstash.
        *   *Key Lectura:* Permisos de lectura para Streamlit.
3.  **Modelado de Datos (Templates):**
    *   Se creó el template `peliculas_csv_template` con `number_of_replicas: 2` (asegurando una copia del dato en cada máquina).
    *   **Analizadores Personalizados:** Se implementó `analizador_pro` con filtro `asciifolding` para permitir búsquedas insensibles a tildes (ej: buscar "acción" encuentra "accion").
4.  **Ciclo de Vida (ILM):**
    *   Política `politica_logs_semanal`: Mueve los logs de scraping a fase "Delete" tras 30 días para optimizar disco.

---

## 2. Ingesta de Datos (ETL con Logstash)

La ingesta se gestiona desde la **VM 2** utilizando Logstash y pipelines múltiples definidos en `pipelines.yml`.

### A. Pipeline Histórico (`importar_csv.conf`)
Carga masiva de base de datos de películas (1980-2024).
*   **Limpieza:** Uso de filtros `mutate` para convertir strings en arrays y tipos numéricos.
*   **Corrección de Mapping:** Se añadió `remove_field => ["host", "event" ...]`, ya que el índice tiene `dynamic: strict` y rechazaba los metadatos automáticos de Logstash.

### B. Pipeline Diario (`scrapping_diario.conf`)
Ingesta automática de novedades.
*   **Grok (Requisito):** Se implementó un filtro `grok` para parsear y validar la fecha de estreno desde el texto crudo.
*   **Índices Dinámicos:** Configurado output con `index => "log-scrapping-%{+YYYY.MM.dd}"`, generando un índice nuevo cada día.

### C. Automatización (Scraper + Cron)
*   Se desarrolló `scraper_semanal.py` que calcula dinámicamente la fecha de los últimos 7 días.
*   Se configuró un **Cron Job** para ejecutarlo cada lunes a las 09:00 AM.

---

## 3. Inteligencia Artificial y RAG (Retrieval-Augmented Generation)

El sistema utiliza un enfoque híbrido para responder preguntas, combinando datos locales vectorizados con datos vivos de Internet.

### Procesamiento de Guiones (Embeddings)
Debido a la alta carga de CPU, el procesamiento de vectores se externalizó:
1.  **Google Colab (GPU T4):** Se ejecutó el script de chunking y vectorización utilizando el modelo multilingüe `paraphrase-multilingual-MiniLM-L12-v2`.
2.  **Transferencia:** Se generó un archivo `.pkl` con los vectores.
3.  **Ingesta Ligera:** El script `ingestar_pkl.py` subió los vectores a Elasticsearch (`guiones-chunks`) sin saturar la VM.

### Chatbot Híbrido (`app_chatbot.py`)
Utiliza **Llama 3.3** (vía OpenRouter) como cerebro orquestador.
*   **Ruta 1 (Semántica):** Preguntas abstractas ("Peli sobre sueños") -> Busca en Elastic (Vectores).
*   **Ruta 2 (Datos):** Preguntas concretas ("Director de Titanic") -> Busca en API TMDb.
*   **Ruta 3 (Guiones):** Preguntas de diálogo ("¿Qué dice Terminator?") -> Busca vectores en inglés, traduce y responde en español.

---

## 4. Aplicación Frontend (Streamlit)

La interfaz se divide en dos aplicaciones conectadas.

### Catálogo de Películas (`catalogo.py`)
*   **Persistencia:** Uso de `st.session_state` para que los filtros no se reinicien al navegar.
*   **Filtros Avanzados:**
    *   Logica **AND** para actores (Pelis que hicieron juntos).
    *   Slider de años y ordenación dinámica.
*   **UX:** Inyección de CSS (`!important`) para crear un **Botón Flotante** que abre el chatbot en una pestaña paralela.

### Chatbot (`app_chatbot.py`)
*   Interfaz de chat con historial.
*   Muestra el proceso de razonamiento ("Pensando...", "Consultando API...").
*   Sidebar con políticas de uso y aviso legal.

---

## 5. Monitorización y Visualización (Kibana)

**Ubicación:** VM 3 (Agente) -> VM 1 (Kibana).

### Metricbeat Cluster Scope
Para evitar instalar agentes en todas las máquinas, se configuró Metricbeat en la VM 3 con `scope: cluster` y el módulo `xpack`. Esto permite monitorizar el estado de salud (CPU, RAM, JVM) de los **3 nodos** desde un solo agente.

### Kibana
*   **Stack Monitoring:** Panel habilitado para ver el rendimiento en tiempo real.
*   **Dashboards:** Gráficos de negocio (Géneros más populares, Películas por año).
*   **Alertas:** Se configuró una regla para notificar en el log del servidor si la CPU de cualquier nodo supera el 80%.
    *   *Solución de error:* Se generaron claves de encriptación (`kibana-encryption-keys`) para habilitar el sistema de alertas seguro.

---

## Guía de Despliegue

### Requisitos
*   Python 3.9+
*   Acceso a las 3 VMs con Elasticsearch configurado.

### 1. Instalación de Dependencias
```bash
pip install -r src/requirements.txt
```
### 2. Configuración de Entorno
Crear un archivo `.env` en la raíz:
```env
TMDB_API_KEY="tu_clave_aqui"
OPENROUTER_API_KEY="tu_clave_aqui"
```

### 3. Ejecución de la Aplicación
El sistema requiere ejecutar dos servicios en paralelo (en dos terminales distintas):

**Terminal 1 (Catálogo - Puerto 8501):**
```bash
streamlit run src/catalogo.py --server.port 8501
```

**Terminal 2 (Chatbot - Puerto 8502):**
```bash
streamlit run src/app_chatbot.py --server.port 8502
```

## Pruebas de Redundancia (Alta Disponibilidad)

Se realizaron pruebas de estrés para validar la robustez del cluster:

1.  **Escenario:** Apagado forzoso del servicio Elasticsearch en **Nodo 1**.
2.  **Resultado Cluster:** Estado `Yellow`. Los nodos 2 y 3 asumieron la carga. No hubo pérdida de datos gracias a `replicas: 2`.
3.  **Resultado App:** Streamlit continuó funcionando sin errores, conectándose automáticamente a los nodos restantes.
4.  **Resultado Kibana:** Al recargar, Kibana conectó con el Nodo 2/3 y permitió visualizar los dashboards.

## 📂 Estructura del Repositorio

*   `config/`: Archivos YAML de configuración de Elasticsearch (por nodo) y Kibana.
*   `logstash/`: Pipelines `.conf` y configuración de `pipelines.yml`.
*   `monitoring/`: Configuración de Metricbeat y módulos del sistema.
*   `scripts/`: Scripts de Python para scraping, chunking y test de carga.
*   `src/`: Código fuente de la aplicación Streamlit (Catálogo y Chatbot).
*   `elastic_objects/`: JSONs con Templates, Policies y API Keys.
