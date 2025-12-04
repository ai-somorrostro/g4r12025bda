# Infraestructura Big Data y Procesamiento

Este documento detalla la ingeniería de datos, la configuración del clúster distribuido y los pipelines de ingestión.

## 1. Arquitectura del Clúster Distribuido

Se ha desplegado un clúster de **Elasticsearch** sobre **3 Máquinas Virtuales (Linux)** para garantizar Alta Disponibilidad (HA) y tolerancia a fallos (Quórum 2/3).

| Nodo | IP | Roles | Función Principal |
| :--- | :--- | :--- | :--- |
| **VM 1** | `192.199.1.38` | Master, Data, Ingest | Coordinación y Visualización (**Kibana**). |
| **VM 2** | `192.199.1.40` | Master, Data, Ingest | Procesamiento (**Logstash**) y Aplicación. |
| **VM 3** | `192.199.1.54` | Master, Data, Ingest | Monitorización (**Metricbeat**). |

### Configuración de Nodos
*   **Discovery:** Configurado `discovery.seed_hosts` con las 3 IPs para permitir la formación del clúster.
*   **Red:** `network.host` configurado a la IP pública de cada VM.
*   **Seguridad:** `xpack.security` habilitado. Uso de **API Keys** granuladas para sustituir al usuario `elastic`:
    *   *Key Ingesta:* Solo permisos de escritura e índices (`create`, `write`).
    *   *Key Lectura:* Solo permisos de búsqueda (`read`).

## 2. Gestión del Dato (Elasticsearch)

### Modelado (Templates)
Se definió el template `peliculas_csv_template` para estandarizar los índices:
*   **Replicación:** `number_of_replicas: 2`. Garantiza que **cada dato existe en los 3 nodos**.
*   **Mapping:** `dynamic: strict` para evitar la ingestión de campos basura.
*   **Analizadores:** Creación de `analizador_pro` (con filtro `asciifolding`) para búsquedas insensibles a tildes.

### Ciclo de Vida del Dato (ILM)
Se implementó la política `politica_logs_semanal` para los logs de scraping:
1.  **Fase Hot:** Escritura activa.
2.  **Fase Delete:** Borrado automático a los **30 días** para optimizar el almacenamiento en disco.

## 3. Pipelines de Ingesta (ETL con Logstash)

La ingesta se centraliza en la **VM 2** mediante Logstash.

### A. Carga Histórica (CSV)
Pipeline para la ingesta masiva de la base de datos de películas (1980-2024).
*   **Transformaciones:**
    *   `mutate/split`: Convierte cadenas de texto en arrays (Géneros, Actores).
    *   `mutate/remove_field`: Elimina metadatos de sistema (`host`, `event`) para cumplir con el mapping estricto.

### B. Ingesta Continua (Scraping Automatizado)
Sistema para mantener la base de datos actualizada.
1.  **Script Python:** `scraper_semanal.py` calcula dinámicamente la fecha actual y descarga estrenos de los últimos 7 días.
2.  **Orquestación:** **Cron Job** configurado para ejecutar el script cada lunes a las 09:00 AM.
3.  **Pipeline Logstash:** Detecta nuevos archivos CSV y utiliza el plugin **Grok** para validar y parsear la fecha de estreno.
4.  **Indexación:** Utiliza índices dinámicos basados en la fecha: `log-scrapping-%{+YYYY.MM.dd}`.

## 4. Monitorización y Observabilidad

Se implementó una arquitectura de monitorización centralizada desde la **VM 3**.

*   **Metricbeat:** Configurado con `scope: cluster` y el módulo `xpack`. Esto permite que un solo agente recolecte métricas de salud (CPU, JVM Heap, Disco) de los **3 nodos** remotamente.
*   **Visualización (Kibana):**
    *   Habilitación de **Stack Monitoring**.
    *   Creación de Dashboards operativos con gráficos de rendimiento.
*   **Alertas:** Configuración de reglas de umbral para notificar si la CPU de cualquier nodo supera el 80% (requirió generación de claves de encriptación en Kibana).
