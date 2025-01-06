# Use a imagem base do Python
FROM python:3.11.9-slim

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# Copia o arquivo requirements.txt para o diretório de trabalho
COPY requirements.txt .

# Instala as dependências do projeto
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código fonte para o diretório de trabalho
COPY . .

# Comando padrão para executar o aplicativo quando o contêiner for iniciado
CMD ["streamlit", "run", "app/index.py"]
