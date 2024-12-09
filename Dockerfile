# Usa una imagen base de Python
FROM python:3.9-slim

# Establece el directorio de trabajo
WORKDIR /app

# Instala las dependencias del sistema necesarias para mysqlclient
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copia solo el archivo de requisitos para instalar dependencias primero
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del proyecto al contenedor
COPY . .

# Configura variables de entorno
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=notification_service.settings
ENV GOOGLE_APPLICATION_CREDENTIALS=/app/credenciales/key.json

# Expone el puerto que usará Django
EXPOSE 8000

# Comando para ejecutar Django en producción
CMD ["sh", "-c", "python /app/manage.py migrate && python /app/manage.py runserver 0.0.0.0:8000"]
