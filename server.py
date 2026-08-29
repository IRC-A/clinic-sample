import os
import sys
import json
import httpx
import asyncio
import subprocess
from fastapi import FastAPI, Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from src.config import config

app = FastAPI(title="The Fortified Healthcare Fleet — Unified GCP Server")

# FastMCP Tool Metadata Registry for BFA Gateway Discovery
TOOLS_REGISTRY = {
    "mcp_citas": [
        {
            "name": "consultar_turnos",
            "description": "Queries available medical appointment slots for clinic specialties.",
            "inputSchema": {"type": "object", "properties": {"especialidad": {"type": "string"}}},
            "annotations": {"tags": ["citas", "turnos"], "examples": ["consultar turnos para Pediatria"]}
        },
        {
            "name": "agendar_turno",
            "description": "Schedules and confirms a medical appointment slot generating a DET booking ticket.",
            "inputSchema": {"type": "object", "properties": {"paciente_id": {"type": "string"}, "fecha": {"type": "string"}}},
            "annotations": {"tags": ["citas", "agendar"], "examples": ["agendar turno para Juan Perez"]}
        }
    ],
    "mcp_staff": [
        {
            "name": "consultar_directorio",
            "description": "Consults clinic medical directory and physician licenses.",
            "inputSchema": {"type": "object", "properties": {"especialidad": {"type": "string"}}},
            "annotations": {"tags": ["staff", "directorio"], "examples": ["consultar medicos en directorio"]}
        },
        {
            "name": "consultar_guardia",
            "description": "Queries active on-call emergency physicians and duty shifts.",
            "inputSchema": {"type": "object", "properties": {"especialidad": {"type": "string"}}},
            "annotations": {"tags": ["staff", "guardia"], "examples": ["quien esta de guardia en Pediatria"]}
        }
    ],
    "mcp_ehr": [
        {
            "name": "consultar_historial",
            "description": "Fetches confidential electronic health record EHR for patient ID.",
            "inputSchema": {"type": "object", "properties": {"paciente_id": {"type": "string"}}},
            "annotations": {"tags": ["historial-medico", "ehr"], "examples": ["consultar historial de paciente 101"]}
        },
        {
            "name": "guardar_evolucion",
            "description": "Persists diagnostic medical evolution with non-repudiation SHA-256 hash and DET PASETO ticket.",
            "inputSchema": {"type": "object", "properties": {"paciente_id": {"type": "string"}, "diagnostico": {"type": "string"}}},
            "annotations": {"tags": ["historial-medico", "evolucion"], "examples": ["guardar evolucion diagnostica"]}
        }
    ],
    "mcp_vademecum": [
        {
            "name": "validar_contraindicaciones",
            "description": "Evaluates pharmacological contraindications, drug-allergy safety, and drug-drug interactions.",
            "inputSchema": {"type": "object", "properties": {"medicamento": {"type": "string"}}},
            "annotations": {"tags": ["vademecum", "farmacia"], "examples": ["validar contraindicaciones de Amoxicilina"]}
        }
    ]
}


@app.get("/mcp_{server_name}/tools")
@app.get("/{server_name}/tools")
def get_tools(server_name: str):
    key = server_name if server_name.startswith("mcp_") else f"mcp_{server_name}"
    tools = TOOLS_REGISTRY.get(key, TOOLS_REGISTRY.get(server_name, []))
    return JSONResponse(content=tools)


@app.post("/mcp_{server_name}/invoke")
@app.post("/{server_name}/invoke")
def invoke_tool(server_name: str, payload: dict):
    return JSONResponse(content={"status": "success", "server": server_name, "data": payload})


@app.get("/register/auto")
async def trigger_register():
    """Trigger background registration of public FastMCP tools with GCP BFA Gateway."""
    gateway_url = config.bfa_gateway_url.rstrip("/")
    base_url = os.getenv("HEALTHCARE_APP_URL", "https://fortified-healthcare-fleet-hmwmve5bjq-uc.a.run.app").rstrip("/")
    
    channel_mapping = {
        "mcp_citas": "#citas",
        "mcp_staff": "#staff",
        "mcp_ehr": "#historial-medico",
        "mcp_vademecum": "#vademecum"
    }
    
    results = {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        for srv_name, channel in channel_mapping.items():
            public_tool_url = f"{base_url}/{srv_name}"
            try:
                res = await client.post(
                    f"{gateway_url}/register/mcp",
                    params={
                        "url": public_tool_url,
                        "channels": channel,
                        "node_id": srv_name
                    },
                    headers={"Authorization": f"Bearer {config.bfa_api_key}"}
                )
                results[srv_name] = {"status": res.status_code, "text": res.text}
            except Exception as e:
                results[srv_name] = {"status": "error", "message": str(e)}

    return JSONResponse(content=results)


# Background Streamlit Proxying
STREAMLIT_PORT = 8501

@app.on_event("startup")
async def startup_event():
    # 1. Start Streamlit on port 8501
    subprocess.Popen([
        sys.executable, "-m", "streamlit", "run", "app.py",
        f"--server.port={STREAMLIT_PORT}",
        "--server.address=0.0.0.0",
        "--server.headless=true",
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false"
    ])
    
    # 2. Wait 3 seconds and trigger BFA Gateway registration
    await asyncio.sleep(3)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.get("http://127.0.0.1:8080/register/auto")
    except Exception:
        pass


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
async def proxy_streamlit(request: Request, path: str):
    """Proxies web requests to Streamlit running on port 8501."""
    if path.startswith("mcp_") or path in ["mcp_citas/tools", "mcp_staff/tools", "mcp_ehr/tools", "mcp_vademecum/tools"]:
        return JSONResponse(content={"error": "Not found"}, status_code=404)

    url = f"http://127.0.0.1:{STREAMLIT_PORT}/{path}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            req_body = await request.body()
            res = await client.request(
                method=request.method,
                url=url,
                headers=dict(request.headers),
                content=req_body,
                params=dict(request.query_params)
            )
            return Response(
                content=res.content,
                status_code=res.status_code,
                headers=dict(res.headers)
            )
        except Exception:
            return Response(content="Service Starting...", status_code=503)


if __name__ == "__main__":
    import uvicorn
    bind_port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=bind_port)
