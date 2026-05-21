import os
import json
import uvicorn
import requests

from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse

# =========================================================
# CONFIGURACIÓN FASTAPI
# =========================================================

app = FastAPI(title="CineStream App Backend")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZIP (reduce muchísimo el peso del JSON)
app.add_middleware(
    GZipMiddleware,
    minimum_size=1000
)

# =========================================================
# RUTAS JSON
# =========================================================

RUTA_PELICULAS = "peliculas.json"
RUTA_SERIES = "series.json"

# =========================================================
# HOME
# =========================================================

@app.get("/", response_class=HTMLResponse)
def home():

    if not os.path.exists("index.html"):
        return "<h1>❌ No se encontró index.html</h1>"

    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

# =========================================================
# API PELÍCULAS
# =========================================================

@app.get("/api/peliculas")
def get_peliculas():

    if not os.path.exists(RUTA_PELICULAS):
        return []

    try:

        with open(RUTA_PELICULAS, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Error leyendo peliculas.json: {str(e)}"
        )

# =========================================================
# API SERIES
# =========================================================

@app.get("/api/series")
def get_series():

    if not os.path.exists(RUTA_SERIES):
        return []

    try:

        with open(RUTA_SERIES, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Error leyendo series.json: {str(e)}"
        )

# =========================================================
# PROXY STREAM
# =========================================================

@app.get("/stream")
def proxy_stream(
    url: Optional[str] = Query(None),
    range: str = Header(None)
):

    if not url:

        raise HTTPException(
            status_code=400,
            detail="Falta URL"
        )

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
        "Connection": "keep-alive"
    }

    if range:
        headers["Range"] = range

    try:

        with requests.Session() as session:

            req = session.get(
                url,
                headers=headers,
                stream=True,
                timeout=20,
                allow_redirects=True
            )

            content_type = req.headers.get(
                "Content-Type",
                "application/octet-stream"
            )

            response_headers = {
                "Content-Type": content_type,
                "Accept-Ranges": "bytes",
                "Access-Control-Allow-Origin": "*",
            }

            if "Content-Range" in req.headers:
                response_headers["Content-Range"] = req.headers["Content-Range"]

            if "Content-Length" in req.headers:
                response_headers["Content-Length"] = req.headers["Content-Length"]

            def iterar_bloques():

                for chunk in req.iter_content(
                    chunk_size=1024 * 512
                ):

                    if chunk:
                        yield chunk

            return StreamingResponse(
                iterar_bloques(),
                status_code=req.status_code,
                headers=response_headers
            )

    except requests.exceptions.Timeout:

        raise HTTPException(
            status_code=504,
            detail="Timeout del stream"
        )

    except requests.exceptions.RequestException as e:

        raise HTTPException(
            status_code=500,
            detail=f"Error de conexión: {str(e)}"
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# =========================================================
# INICIO SERVIDOR
# =========================================================

if __name__ == "__main__":

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000
    )