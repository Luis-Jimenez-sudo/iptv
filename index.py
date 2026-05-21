import os
import json
import uvicorn
import requests
import re
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

app = FastAPI(title="CineStream App Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RUTA_JSON = "iptv_data.json"

def estructurar_datos_estilo_netflix():
    if not os.path.exists(RUTA_JSON):
        return {"peliculas": [], "series": []}
    
    try:
        with open(RUTA_JSON, "r", encoding="utf-8") as f:
            datos_raw = json.load(f)
            
        peliculas = datos_raw.get("peliculas", [])
        
        # Agrupar capítulos en carpetas únicas de Series
        series_agrupadas = {}
        for cap in datos_raw.get("series", []):
            nombre_completo = cap.get("nombre", "")
            categoria_serie = cap.get("categoria", "Series")
            logo = cap.get("logo", "")
            url = cap.get("url", "")

            nombre_raiz = nombre_completo
            patrones = [r'\s+S\d+', r'\s+T\d+', r'\s+Temporada', r'\s+Capitulo', r'\s+Capítulo', r'\s+E\d+']
            for pat in patrones:
                match = re.search(pat, nombre_completo, re.IGNORECASE)
                if match:
                    nombre_raiz = nombre_completo[:match.start()].strip()
                    break

            if nombre_raiz not in series_agrupadas:
                series_agrupadas[nombre_raiz] = {
                    "title": nombre_raiz,
                    "categoria": categoria_serie,
                    "logo": logo,
                    "capitulos": []
                }
            
            series_agrupadas[nombre_raiz]["capitulos"].append({
                "titulo_capitulo": nombre_completo,
                "url": url
            })

        for s in series_agrupadas:
            series_agrupadas[s]["capitulos"].sort(key=lambda x: x["titulo_capitulo"])

        return {
            "peliculas": peliculas,
            "series": list(series_agrupadas.values())
        }

    except Exception as e:
        print(f"❌ Error estructurando el JSON: {e}")
        return {"peliculas": [], "series": []}

VISTA_NETFLIX = estructurar_datos_estilo_netflix()
print(f"🍿 Catálogo preparado: {len(VISTA_NETFLIX['peliculas'])} Películas y {len(VISTA_NETFLIX['series'])} Series listas.")

@app.get("/")
def home():
    return FileResponse("index.html")

@app.get("/api/peliculas")
def get_peliculas():
    return VISTA_NETFLIX["peliculas"]

@app.get("/api/series")
def get_series():
    return VISTA_NETFLIX["series"]

@app.get("/stream")
def proxy_stream(url: Optional[str] = Query(None), range: str = Header(None)):
    if not url:
        raise HTTPException(status_code=400, detail="Falta la URL")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "*/*",
        "Connection": "keep-alive"
    }
    if range:
        headers["Range"] = range

    try:
        session = requests.Session()
        req = session.get(url, headers=headers, stream=True, timeout=15, verify=False, allow_redirects=True)
        
        response_headers = {
            "Content-Type": "video/mp4",
            "Accept-Ranges": "bytes",
            "Access-Control-Allow-Origin": "*",
        }
        if "Content-Range" in req.headers:
            response_headers["Content-Range"] = req.headers["Content-Range"]
        if "Content-Length" in req.headers:
            response_headers["Content-Length"] = req.headers["Content-Length"]

        def iterar_bloques():
            for chunk in req.iter_content(chunk_size=128 * 1024):
                if chunk:
                    yield chunk

        return StreamingResponse(iterar_bloques(), status_code=req.status_code, headers=response_headers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)