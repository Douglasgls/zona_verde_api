from fastapi import APIRouter, Form, UploadFile, File, HTTPException, Response, BackgroundTasks
from app.uteis import distancia_ponderada, save_image_bytes_as_png, get_plate_text, broadcast_to_websockets
from fastapi import WebSocket
import asyncio
from app.mqtt_client import mqttc 
from app.service.spot import SpotService
from datetime import datetime
from fastapi import HTTPException
from fastapi.responses import FileResponse
import os
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import tempfile
from io import BytesIO

connections = []
executor = ThreadPoolExecutor(max_workers=3)

class SpotStatus(str, Enum):
    LIVRE = "LIVRE"
    OCUPADO = "OCUPADO"
    MANUAL = "MANUAL"

router = APIRouter(
    prefix="/plate",
    tags=["plate"],
    responses={404: {"description": "Not found"}},
)

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connections.append(websocket)
    print(f"Cliente conectado: {websocket.client}")
    try:
        while True:
            await asyncio.sleep(1)
    except Exception as e:
        print(f"Cliente desconectado: {websocket.client}")
    finally:
        if websocket in connections:
            connections.remove(websocket)

async def process_ocr_and_notify(file_content: bytes, spot_id: str, status: SpotStatus):
    """
    Processa a imagem para OCR e notifica os clientes WebSocket.
    """
    loop = asyncio.get_running_loop()

    await loop.run_in_executor(executor, save_image_bytes_as_png, file_content, spot_id)

    plate_detected = ""
    similarity = 0
    expected_plate = "BEE4R2P"

    if status in [SpotStatus.OCUPADO, SpotStatus.MANUAL]:
        print("Iniciando OCR pesado...")
        result = await loop.run_in_executor(executor, get_plate_text, file_content)
        plate_detected = result.get('plate') or ""
        comparison = await loop.run_in_executor(executor, distancia_ponderada, expected_plate, plate_detected)
        similarity = comparison['similaridade_pct']

        print(f"Placa: {plate_detected} | Similaridade: {similarity}%")

        print("-------------------------------")

    payload = {
        "plate_ocr": plate_detected,
        "plate_db": expected_plate,
        "status": status.value,
        "id": spot_id,
        "similarity": similarity,
        "last_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    await broadcast_to_websockets(payload, connections)

@router.post("/validate")
async def validate_plate_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    id: str = Form(...),
    status: str = Form(...)
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Arquivo deve ser uma imagem.")
    
    try:
        current_status = SpotStatus(status.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="Status inválido.")

    await SpotService.update_status(id, current_status.value)

    file_content = await file.read()
    print(f"Tamanho do arquivo recebido: {len(file_content)} bytes")

    background_tasks.add_task(
        process_ocr_and_notify,
        file_content,
        id,
        current_status
    )

    return Response(status_code=202)

@router.post("/take_picture/{spot_id}")
def take_picture(spot_id: str):
    topic = f"camera/{spot_id}"
    mqttc.publish(topic, "picture")
    return {"status": "ok", "message": f"Comando para tirar foto enviado para o tópico {topic}."}

@router.get("/last_picture/{spot_id}")
async def get_last_picture(spot_id: str):
    folder = f"uploads/vaga-{spot_id}"

    if not os.path.isdir(folder):
        raise HTTPException(status_code=404, detail="Pasta não encontrada para este ID.")

    files = [
        f for f in os.listdir(folder)
        if f.lower().endswith((".png", ".jpg", ".jpeg"))
    ]

    if not files:
        raise HTTPException(status_code=404, detail="Nenhuma imagem encontrada para este ID.")
    
    files.sort(key=lambda f: os.path.getmtime(os.path.join(folder, f)), reverse=True)

    last_file = os.path.join(folder, files[0])

    return FileResponse(last_file, media_type="image/png")

@router.get("/last_picture_info/{spot_id}")
async def get_last_picture_info(spot_id: str):
    folder = f"uploads/vaga-{spot_id}"

    if not os.path.isdir(folder):
        raise HTTPException(status_code=404, detail="Pasta não encontrada para este ID.")

    files = [
        f for f in os.listdir(folder)
        if f.lower().endswith((".png", ".jpg", ".jpeg"))
    ]

    if not files:
        raise HTTPException(status_code=404, detail="Nenhuma imagem encontrada para este ID.")
    
    files.sort(key=lambda f: os.path.getmtime(os.path.join(folder, f)), reverse=True)

    last_file = files[0]
    file_path = os.path.join(folder, last_file)

    timestamp = os.path.getmtime(file_path)

    return {
        "image_url": f"/plate/last_picture/{spot_id}",
        "filename": last_file,
        "timestamp": datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    }





# # ///// uteis.py /////


# import re
# import easyocr
# import numpy as np
# from fastapi import UploadFile
# from PIL import Image, UnidentifiedImageError 
# import io
# from datetime import datetime
# import os 
# import cv2
# import asyncio


# def only_letters_numbers(text: str) -> bool:
#     """
#     Verifica se o texto contém apenas letras (A-Z) e números (0-9)
#     """
#     text = text.replace("-", "").replace(" ", "").upper().strip()
#     return bool(re.fullmatch(r'[A-Z0-9]+', text))

# async def get_plate_info(img: np.ndarray) -> dict | None:
#     reader = easyocr.Reader(['pt'], gpu=False, verbose=False)
#     results = reader.readtext(img)

#     best_plate = None
#     best_confidence = 0.0

#     for (bbox, text, confidence) in results:

#         text = text.replace("-", "").replace(" ", "").upper().strip()

#         if len(text) < 6 or text in ["BRASIL", "BR"]:
#             continue
        
#         if text:
#             if not only_letters_numbers(text):
#                 if confidence > best_confidence:
#                     best_confidence = confidence
#                     best_plate = text

#             if best_plate is None:
#                 return {"plate": text, "confidence": confidence}

#     return {"plate": best_plate, "confidence": best_confidence}

# TAMANHO_PLACA = 7
# MAX_PONTUACAO_PERFEITA = 100 

# CONFUSOES_OCR = {
#     "0": ["O", "Q"],
#     "O": ["0", "Q"],
#     "Q": ["O", "0"],
#     "1": ["I", "L"],
#     "I": ["1", "L"],
#     "L": ["I", "1"],
#     "2": ["Z"],
#     "Z": ["2"],
#     "5": ["S"],
#     "S": ["5"],
#     "8": ["B"],
#     "B": ["8"],
#     "6": ["G"],
#     "G": ["6"],
#     "4": ["A"],
#     "A": ["4"]
# }

# def distancia_ponderada(plate_valid: str, plate_ocr: str) -> dict:
#     """
#     Calcula a similaridade ponderada entre duas placas (certa e OCR).
#     Considera erros leves, graves e acertos em sequência.
#     Retorna dicionário com pontuação total, similaridade e detalhes.
#     """

#     if not plate_ocr:
#         print("OCR falhou: Nenhuma placa detectada.")
#         return {
#             "similaridade": 0.0,
#             "similaridade_pct": 0.0,
#             "custo_total": 0,
#             "detalhes": [{"posicao": 0, "esperado": "N/A", "obtido": "N/A", "explicacao": "OCR não retornou texto"}]
#         }
    
#     if len(plate_valid) != TAMANHO_PLACA or len(plate_ocr) != TAMANHO_PLACA:
#          print(f"Tamanho inválido: {len(plate_ocr)} texto obtido do OCR {plate_ocr}")
#          return {
#             "similaridade": 0.0,
#             "similaridade_pct": 0.0,
#             "custo_total": 0,
#             "detalhes": [{"explicacao": f"Tamanho incorreto: {len(plate_ocr)}"}]
#         }

#     custo_total = 70
#     ordemCertaPosAnterior = False
#     detalhes = []

#     print(f"Comparando placas: válida='{plate_valid}' vs OCR='{plate_ocr}'")

#     for i in range(TAMANHO_PLACA):
#         v = plate_valid[i]
#         o = plate_ocr[i]

#         if v == o:
          
#             pontos = 5 if ordemCertaPosAnterior else 0
#             custo_total += pontos
#             detalhes.append({
#                 "posicao": i + 1,
#                 "esperado": v,
#                 "obtido": o,
#                 "explicacao": f"Caractere correto (+{pontos})"
#             })
#             ordemCertaPosAnterior = True

#         elif o in CONFUSOES_OCR.get(v, []):
#             custo_total -= 3
#             detalhes.append({
#                 "posicao": i + 1,
#                 "esperado": v,
#                 "obtido": o,
#                 "explicacao": f"Erro leve: confusão típica OCR ({v}->{o}) (-3)"
#             })
#             ordemCertaPosAnterior = False

#         elif v.isalpha() != o.isalpha():
           
#             custo_total -= 10
#             detalhes.append({
#                 "posicao": i + 1,
#                 "esperado": v,
#                 "obtido": o,
#                 "explicacao": f"Erro grave: tipo incorreto ({'letra' if v.isalpha() else 'número'} → {'número' if o.isdigit() else 'letra'}) (-10)"
#             })
#             ordemCertaPosAnterior = False

#         else:
          
#             custo_total -= 5
#             detalhes.append({
#                 "posicao": i + 1,
#                 "esperado": v,
#                 "obtido": o,
#                 "explicacao": f"Erro leve: caractere errado mas tipo certo ({v}->{o}) (-5)"
#             })
#             ordemCertaPosAnterior = False

#     similarity = max(0.0, min(1.0, custo_total / MAX_PONTUACAO_PERFEITA))
#     similarity_pct = round(similarity * 100, 1)

#     return {
#         "similaridade": similarity,
#         "similaridade_pct": similarity_pct,
#         "custo_total": custo_total,
#         "detalhes": detalhes
#     }

# def save_image_bytes_as_png(file: bytes, spot_id: str) -> str:
#     """
#     Recebe um UploadFile (JPG), converte para PNG e salva na pasta uploads/.
#     Retorna o caminho completo do arquivo salvo.
#     """
#     folder_path = f'uploads/vaga-{spot_id}'
#     os.makedirs(folder_path, exist_ok=True)

#     try:
#         image = Image.open(io.BytesIO(file)).convert("RGB")

#         image = image.rotate(-90, expand=True)

#         timestamp = datetime.now().strftime("%Y%m%d%H%M")
#         filename = f"{spot_id}-{timestamp}.png"
#         filepath = os.path.join(folder_path, filename)

#         image.save(filepath, format="PNG")

#         return filepath

#     except UnidentifiedImageError:
#         raise ValueError("Arquivo de imagem inválido ou corrompido.")
#     except Exception as e:
#         print(f"Erro ao salvar imagem: {e}")
#         raise e


# async def broadcast_to_websockets(message: dict, connections: list):
#     if not connections:
#         return

#     tasks = [connection.send_json(message) for connection in connections]
#     results = await asyncio.gather(*tasks, return_exceptions=True)

#     indices_to_remove = [i for i, res in enumerate(results) if isinstance(res, Exception)]
    
#     for i in reversed(indices_to_remove):
#         connections.pop(i)

# READER = easyocr.Reader(['pt'], gpu=False)

# def get_plate_text(file_bytes: bytes) -> dict:
#     """
#     Lê a imagem do arquivo, aplica técnicas de melhoria e retorna o texto da placa.
#     """
#     try:
#         image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
#         img_np = np.array(image)
#         gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)

#         clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
#         gray = clahe.apply(gray)

#         height, width = gray.shape
#         gray_resized = cv2.resize(gray, (width * 2, height * 2), interpolation=cv2.INTER_LANCZOS4)

#         processed_np = cv2.bilateralFilter(gray_resized, 9, 75, 75)

#         results = READER.readtext(processed_np, detail=1)

#         if not results:
#             return {"plate": None, "confidence": 0}
        
#         best_match = max(results, key=lambda x: x[2])

#         print(f"Placa detectada: {best_match[1]} com confiança {best_match[2]}")

#         return {
#             "plate": best_match[1].upper().replace(" ", ""),
#             "confidence": round(best_match[2], 2)
#         }

#     except Exception as e:
#         print(f"Erro ao processar imagem: {e}")
#         raise e