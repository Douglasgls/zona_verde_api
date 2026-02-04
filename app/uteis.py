import re
import cv2
import numpy as np
import io
import os
import asyncio
import easyocr
from PIL import Image
from datetime import datetime
from fastapi.websockets import WebSocket
from app.mqtt_client import mqttc as mqtt_client
from app.models.spot import Spot
from typing import Dict, Any
from ultralytics import YOLO
from thefuzz import fuzz

# ============================================================
# CONFIGURAÇÕES E CONSTANTES
# ============================================================

READER = easyocr.Reader(["pt"], gpu=False, verbose=False)
ALLOW_LIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
PLATE_REGEX = re.compile(r"[A-Z]{3}[0-9][A-Z][0-9]{2}")

try:
    MODELO_YOLO = YOLO("license_plate_detector.pt")
except Exception as e:
    print(f"ERRO CRÍTICO: Não foi possível carregar o modelo YOLO. {e}")


# ============================================================
# LÓGICA DE COMPARAÇÃO (SIMILARIDADE DE PLACAS)
# ============================================================
MAPA_AMBIGUIDADE = str.maketrans(
    {"8": "B", "0": "O", "Q": "O", "1": "I", "5": "S", "Z": "2", "P": "2"}
)


def limpar_placa(texto: str) -> str:
    """Remove caracteres especiais e converte para maiúsculo."""
    return re.sub(r"[^A-Z0-9]", "", str(texto).upper())

def normalizar_ocr(texto: str) -> str:
    """
    Substitui caracteres visualmente semelhantes por um padrão comum.
    Ex: Transforma tanto 'B' quanto '8' em 'B' para a comparação não falhar.
    """
    return texto.translate(MAPA_AMBIGUIDADE)

def calcular_similaridade(
    placa_valid: str, placa_ocr: str, limiar_aceite: int = 85
) -> Dict[str, Any]:
    """
    Calcula similaridade usando Levenshtein (thefuzz).
    Retorna um dicionário com estatísticas e decisão.
    """
    v_clean = limpar_placa(placa_valid)
    o_clean = limpar_placa(placa_ocr)

    if not o_clean:
        return {"score": 0, "aprovado": False, "status": "SEM_LEITURA"}

    score_bruto = fuzz.ratio(v_clean, o_clean)

    score_final = score_bruto
    if score_bruto < 100:
        v_norm = normalizar_ocr(v_clean)
        o_norm = normalizar_ocr(o_clean)
        score_norm = fuzz.ratio(v_norm, o_norm)

        score_final = max(score_bruto, score_norm)

    return {
        "similaridade_pct": score_final,
        "aprovado": score_final >= limiar_aceite,
        "detalhes": {
            "entrada_limpa": v_clean,
            "ocr_limpa": o_clean,
            "score_bruto": score_bruto
        },
    }


# ============================================================
# PROCESSAMENTO DE IMAGEM E OCR
# ============================================================
def get_plate_text(file_bytes: bytes) -> dict:
    """
    Aplica recorte estratégico (Topo + Esquerda) para remover 'BRASIL' e 'BR'.
    """
    try:
        os.makedirs("debug", exist_ok=True)
        img_pil = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        img_np = np.array(img_pil)

        results = MODELO_YOLO.predict(img_np, imgsz=640, conf=0.25, verbose=False)

        if not results or len(results[0].boxes) == 0:
            return {"plate": "", "confidence": 0}
        
        box = max(results[0].boxes, key=lambda b: float(b.conf))
        x1, y1, x2, y2 = map(int, box.xyxy[0])

        h_orig, w_orig, _ = img_np.shape
        pad = 10
        crop_bgr = img_np[max(0, y1-pad):min(h_orig, y2+pad), max(0, x1-pad):min(w_orig, x2+pad)]

        h_crop, w_crop, _ = crop_bgr.shape
        
        crop_bgr = crop_bgr[
            int(h_crop * 0.25) : h_crop, 
            int(w_crop * 0.07) : w_crop
        ]

        gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_LANCZOS4)

        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        contrast = clahe.apply(gray)
        blurred = cv2.GaussianBlur(contrast, (5, 5), 0)

        results = READER.readtext(
            blurred,
            detail=1,
            allowlist=ALLOW_LIST,
            paragraph=False,
            text_threshold=0.6,
            low_text=0.4,
            contrast_ths=0.1,
            adjust_contrast=0.8
        )

        if not results:
            return {"plate": "", "confidence": 0}
        
        valid_results = []

        for box, text, conf in results:
            clean_text = text.upper().replace(" ", "")
            
            if clean_text in ["BR", "BRASIL", "MERCOSUL"]:
                continue
            
            if 'PLATE_REGEX' in globals() and PLATE_REGEX.fullmatch(clean_text):
                 valid_results.append((clean_text, conf))
            elif len(clean_text) >= 7: 
                 valid_results.append((clean_text, conf))

        if not valid_results:
            return {"plate": "", "confidence": 0}

        best_text, best_conf = max(valid_results, key=lambda x: x[1])
        
        # Debug
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        cv2.imwrite(f"debug/ocr_processada_{timestamp}.png", blurred)

        return {"plate": best_text, "confidence": float(best_conf)}
    
    except Exception as e:
        print(f"Erro no processamento OCR: {e}")
        return {"plate": "ERRO", "confidence": 0}


# ============================================================
# UTILITÁRIOS DE SISTEMA
# ============================================================
def save_image_bytes_as_png(file: bytes, spot_id: str) -> str:
    """
    Salva a imagem rotacionada em formato PNG.
    """
    folder = f"uploads/vaga-{spot_id}"
    os.makedirs(folder, exist_ok=True)
    try:
        image = Image.open(io.BytesIO(file)).convert("RGB")
        filename = f"{spot_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        path = os.path.join(folder, filename)
        image.save(path, "PNG")
        return path
    except Exception as e:
        print(f"Erro ao salvar: {e}")
        raise

async def broadcast_to_websockets(message: dict, connections: list):
    """
    Notifica clientes via WebSocket em tempo real.
    """
    if not connections:
        return
    print(connections)
    tasks = [conn.send_json(message) for conn in connections]
    await asyncio.gather(*tasks, return_exceptions=True)

async def send_initial_state(websocket: WebSocket):
    spots = await Spot.all()
    payload = {}

    for spot in spots:
        payload = {
            "id": str(spot.id),
            "current_status": spot.current_status.value,
            "alert_status": spot.alert_status.value,
            "last_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    await websocket.send_json({"type": "INITIAL_STATE", "data": payload})

    print("WebSocket enviado com sucesso.")

async def send_message_to_mqtt(message: str,topic: str):
    """
    Envia mensagem para o broker MQTT.
    """
    try:
        if mqtt_client.is_connected():
            topic = topic
            payload = message
            mqtt_client.publish(topic, str(payload))
            print(f"Mensagem MQTT enviada para {topic}: {payload}")
        else:
            print("Cliente MQTT não está conectado.")
    except ImportError:
        print("MQTT Client não está disponível.")