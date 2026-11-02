import json
import os
from typing import Dict, List, Any

# devCt: carga el json de canales de tracking generado a partir del excel
def getTrackingChannelsList() -> List[Dict[str, Any]]:
    jsonPath = os.path.join(os.path.dirname(__file__), "..", "data", "tracking_channels.json")
    if not os.path.exists(jsonPath):
        # fallback si corre desde otra ruta
        jsonPath = os.path.join(os.getcwd(), "src", "data", "tracking_channels.json")
    if not os.path.exists(jsonPath):
        jsonPath = os.path.join(os.getcwd(), "context", "tracking_channels.json")
    
    if os.path.exists(jsonPath):
        with open(jsonPath, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# devCt: retorna diccionario asociativo ceco -> canales_activos para busqueda rapida o(1)
def getTrackingChannelsMap() -> Dict[str, int]:
    records = getTrackingChannelsList()
    return {str(item["ceco"]).strip(): int(item.get("canales_activos", 0)) for item in records}
