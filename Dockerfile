# Usa uma imagem oficial do Python
FROM python:3.10-slim

# Define o diretório de trabalho
WORKDIR /app

# Copia os arquivos do projeto
COPY . .

# Instala dependências
RUN pip install --upgrade pip && \
    pip install flask flask_cors requests beautifulsoup4 gunicorn yfinance ta pandas numpy

# Expõe a porta usada pelo Flask
EXPOSE 8080

# Comando para iniciar o servidor com gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
