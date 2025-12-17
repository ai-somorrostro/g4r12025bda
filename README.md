# PARTE 1: Infraestructura Big Data y Procesamiento (Actualizado)

Este documento detalla la ingeniería de datos, la configuración del clúster distribuido, la seguridad y los pipelines de ingestión optimizados.

## 1. Arquitectura del Clúster y Seguridad

Se ha desplegado un clúster de **Elasticsearch** sobre **3 Máquinas Virtuales** con roles compartidos (*Master, Data, Ingest*) para garantizar Alta Disponibilidad.

### Seguridad: Gestión Granular de API Keys
Para cumplir con el principio de mínimo privilegio, se ha eliminado el uso del superusuario `elastic` en los servicios, implementando **IDs y API Keys independientes** para cada componente:

*   **Key `writer_logstash`:** Exclusiva para el pipeline de Logstash. Solo tiene permisos de escritura (`create`, `write`) e indexación sobre `peliculas-csv` y `log-scrapping-*`.
*   **Key `reader_streamlit`:** Exclusiva para la aplicación frontend. Solo tiene permisos de lectura (`read`, `search`) sobre los índices de datos.
*   **Key `writer_scripts`:** Exclusiva para los scripts de Python que cargan vectores, permitiendo la gestión de índices específicos de IA.

## 2. Gestión del Dato (Elasticsearch)

### Modelado y Análisis de Texto
Se ha optimizado el mapeo (`_mapping`) en las plantillas de índice para mejorar la experiencia de búsqueda en español:

*   **Analizador Español (`spanish`):** Aplicado a campos de texto largo como `overview` y `title`.
    *   *Función:* Realiza *stemming* (raíz de las palabras) y eliminación de *stopwords*. Esto permite que una búsqueda de "corriendo" encuentre resultados que contengan "correr", o que "película de acción" funcione aunque el usuario busque "peliculas accion".
*   **Analizador Custom (`analizador_pro`):** Mantenido para nombres propios, aplicando `asciifolding` (ignorar tildes) y `lowercase`.

## 3. Estrategia de Ingesta Unificada (ETL)

Se ha refactorizado el proceso de ingestión para simplificar el mantenimiento y mejorar la calidad de los datos.

### A. Script Maestro (`scraper_master.py`)
En lugar de mantener múltiples scripts dispersos, se ha unificado la lógica de extracción en un solo **Script Maestro**.
*   **Modo Histórico:** Capaz de descargar el catálogo completo desde los años 80.
*   **Modo Semanal (Cron):** Se ejecuta automáticamente para buscar solo las novedades de la última semana (Lunes a Lunes).
*   **Beneficio:** Centraliza la lógica de conexión a la API de TMDb y el manejo de errores en un solo punto.

### B. Pipeline de Logstash y Limpieza de Datos
El pipeline de Logstash se ha robustecido para manejar inconsistencias en los archivos CSV de origen:

*   **Limpieza de Columnas Fantasma:** Se detectó que algunos CSVs generaban columnas erróneas (ej: `column15`) debido a comas dentro de los textos. Se aplicaron filtros `mutate/remove_field` para eliminar estrictamente cualquier columna que no pertenezca al esquema oficial.
*   **Normalización:** Conversión de tipos de datos y separación de arrays (`genre_names`, `cast_names`) antes de la indexación.

## 4. Monitorización y Observabilidad

La monitorización se realiza de forma centralizada desde la **VM 3** mediante Metricbeat con configuración `scope: cluster`.

### Sistema de Alertas (Alerting)
Se ha configurado una regla crítica en Kibana para vigilar la salud de los recursos, priorizando la Memoria RAM sobre la CPU, dado que Elasticsearch es intensivo en memoria Java (JVM).

*   **Regla:** "High RAM Usage Warning".
*   **Condición:** Si el uso de **Memoria RAM** del sistema o la JVM Heap supera el **90%** en cualquiera de los nodos.
*   **Acción:** Registro inmediato en el log del servidor (o índice de alertas) para notificar la necesidad de escalar recursos o revisar Garbage Collection.

---

### Resumen de Mejoras Implementadas

| Área | Estado Anterior | Estado Actual (Mejorado) |
| :--- | :--- | :--- |
| **Ingesta** | Scripts separados dispersos | **`scraper_master.py`** unificado |
| **Calidad de Datos** | Columnas sucias (`column15`) | **Limpieza automática** en Logstash |
| **Búsqueda** | Coincidencia exacta | **Analizador Español** (Semántico/Gramatical) |
| **Seguridad** | Usuario `elastic` genérico | **API Keys independientes** por servicio |
| **Alertas** | CPU > 80% | **RAM > 90%** (Métrica más crítica para Java) |
