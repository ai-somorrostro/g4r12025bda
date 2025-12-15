# Imagen base de Python 3.11 slim
FROM python:3.11-slim

# Directorio de trabajo
WORKDIR /app

# Copiar requirements primero para aprovechar cache
COPY requirements.txt .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar codigo de la API
COPY main.py .

# Exponer puerto 8000
EXPOSE 8000

# Ejecutar servidor uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
