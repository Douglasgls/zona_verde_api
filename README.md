# Zona Verde API

API responsável pelo backend do ecossistema Zona Verde. O projeto gerencia vagas, reservas, clientes, usuários e dispositivos IoT, além de processar imagens para leitura de placas e integração com MQTT.

## Objetivo

A API centraliza a lógica de negócio do sistema de estacionamento inteligente, oferecendo:

- CRUD de usuários, clientes, vagas, dispositivos e reservas
- Atualização de status de vagas com regras de consistência
- Integração MQTT para notificação de dispositivos ESP
- Endpoints para processamento e validação de placas de veículos
- Suporte a WebSocket para atualização de eventos em tempo real

## Tecnologias principais

- Python 3.12+
- FastAPI
- Tortoise ORM
- MySQL
- MQTT (Mosquitto)
- Ultralytics, EasyOCR, PaddleOCR e Tesseract para OCR/detecção

## Estrutura do projeto

```text
app/
  core/          # configuração do banco
  models/        # entidades do domínio
  routers/       # endpoints HTTP/WebSocket
  schemas/       # contratos de entrada/saída
  service/       # regras de negócio
  assets/        # imagens auxiliares
```

## Pré-requisitos

- Python 3.12 ou superior
- Poetry
- Docker (recomendado para MySQL e Mosquitto)

## Configuração rápida

### 1) Clonar e instalar dependências

```bash
git clone <url-do-repositorio>
cd zona_verde_api
poetry install
```

### 2) Subir MySQL

```bash
docker run --name mysql-zona-verde -e MYSQL_ROOT_PASSWORD=root -p 3306:3306 -d mysql
```

Criar o banco `appdb`:

```bash
docker exec -it mysql-zona-verde mysql -u root -proot -e "CREATE DATABASE appdb;"
```

### 3) Subir broker MQTT

```bash
docker run --name mosquitto-zona-verde -p 1883:1883 -d eclipse-mosquitto
```

### 4) Ajustar conexão com banco

Revise `app/core/database.py` e ajuste a variável `DATABASE_URL` conforme seu ambiente.

### 5) Executar a API

```bash
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Endpoints base

Com a API rodando, a documentação interativa estará disponível em:

- Swagger: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

Os endpoints são expostos sob o prefixo `/api`.

## Projetos complementares

Para uma experiência completa do ecossistema Zona Verde, consulte também:

- zona_verde_app (aplicação cliente)
- zona_verde_esp (firmware/dispositivo embarcado)

## Observações

- O projeto depende de serviços externos (MySQL e MQTT).
- O processamento de imagem/OCR pode exigir bibliotecas nativas no sistema operacional.
- As entidades são criadas automaticamente pelo Tortoise ORM ao iniciar a aplicação.
