# Usa uma imagem oficial do Python
FROM python:3.11-slim

# Define diretório de trabalho
WORKDIR /app

# Copia os arquivos
COPY . /app

# Instala dependências
RUN pip install --upgrade pip && pip install -r requirements.txt

# Exponha a porta usada pelo Flask (Render usará a porta passada via env)
EXPOSE 8080

# Comando de inicialização
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
