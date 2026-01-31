from fastapi import (
    APIRouter,
    Form,
    UploadFile,
    File,
    HTTPException,
    Response,
    BackgroundTasks,
)
from app.uteis import (
    calcular_similaridade,
    save_image_bytes_as_png,
    get_plate_text,
    broadcast_to_websockets,
    send_initial_state,
)
from fastapi import WebSocket
import asyncio
from app.mqtt_client import mqttc
from app.service.spot import SpotService
from datetime import datetime
from fastapi.responses import FileResponse
import os
from enum import Enum
from app.schemas.spot import SpotUpdate, SpotState, SpotAlertStatus
from concurrent.futures import ThreadPoolExecutor
from app.models.spot import Spot
from app.service.device import DeviceService
from app.models.device import Device
from app.uteis import send_message_to_mqtt


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
    except Exception:
        print(f"Cliente desconectado: {websocket.client}")
    finally:
        if websocket in connections:
            connections.remove(websocket)


async def process_ocr_and_notify(file_content: bytes, spot_id: str, status: SpotStatus):
    """
    Processa a imagem para OCR e notifica os clientes WebSocket.
    """
    loop = asyncio.get_running_loop()

    # Salva a imagem em segundo plano
    await loop.run_in_executor(executor, save_image_bytes_as_png, file_content, spot_id)

    plate_detected = ""
    similarity = 0
    expected_plate = await SpotService.get_expected_plate(int(spot_id)) or ""
    minimum_similarity = 60

    print(f"Placa esperada para a vaga {spot_id}: {expected_plate}")

    if status in [SpotStatus.OCUPADO, SpotStatus.MANUAL]:
        print("Iniciando OCR pesado...")

        result = await loop.run_in_executor(executor, get_plate_text, file_content)
        plate_detected = result.get("plate") or ""
        
        comparison = await loop.run_in_executor(
            executor, calcular_similaridade, expected_plate, plate_detected
        )

        similarity = comparison["similaridade_pct"]


        print(f"Placa: {plate_detected} | Similaridade: {similarity}%")


    image_path = f"/plate/last_picture/{spot_id}"

    is_alert_condition = (
        similarity < minimum_similarity 
        and status in [SpotStatus.OCUPADO, SpotStatus.MANUAL]
        and expected_plate != ""
    )

    alert_status = SpotAlertStatus.ACTIVE if is_alert_condition else SpotAlertStatus.NONE

    await SpotService.update(spot_id, data=SpotUpdate(alert_status=alert_status))

    if is_alert_condition:
        try:
            device: Device = await DeviceService.get_device_by_spot(int(spot_id))
            if device and device.topic_subscribe:
                await send_message_to_mqtt("ALERTA_ON", device.topic_subscribe)
                print(f"MQTT: ALERTA_ON enviado para {device.topic_subscribe}")
        except Exception as e:
            print(f"Erro ao enviar ALERTA_ON via MQTT: {e}")

    # if not is_alert_condition:
    #     try:
    #         device: Device = await DeviceService.get_device_by_spot(int(spot_id))
    #         if device and device.topic_subscribe:
    #             await send_message_to_mqtt("OCUPADO", device.topic_subscribe)
    #             print(f"MQTT: OCUPADO enviado para {device.topic_subscribe}")
    #     except Exception as e:
    #         print(f"Erro ao enviar OCUPADO via MQTT: {e}")

    payload = {
        "plate_ocr": plate_detected,
        "plate_db": expected_plate,
        "current_status": status.value,
        "id": spot_id,
        "similarity": similarity,
        "image_url": image_path,
        "is_alert": is_alert_condition,
        "last_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    print("Notificando clientes WebSocket...")
    await broadcast_to_websockets(payload, connections)


@router.post("/validate")
async def validate_plate_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    onecode: str = Form(...),
    status: str = Form(...),
):
    # if not file.content_type.startswith("image/"):
    #     raise HTTPException(status_code=400, detail="Arquivo deve ser uma imagem.")

    try:
        new_status = SpotStatus(status.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="Status inválido.")
    
    spot = await DeviceService.get_spot_by_onecode(onecode)
    
    if not spot:
        raise HTTPException(status_code=404, detail="Vaga não encontrada.")
    
    

    spot_id = str(spot.id)

    if new_status == SpotStatus.LIVRE:
        try:
            device: Device = await DeviceService.get_device_by_spot(int(spot_id))
            if device and device.topic_subscribe:
                await send_message_to_mqtt("ALERTA_OFF", device.topic_subscribe)
                print(f"MQTT: ALERTA_OFF enviado para {device.topic_subscribe}")
        except Exception as e:
            print(f"Erro ao enviar ALERTA_ON via MQTT: {e}")


    if spot.status != SpotState.RESERVED:
        await SpotService.update(spot_id, SpotUpdate(current_status=new_status.value))

        await broadcast_to_websockets(
            {
                "id": spot_id,
                "current_status": new_status.value,
                "message": "Status atualizado sem validação de reserva.",
            },
            connections,
        )

        return Response(status_code=202)

    await SpotService.update(spot_id, SpotUpdate(current_status=new_status.value))

    file_content = await file.read()
    print(f"Tamanho do arquivo recebido: {len(file_content)} bytes")

    background_tasks.add_task(process_ocr_and_notify, file_content, spot_id, new_status)

    return Response(status_code=202)


@router.post("/take_picture/{onecode}")
async def take_picture(onecode: str):
    device = await DeviceService.get_device_by_onecode(onecode)
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado.")

    topic = device.topic_subscribe
    mqttc.publish(topic, "picture")
    return {
        "status": "ok",
        "message": f"Comando para tirar foto enviado para o tópico {topic}.",
    }

@router.post("/send_mqtt/{onecode}")
async def send_mqtt_message(onecode: str, message: str):
    device = await DeviceService.get_device_by_onecode(onecode)
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado.")

    topic = device.topic_subscribe
    await send_message_to_mqtt(message, topic)
    return {
        "status": "ok",
        "message": f"Mensagem enviada para o tópico {topic}.",
    }


@router.get("/last_picture/{spot_id}")
async def get_last_picture(spot_id: str):
    folder = f"uploads/vaga-{spot_id}"

    if not os.path.isdir(folder):
        raise HTTPException(
            status_code=404, detail="Pasta não encontrada para este ID."
        )

    files = [
        f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg"))
    ]

    if not files:
        raise HTTPException(
            status_code=404, detail="Nenhuma imagem encontrada para este ID."
        )

    files.sort(key=lambda f: os.path.getmtime(os.path.join(folder, f)), reverse=True)

    last_file = os.path.join(folder, files[0])

    return FileResponse(last_file, media_type="image/png")


@router.get("/last_picture_info/{spot_id}")
async def get_last_picture_info(spot_id: str):
    folder = f"uploads/vaga-{spot_id}"

    if not os.path.isdir(folder):
        raise HTTPException(
            status_code=404, detail="Pasta não encontrada para este ID."
        )

    files = [
        f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg"))
    ]

    if not files:
        raise HTTPException(
            status_code=404, detail="Nenhuma imagem encontrada para este ID."
        )

    files.sort(key=lambda f: os.path.getmtime(os.path.join(folder, f)), reverse=True)

    last_file = files[0]
    file_path = os.path.join(folder, last_file)

    timestamp = os.path.getmtime(file_path)

    return {
        "image_url": f"/plate/last_picture/{spot_id}",
        "filename": last_file,
        "timestamp": datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S"),
    }


# @router.post("/ignore_alert/{spot_id}")
# async def ignore_alert(spot_id: int):
#     spot = await Spot.get_or_none(id=spot_id)
#     if spot:
#         spot.alert_status = False
#         await spot.save()

#     return {"status": "ok", "alert_status": False}

@router.post("/ignore_alert/{spot_id}")
async def ignore_alert(spot_id: int):
    spot = await Spot.get_or_none(id=spot_id)
    if spot:
        spot.alert_status = SpotAlertStatus.IGNORED
        await spot.save()
        try:
            device: Device = await DeviceService.get_device_by_spot(spot_id)
            if device and device.topic_subscribe:
                await send_message_to_mqtt("ALERTA_OFF", device.topic_subscribe)
        except Exception as e:
            print(f"Erro ao enviar ALERTA_OFF via MQTT, {device.topic_subscribe}: {e}")
    return {"status": "ok", "alert_status": False}

