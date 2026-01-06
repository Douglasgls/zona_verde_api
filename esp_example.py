import paho.mqtt.client as mqtt
import requests
import io
from PIL import Image

BROKER = "localhost"
PORT = 1883
TOPIC = "camera/01"

IMAGENS = ["teste_image.png", "teste_image2.png"]
last_image = None

# --------------------------
# FUNÇÕES
# --------------------------


def enviar_imagem(imagem_path, spot_id, status):
    try:

        img_pil = Image.open(imagem_path).convert("RGB")

        img_pil = img_pil.rotate(-90, expand=True)

        buffer = io.BytesIO()
        img_pil.save(buffer, format="JPEG")
        buffer.seek(0)

        response = requests.post(
            "http://localhost:8000/api/plate/validate/",
            files={"file": ("esp32_simulada.jpg", buffer, "image/jpeg")},
            data={"id": spot_id, "status": status},
        )

        print("Resposta:", response.status_code, response.text)

    except Exception as e:
        print("Erro ao enviar:", e)


def fluxo_manual(imagem_path):
    while True:
        spot_id = input("Digite o ID da vaga: ").strip()
        status = input("Digite o status (EX: MANUAL, OCUPADO, LIVRE): ").strip()

        enviar_imagem(imagem_path, spot_id, status)

        again = input("Deseja enviar novamente? (s/n): ").strip().lower()
        if again != "s":
            break


# --------------------------
# MQTT CALLBACKS
# --------------------------


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Conectado ao MQTT!")
        client.subscribe(TOPIC)
    else:
        print("❌ Erro ao conectar:", rc)


def on_message(client, userdata, msg):
    global last_image

    payload = msg.payload.decode().lower()
    print(f"📩 Mensagem recebida: {payload}")

    if payload != "picture":
        print("Ignorado (não é picture)")
        return

    print("📸 Comando PICTURE recebido!")

    # alterna imagem
    choice_image = IMAGENS[1] if last_image == IMAGENS[0] else IMAGENS[0]
    last_image = choice_image

    print(f"🖼️ Imagem selecionada: {choice_image}")

    modo = input("Modo automático (a) ou manual (m)? ").strip().lower()

    if modo == "a":
        enviar_imagem(imagem_path=choice_image, spot_id="01", status="MANUAL")
    else:
        fluxo_manual(choice_image)


# --------------------------
# MAIN
# --------------------------

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT, 60)
client.loop_forever()
