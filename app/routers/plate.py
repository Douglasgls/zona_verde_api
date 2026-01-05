from fastapi import APIRouter, Form, UploadFile, File, HTTPException, Response, BackgroundTasks
from app.uteis import distancia_ponderada, save_image_bytes_as_png, get_plate_text, broadcast_to_websockets, send_initial_state
from fastapi import WebSocket
import asyncio
from app.mqtt_client import mqttc 
from app.service.spot import SpotService
from datetime import datetime
from fastapi import HTTPException
from fastapi.responses import FileResponse
import os
from enum import Enum
from app.schemas.spot import SpotUpdate, SpotState, SpotAlertStatus
from concurrent.futures import ThreadPoolExecutor
from app.models.spot import Spot


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

    await send_initial_state(websocket)

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
    expected_plate = await SpotService.get_expected_plate(int(spot_id))

    print(f"Placa esperada para a vaga {spot_id}: {expected_plate}")

    if status in [SpotStatus.OCUPADO, SpotStatus.MANUAL]:
        print("Iniciando OCR pesado...")
        result = await loop.run_in_executor(executor, get_plate_text, file_content)
        plate_detected = result['plate'] or ""
        comparison = await loop.run_in_executor(executor, distancia_ponderada, expected_plate, plate_detected)
        similarity = comparison['similaridade_pct']

        print(f"Placa: {plate_detected} | Similaridade: {similarity}%")

    image_path = f"/plate/last_picture/{spot_id}"

    if similarity < 60 and status in [SpotStatus.OCUPADO, SpotStatus.MANUAL]:
        await SpotService.update(
            spot_id,
            data=SpotUpdate(alert_status=SpotAlertStatus.ACTIVE)
        )
    else:
        await SpotService.update(
            spot_id,
            data=SpotUpdate(alert_status=SpotAlertStatus.NONE)
        )

    payload = {
        "plate_ocr": plate_detected,
        "plate_db": expected_plate,
        "current_status": status.value,
        "id": spot_id,
        "similarity": similarity,
        "image_url": image_path,
        "is_alert": similarity < 70 and status in [SpotStatus.OCUPADO, SpotStatus.MANUAL],
        "last_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    print("Notificando clientes WebSocket...")

    await broadcast_to_websockets(payload, connections)

@router.post("/validate")
async def validate_plate_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    id: str = Form(...),
    status: str = Form(...)
):
    # if not file.content_type.startswith("image/"):
    #     raise HTTPException(status_code=400, detail="Arquivo deve ser uma imagem.")
    
    try:
        current_status = SpotStatus(status.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="Status inválido.")

    await SpotService.update(
        id,
        SpotUpdate(current_status=current_status.value)
    )

    spot = await SpotService.get_by_id(int(id))

    if not spot:
        raise HTTPException(status_code=404, detail="Vaga não encontrada.")

    if spot.status != SpotState.RESERVED:
        await SpotService.update(
            id,
            SpotUpdate(current_status=current_status)
        )

        await broadcast_to_websockets({
            "id": id,
            "current_status": current_status.value,
            "message": "Vaga não reservada, status atualizado sem OCR."
        }, connections)

        return Response(status_code=202)
    

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


@router.post("/ignore_alert/{spot_id}")
async def ignore_alert(spot_id: int):
    spot = await Spot.get_or_none(id=spot_id)
    if spot:
        spot.alert_status = False
        await spot.save()
    
    return {"status": "ok", "alert_status": False}