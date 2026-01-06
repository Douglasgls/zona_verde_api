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
from app.models.spot import Spot
from typing import Dict, Any
from thefuzz import fuzz

# ============================================================
# CONFIGURAÇÕES E CONSTANTES
# ============================================================
TAMANHO_PLACA = 7
MAX_PONTUACAO_PERFEITA = 105  # 70 base + (7 posições * 5 pontos de bônus)
BLACKLIST_OCR = ["BRASIL", "MERCOSUL", "MARCOSUL", "MERCOSUR", "PR", "BR"]
REGEX_PLACA = r"[A-Z]{3}[0-9][A-Z0-9][0-9]{2}"

CONFUSOES_OCR = {
    "B": ["8"],
    "8": ["B"],
    "D": ["0", "O", "Q"],
    "0": ["D", "O", "Q", "U"],
    "O": ["D", "0", "Q"],
    "I": ["1", "T"],
    "1": ["I", "T"],
    "P": ["R"],
    "Z": ["2"],
    "2": ["Z"],
    "S": ["5"],
    "5": ["S"],
}

READER = easyocr.Reader(["pt"], gpu=False, verbose=False)

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

    # 1. Comparação Bruta (Literal)
    score_bruto = fuzz.ratio(v_clean, o_clean)

    # 2. Comparação Flexível (Normalizando confusões comuns de OCR)
    # Se a bruta for baixa, tentamos ver se normalizando melhora (ex: B vs 8)
    score_final = score_bruto
    if score_bruto < 100:
        v_norm = normalizar_ocr(v_clean)
        o_norm = normalizar_ocr(o_clean)
        score_norm = fuzz.ratio(v_norm, o_norm)

        # Usamos o maior score entre o literal e o normalizado
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
    Aplica filtros de imagem e extrai o texto da placa via EasyOCR.
    """
    try:
        os.makedirs("debug", exist_ok=True)

        img_pil = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        img_pil = img_pil.rotate(-90, expand=True)
        img_np = np.array(img_pil)

        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_LANCZOS4)

        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        contrast = clahe.apply(gray)
        blurred = cv2.GaussianBlur(contrast, (5, 5), 0)

        results = READER.readtext(blurred, detail=1)

        best_match = max(results, key=lambda x: x[2])

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        debug_name = f"debug/{timestamp}.png"
        cv2.imwrite(debug_name, blurred)

        return {
            "plate": best_match[1].upper().replace(" ", ""),
            "confidence": round(best_match[2], 2) if best_match else 0,
        }

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
        image = Image.open(io.BytesIO(file)).convert("RGB").rotate(-90, expand=True)
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

    for spot in spots:
        payload = {
            "id": str(spot.id),
            "current_status": spot.current_status.value,
            "alert_status": spot.alert_status.value,
            "last_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    await websocket.send_json({"type": "INITIAL_STATE", "data": payload})

    print("WebSocket enviado com sucesso.")
