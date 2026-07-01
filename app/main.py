"""
openclaw — minimal FastAPI gateway over vLLM
Proxies the OpenAI-compatible API so clients only talk to this container.
"""

import os
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse

VLLM_BASE_URL = os.environ["VLLM_BASE_URL"]   # http://vllm:8000/v1
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8080"))

app = FastAPI(title="openclaw", version="0.1.0")

_client = httpx.AsyncClient(base_url=VLLM_BASE_URL, timeout=300.0)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.api_route("/{path:path}", methods=["GET", "POST", "DELETE", "PUT", "PATCH"])
async def proxy(path: str, request: Request):
    """Transparent proxy to vLLM — supports streaming."""
    url = f"{VLLM_BASE_URL}/{path}"
    body = await request.body()
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length")
    }

    req = _client.build_request(
        method=request.method,
        url=url,
        headers=headers,
        content=body,
        params=dict(request.query_params),
    )
    resp = await _client.send(req, stream=True)

    return StreamingResponse(
        resp.aiter_raw(),
        status_code=resp.status_code,
        headers=dict(resp.headers),
        media_type=resp.headers.get("content-type"),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=APP_HOST, port=APP_PORT, log_level="info")
