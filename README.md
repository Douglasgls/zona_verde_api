# ESP-PLATE-VISION

API para detecção e validação de placas de veículos no Brasil

O objetivo principal desta API é fornecer uma solução completa de detecção e validação de placas de veículos, incluindo:

- Detecção de placas de veículos
- Validação de placas de veículos
- Gerenciamento de clientes
- Gerenciamento de dispositivos
- Gerenciamento de reservas de vagas de estacionamento

# Requesitos mínimos:
- Python 3.8 ou superior
- FastAPI
- Poetry 
- MySQL
- Mosquitto


# Banco de dados MySQL e Mosquitto

Para executar o programa, é necessário ter um banco de dados MySQL e um servidor Mosquitto rodando em um computador.

# Banco de dados MySQL

```bash
    docker run --name mysql -e MYSQL_ROOT_PASSWORD=root -p 3306:3306 -d mysql
```
# Startando o servidor MySQL

Dentro a pasta core do projeto altere a URL do banco de dados no arquivo database.py

```bash
    docker start #ID do container
```

# Servidor Mosquitto

```bash
    docker run --name mosquitto -p 1883:1883 -d eclipse-mosquitto
```

# Startando o servidor Mosquitto

```bash
    docker start #ID do container
```

# Instalação

```bash
    git clone https://github.com/Douglasgls/esp-plate-vision.git
    cd esp-plate-vision
```

# criando um ambiente virtual e ativando

```bash
    python3 -m venv env

    source env/bin/activate
```

# Instalando as dependências

```bash
    poetry install
    or
    poetry update
```


# Executando a API

```bash
    poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```