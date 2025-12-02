# 🎬 Sistema de Análisis de Cine con Big Data, IA y RAG Híbrido

Este proyecto implementa una arquitectura completa de **Big Data** distribuida para la ingesta, procesamiento, búsqueda y visualización de datos cinematográficos. Incluye un cluster de **Elasticsearch de 3 nodos**, pipelines de ingestión automatizados con **Logstash**, y una interfaz de usuario en **Streamlit** que integra un **Chatbot con RAG Híbrido** (Búsqueda Vectorial Local + API Externa).

---

## 🏗️ Arquitectura del Sistema

El sistema está desplegado sobre 3 Máquinas Virtuales (Linux) para garantizar Alta Disponibilidad (HA) y distribución de carga.

| Máquina | IP | Servicios Desplegados | Rol en Cluster |
| :--- | :--- | :--- | :--- |
| **VM 1** | `192.199.1.38` | Elasticsearch, Kibana | Master, Data, Ingest |
| **VM 2** | `192.199.1.40` | Elasticsearch, Logstash, Python App | Master, Data, Ingest |
| **VM 3** | `192.199.1.54` | Elasticsearch, Metricbeat | Master, Data, Ingest |

### Diagrama de Flujo de Datos
1.  **Scraping:** Python extrae datos de TMDb (Histórico y Novedades Semanales).
2.  **ETL:** Logstash procesa CSVs -> Limpieza -> Grok -> Elasticsearch.
3.  **Vectorización:** Google Colab (GPU) procesa guiones -> Vectores -> Ingesta en VM.
4.  **Almacenamiento:** Cluster Elasticsearch (3 Nodos, Réplicas=2).
5.  **Visualización:** Kibana (Dashboards Operativos y de Negocio).
6.  **Frontend:** Streamlit + Chatbot IA (Llama 3.3 vía OpenRouter).

---

## 🚀 1. Despliegue del Cluster Elasticsearch

### Configuración Distribuida
Se ha configurado un cluster tolerante a fallos. Si cae un nodo, el servicio continúa (Quórum 2/3).

*   **Configuración clave (`elasticsearch.yml`):**
    *   `discovery.seed_hosts`: Lista de las 3 IPs para que los nodos se encuentren.
    *   `cluster.initial_master_nodes`: Definido solo en el primer arranque.
    *   `network.host`: Binding a la IP pública de cada VM.

### Seguridad (API Keys)
Se ha deshabilitado el uso de usuario/contraseña (`elastic`) en las aplicaciones en favor de **API Keys** con permisos granulares:
*   🔑 **Logstash Writer:** Permisos solo de escritura y creación de índices (`create`, `write`).
*   🔑 **Streamlit Reader:** Permisos solo de lectura (`read`, `search`).

---

## 🔄 2. Ingesta de Datos (Logstash & Pipelines)

Se utiliza **Logstash** en la VM 2 gestionado mediante `pipelines.yml`.

### Pipeline 1: Carga Histórica (`importar_csv.conf`)
*   **Fuente:** Archivos CSV masivos de películas (años 80-2024).
*   **Transformaciones:**
    *   `mutate/split`: Convierte strings "Acción, Drama" en Arrays reales.
    *   `mutate/remove_field`: Elimina metadatos (`host`, `event`) para cumplir con **Mapping Estricto**.

### Pipeline 2: Scraping Diario (`scrapping_diario.conf`)
*   **Automatización:** Script Python ejecutado vía **Cron Job** cada lunes a las 09:00.
*   **Requisito Grok:** Se utiliza el plugin `grok` para parsear y validar el formato de la fecha de estreno en los logs de entrada.
*   **Índices Dinámicos:** Output configurado con `index => "log-scrapping-%{+YYYY.MM.dd}"` para rotación diaria.

---

## ⚙️ 3. Optimización y Gestión de Índices

### Plantillas (`_index_template`)
Se ha definido una plantilla `peliculas_csv_template` que aplica automáticamente:
*   **Shards:** 1 (Suficiente para el volumen de datos).
*   **Réplicas:** 2 (Para tener una copia en CADA nodo del cluster).
*   **Mapping:** `dynamic: strict` (Seguridad de esquema).
*   **Analizadores:** Creación de un analizador custom (`analizador_pro`) con `asciifolding` para búsquedas insensibles a tildes (ej: "acción" = "accion").

### Ciclo de Vida (ILM Policies)
Política `politica_logs_semanal` aplicada a los índices de logs de scraping:
1.  **Hot:** Escritura activa.
2.  **Delete:** Borrado automático a los 30 días para optimizar espacio en disco.

---

## 🧠 4. Aplicación: Buscador & Chatbot IA

El frontend está desarrollado en **Streamlit** (`src/app_cine_completa.py`).

### Características del Catálogo
*   **Filtros Avanzados:** Filtrado multicriterio (Actores con lógica AND, Categorías con lógica OR).
*   **Paginación Eficiente:** Uso de `from` y `size` en Elasticsearch (no descarga toda la BD).
*   **Navegación:** Botones "Atrás" y "Inicio" funcionales mediante gestión de URL params.

### 🤖 Chatbot Híbrido (RAG + Herramientas)
Implementación avanzada de IA utilizando **Llama 3.3** (vía OpenRouter). El bot decide qué herramienta usar:

1.  **Vía API (Datos Estructurados):**
    *   Si el usuario pregunta *"Películas de Brad Pitt"*, el bot usa la API de TMDb.
    *   Flujo: `search_person` -> ID -> `discover_movies`.

2.  **Vía Vectorial (Datos Abstractos - RAG):**
    *   Si el usuario pregunta *"Peli sobre sueños dentro de sueños"*, el bot usa **Elasticsearch**.
    *   Utiliza **Embeddings Multilingües** (`paraphrase-multilingual-MiniLM-L12-v2`).
    *   Busca similitud semántica en las sinopsis y guiones indexados.

3.  **Búsqueda en Guiones:**
    *   Capacidad de buscar frases exactas o escenas dentro de guiones completos, procesados mediante **Chunking** en Google Colab (GPU) e ingestados en Elastic.

---

## 📊 5. Monitorización y Observabilidad

### Metricbeat (Scope Cluster)
Instalado en la **VM 3**.
*   Configurado con `scope: cluster` y `xpack.enabled: true`.
*   Recoge métricas (CPU, RAM, JVM) de **los 3 nodos** y las envía al clúster.

### Kibana
*   **Stack Monitoring:** Visualización del estado de salud de los 3 nodos y Logstash.
*   **Alertas:** Regla configurada para notificar si la CPU de cualquier nodo supera el 80%.
*   **Dashboards de Negocio:** Visualizaciones de "Géneros más populares" y "Películas por década".

---

## 🛠️ Instrucciones de Instalación

### 1. Clonar Repositorio
```bash
git clone https://github.com/TU_USUARIO/TU_REPO.git
cd TU_REPO
