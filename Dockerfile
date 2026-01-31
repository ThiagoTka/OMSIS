# Usa uma imagem Python oficial leve
FROM python:3.9-slim

# Define o diretório de trabalho
WORKDIR /app

# Copia os arquivos locais para o container
COPY . .

# Instala as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Define a variável de ambiente para logs imediatos no Cloud Run
ENV PYTHONUNBUFFERED=1

# Comando para iniciar a aplicação usando Gunicorn (servidor de produção)
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app