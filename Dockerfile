FROM ubuntu:22.04

# Instalar dependências básicas
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Configurar diretório de trabalho
WORKDIR /app

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copiar código fonte
COPY src/ ./src/
COPY main_instaloader_salad.py .

# Criar diretório de logs
RUN mkdir -p logs/bio_collector_instaloader

# Comando padrão
CMD ["python3", "main_instaloader_salad.py"]