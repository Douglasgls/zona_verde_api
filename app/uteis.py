import re
import cv2
import numpy as np
import io
import os
import asyncio
import difflib
import easyocr
from PIL import Image
from datetime import datetime
from fastapi.websockets import WebSocket
from app.models.spot import Spot

# ============================================================
# CONFIGURAÇÕES E CONSTANTES
# ============================================================
TAMANHO_PLACA = 7
MAX_PONTUACAO_PERFEITA = 105  # 70 base + (7 posições * 5 pontos de bônus)
BLACKLIST_OCR = ["BRASIL", "MERCOSUL", "MARCOSUL", "MERCOSUR", "PR", "BR"]
REGEX_PLACA = r'[A-Z]{3}[0-9][A-Z0-9][0-9]{2}'

CONFUSOES_OCR = {
    'B': ['8'], '8': ['B'], 'D': ['0', 'O', 'Q'], '0': ['D', 'O', 'Q', 'U'], 
    'O': ['D', '0', 'Q'], 'I': ['1', 'T'], '1': ['I', 'T'], 
    'Z': ['2'], '2': ['Z'], 'S': ['5'], '5': ['S']
}
READER = easyocr.Reader(['pt'], gpu=False, verbose=False)

# ============================================================
# LÓGICA DE COMPARAÇÃO (FUZZY MATCHING)
# ============================================================
def distancia_ponderada(plate_valid: str, plate_ocr: str) -> dict:
    """
    Calcula similaridade entre placas aceitando tamanhos diferentes (difflib).
    """
    v_clean = re.sub(r'[^A-Z0-9]', '', plate_valid.upper())
    o_clean = re.sub(r'[^A-Z0-9]', '', plate_ocr.upper())

    if not o_clean:
        return {"similaridade_pct": 0.0, "custo_total": 0, "status": "OCR_FALHOU"}

    custo_total = 90
    detalhes = []
    sequencia_correta = False
    matcher = difflib.SequenceMatcher(None, v_clean, o_clean)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            for i in range(i1, i2):
                bonus = 5 if sequencia_correta else 0
                custo_total += bonus
                detalhes.append(f"Pos {i+1}: OK (+{bonus})")
                sequencia_correta = True
        elif tag == 'replace':
            for i in range(i1, i2):
                idx_o = j1 + (i - i1)
                if idx_o < j2:
                    v, o = v_clean[i], o_clean[idx_o]
                    if o in CONFUSOES_OCR.get(v, []):
                        custo_total -= 3
                        detalhes.append(f"Pos {i+1}: Confusão {v}->{o} (-3)")
                    elif v.isalpha() != o.isalpha():
                        custo_total -= 10
                        detalhes.append(f"Pos {i+1}: Tipo Errado {v}->{o} (-10)")
                    else:
                        custo_total -= 5
                        detalhes.append(f"Pos {i+1}: Erro {v}->{o} (-5)")
                sequencia_correta = False
        elif tag in ('delete', 'insert'):
            custo_total -= 8
            sequencia_correta = False

    similarity = max(0.0, min(1.0, custo_total / MAX_PONTUACAO_PERFEITA))
    return {
        "similaridade_pct": round(similarity * 100, 1),
        "custo_total": custo_total,
        "detalhes": detalhes
    }

# def calcular_similaridade_placa(placa_correta: str, placa_ocr: str) -> dict:
#     # 1. Padronização: Remove traços/espaços e deixa maiúsculo
#     p_real = re.sub(r'[^A-Z0-9]', '', placa_correta.upper())
#     p_lida = re.sub(r'[^A-Z0-9]', '', placa_ocr.upper())

#     # Mapa de confusões comuns (Sensor leu X, mas era Y)
#     confusoes_ocr = {
#         'B': ['8'], '8': ['B'],
#         'D': ['0', 'O', 'Q'], '0': ['D', 'O', 'Q', 'U'], 'O': ['D', '0', 'Q'],
#         'I': ['1', 'T'], '1': ['I', 'T'],
#         'Z': ['2'], '2': ['Z'],
#         'S': ['5'], '5': ['S']
#     }

#     pontuacao_atual = 70
#     bonus_sequencia = 0
    
#     BONUS_POR_SEQUENCIA = 5  
#     PENALIDADE_ERRO = 10
#     PENALIDADE_CONFUSAO = 3  

#     tamanho_max = max(len(p_real), len(p_lida))
    
#     detalhes = []

#     for i in range(tamanho_max):
#         if i >= len(p_real) or i >= len(p_lida):
#             pontuacao_atual -= PENALIDADE_ERRO
#             bonus_sequencia = 0
#             detalhes.append(f"Pos {i}: Tamanho diferente (-{PENALIDADE_ERRO})")
#             continue

#         char_real = p_real[i]
#         char_lida = p_lida[i]

#         if char_real == char_lida:
#             # ACERTOU
#             bonus_sequencia += BONUS_POR_SEQUENCIA # Aumenta o bônus para a próxima
#             detalhes.append(f"Pos {i}: Igual ({char_real}) -> +{pontos_ganhos}")
        
#         elif char_lida in confusoes_ocr.get(char_real, []):
#             # ERROU, MAS É UMA CONFUSÃO COMUM (Ex: B e 8)
#             pontuacao_atual -= PENALIDADE_CONFUSAO
#             bonus_sequencia = 0 # Quebra o combo
#             detalhes.append(f"Pos {i}: Confusão OCR ({char_real}->{char_lida}) -> -{PENALIDADE_CONFUSAO}")
            
#         else:
#             # ERRO FEIO
#             pontuacao_atual -= PENALIDADE_ERRO
#             bonus_sequencia = 0
#             detalhes.append(f"Pos {i}: Diferente ({char_real}->{char_lida}) -> -{PENALIDADE_ERRO}")

        
#         if pontuacao_atual < 0:
#             pontuacao_atual = 0

#         print(detalhes)

#     return {
#         "placa_ocr": p_lida,
#         "similaridade_pct": pontuacao_atual,
#         "detalhes": detalhes
#     }


MAX_PONTUACAO_PERFEITA = 175

# def calcular_similaridade_placa(placa_db: str, placa_ocr: str) -> dict:
#     PONTUACAO_INICIAL = 90
#     BONUS_SEQUENCIA   = 5
    
#     PENALIDADE_CONFUSAO    = 3  # Ex: B virou 8
#     PENALIDADE_TIPO_ERRADO = 10 # Ex: Letra virou Número
#     PENALIDADE_ERRO_GRAVE  = 5  # Ex: A virou X
#     PENALIDADE_TAMANHO     = 8  # Inserção ou Remoção de caractere

#     # --- 2. Limpeza e Validação Inicial ---
#     placa_real = re.sub(r'[^A-Z0-9]', '', placa_db.upper())
#     placa_lida = re.sub(r'[^A-Z0-9]', '', placa_ocr.upper())

#     if not placa_lida:
#         return {
#             "similaridade_pct": 0.0, 
#             "custo_total": 0, 
#             "status": "OCR_FALHOU",
#             "detalhes": ["Placa lida vazia"]
#         }

#     # --- 3. Inicialização do Comparador ---
#     pontuacao_atual = PONTUACAO_INICIAL
#     detalhes = []
#     em_sequencia_correta = False
    
#     # O SequenceMatcher encontra a melhor forma de alinhar as duas strings
#     comparador = difflib.SequenceMatcher(None, placa_real, placa_lida)

#     # --- 4. Iteração sobre as diferenças (Opcodes) ---
#     # tag: tipo de alteração ('equal', 'replace', 'delete', 'insert')
#     # i1, i2: índices de inicio e fim na placa REAL
#     # j1, j2: índices de inicio e fim na placa LIDA
#     for tag, i1, i2, j1, j2 in comparador.get_opcodes():
        
#         # CASO 1: Trecho Idêntico
#         if tag == 'equal':
#             for i in range(i1, i2):
#                 # Se já vinha acertando, ganha bônus. Se não, ganha 0 (mas ativa a flag para o próximo).
#                 bonus = BONUS_SEQUENCIA if em_sequencia_correta else 0
#                 pontuacao_atual += bonus
                
#                 detalhes.append(f"Pos {i+1}: OK (+{bonus})")
#                 em_sequencia_correta = True

#         # CASO 2: Substituição (Letra errada no lugar da certa)
#         elif tag == 'replace':
#             for i in range(i1, i2):
#                 # Calcula o índice correspondente na placa lida
#                 offset = i - i1
#                 idx_lida = j1 + offset
                
#                 # Proteção de índice
#                 if idx_lida < j2:
#                     char_real = placa_real[i]
#                     char_lida = placa_lida[idx_lida]

#                     # Verificação do tipo de erro
#                     confusoes_conhecidas = CONFUSOES_OCR.get(char_real, [])
                    
#                     if char_lida in confusoes_conhecidas:
#                         pontuacao_atual -= PENALIDADE_CONFUSAO
#                         detalhes.append(f"Pos {i+1}: Confusão {char_real}->{char_lida} (-{PENALIDADE_CONFUSAO})")
                    
#                     elif char_real.isalpha() != char_lida.isalpha():
#                         pontuacao_atual -= PENALIDADE_TIPO_ERRADO
#                         detalhes.append(f"Pos {i+1}: Tipo Errado {char_real}->{char_lida} (-{PENALIDADE_TIPO_ERRADO})")
                    
#                     else:
#                         pontuacao_atual -= PENALIDADE_ERRO_GRAVE
#                         detalhes.append(f"Pos {i+1}: Erro {char_real}->{char_lida} (-{PENALIDADE_ERRO_GRAVE})")
                
#                 # Errou, então quebra o combo de sequência
#                 em_sequencia_correta = False

#         # CASO 3: Tamanho diferente (Inserção ou Remoção)
#         elif tag in ('delete', 'insert'):
#             pontuacao_atual -= PENALIDADE_TAMANHO
#             em_sequencia_correta = False
#             tipo_erro = "Caractere Extra" if tag == 'insert' else "Caractere Faltando"
#             detalhes.append(f"Erro de Tamanho: {tipo_erro} (-{PENALIDADE_TAMANHO})")

#     # --- 5. Cálculo Final ---
#     # Garante que fique entre 0.0 e 1.0
#     proporcao = max(0.0, min(1.0, pontuacao_atual / MAX_PONTUACAO_PERFEITA))
    
#     return {
#         "similaridade_pct": round(proporcao * 100, 1),
#         "custo_total": pontuacao_atual,
#         "detalhes": detalhes
#     }



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
            "confidence": round(best_match[2], 2) if best_match else 0
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
    folder = f'uploads/vaga-{spot_id}'
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
    if not connections: return
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
            "last_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    await websocket.send_json({
        "type": "INITIAL_STATE",
        "data": payload
    })

    print("WebSocket enviado com sucesso.")