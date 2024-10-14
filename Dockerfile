FROM python:3.12

# Atualizar e instalar pacotes necessários
RUN apt-get update && apt-get install -y \
    iputils-ping \
    gnupg wget

# Adicionar a chave GPG do MongoDB (versão bionic)
RUN wget -qO - https://www.mongodb.org/static/pgp/server-4.4.asc | apt-key add -

# Adicionar o repositório MongoDB (usar a versão bionic)
RUN echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu bionic/mongodb-org/4.4 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-4.4.list

# Atualizar pacotes novamente após adicionar o repositório
RUN apt-get update && apt-get install -y \
    mongodb-org-tools

# Copiar e instalar dependências do Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o código do bot
COPY . /app
WORKDIR /app

# Definir comando padrão
CMD ["python", "app.py"]