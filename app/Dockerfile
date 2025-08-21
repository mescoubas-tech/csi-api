FROM python:3.11-slim

# Installer Tesseract OCR et ses dépendances
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Définir dossier de travail
WORKDIR /app

# Copier et installer dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier ton code
COPY . .

# Exposer le port pour Render
EXPOSE 10000

# Lancer l'app FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000"]
