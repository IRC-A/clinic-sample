import os
import sys
import json
import httpx
import asyncio
import subprocess
import websockets
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

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

AGENTS_CARDS = {
    "pediatria": {
        "name": "Pediatria Agent",
        "description": "Pediatrics specialist: evaluates symptoms in infants and children (fever, measles, mumps, tonsillitis), provides vaccination guidance, growth and nutrition advice, and urgent-care triage.",
        "version": "1.0.0",
        "skills": [
            {
                "id": "pediatria-agent",
                "name": "Pediatria Agent",
                "description": "Pediatrics specialist: evaluates symptoms in infants and children (fever, measles, mumps, tonsillitis), provides vaccination guidance, growth and nutrition advice, and urgent-care triage.",
                "tags": ["pediatria", "niños", "infantes", "vacunas", "crecimiento"],
                "examples": [
                    "mi bebe tiene fiebre y no come",
                    "¿cuando le toca la proxima vacuna a mi hijo?",
                    "diagnostico para sospecha de sarampion o angina infantil"
                ]
            }
        ]
    },
    "clinica-general": {
        "name": "Clinica General Agent",
        "description": "General medicine specialist: evaluates general symptoms (flu, fever, hypertension, abdominal pain), routine checkups, and triage.",
        "version": "1.0.0",
        "skills": [
            {
                "id": "clinica-general-agent",
                "name": "Clinica General Agent",
                "description": "General medicine specialist: evaluates general symptoms (flu, fever, hypertension, abdominal pain), routine checkups, and triage.",
                "tags": ["clinica", "medicina-general", "gripe", "fiebre", "hipertension"],
                "examples": [
                    "tengo mucha tos y dolor de cabeza",
                    "control de presion arterial para adulto",
                    "tratamiento para estado gripal"
                ]
            }
        ]
    },
    "oncologia": {
        "name": "Oncologia Agent",
        "description": "Oncology specialist: evaluates tumor markers, biopsy reports, carcinoma staging, and specialized oncology consultations.",
        "version": "1.0.0",
        "skills": [
            {
                "id": "oncologia-agent",
                "name": "Oncologia Agent",
                "description": "Oncology specialist: evaluates tumor markers, biopsy reports, carcinoma staging, and specialized oncology consultations.",
                "tags": ["oncologia", "carcinomas", "tumores", "biopsias", "quimioterapia"],
                "examples": [
                    "evaluacion de marcadores tumorales en biopsia",
                    "estadiamiento de carcinoma",
                    "consulta especializada en oncologia"
                ]
            }
        ]
    },
    "triage": {
        "name": "Triage Agent",
        "description": "Patient portal & triage assistant: guides patients, checks physician directory, schedules appointments, and enforces zero-trust channel security.",
        "version": "1.0.0",
        "skills": [
            {
                "id": "triage-agent",
                "name": "Triage Agent",
                "description": "Patient portal & triage assistant: guides patients, checks physician directory, schedules appointments, and enforces zero-trust channel security.",
                "tags": ["triage", "citas", "turnos", "pacientes", "orientacion"],
                "examples": [
                    "quiero agendar un turno con pediatria",
                    "¿quien esta de guardia hoy en la clinica?",
                    "orientacion inicial para paciente"
                ]
            }
        ]
    }
}


class MCPDiscoveryMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            path_str = str(request.url.path).strip("/")
            
            # FastMCP Tools Interceptor
            if "mcp" in path_str:
                parts = path_str.split("/")
                raw_node = parts[0].replace("-", "_")
                srv_key = raw_node if raw_node.startswith("mcp_") else f"mcp_{raw_node}"
                tools = TOOLS_REGISTRY.get(srv_key, TOOLS_REGISTRY.get(raw_node, []))
                return JSONResponse(content=tools, headers={"Content-Type": "application/json"})
                
            # Cognitive Agent Discovery Interceptor
            if "agent" in path_str:
                for agent_slug, card_data in AGENTS_CARDS.items():
                    if agent_slug in path_str:
                        return JSONResponse(content=card_data, headers={"Content-Type": "application/json"})
        except Exception as e:
            print(f"[MCP Middleware Error]: {e}")
            
        return await call_next(request)


app = FastAPI(title="The Fortified Healthcare Fleet — Unified GCP Server")
app.add_middleware(MCPDiscoveryMiddleware)


@app.get("/register/auto")
async def trigger_register():
    from src.config import config
    gateway_url = config.bfa_gateway_url.rstrip("/")
    base_url = os.getenv("HEALTHCARE_APP_URL", "https://fortified-healthcare-fleet-hmwmve5bjq-uc.a.run.app").rstrip("/")
    
    # 1. Register FastMCP Servers
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
                results[f"tool_{srv_name}"] = {"status": res.status_code, "text": res.text}
            except Exception as e:
                results[f"tool_{srv_name}"] = {"status": "error", "message": str(e)}

        # 2. Register Cognitive Specialist Agents
        agent_mapping = {
            "pediatria-agent": (f"{base_url}/agent/pediatria", "#citas,#staff,#historial-medico,#vademecum"),
            "clinica-general-agent": (f"{base_url}/agent/clinica-general", "#citas,#staff,#historial-medico,#vademecum"),
            "oncologia-agent": (f"{base_url}/agent/oncologia", "#citas,#staff,#historial-medico,#vademecum"),
            "triage-agent": (f"{base_url}/agent/triage", "#citas,#staff")
        }

        for agent_id, (agent_url, channels) in agent_mapping.items():
            try:
                res = await client.post(
                    f"{gateway_url}/register/agent",
                    params={
                        "url": agent_url,
                        "channels": channels,
                        "node_id": agent_id
                    },
                    headers={"Authorization": f"Bearer {config.bfa_api_key}"}
                )
                results[f"agent_{agent_id}"] = {"status": res.status_code, "text": res.text}
            except Exception as e:
                results[f"agent_{agent_id}"] = {"status": "error", "message": str(e)}

    return JSONResponse(content=results)


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
        "--server.enableXsrfProtection=false",
        "--browser.gatherUsageStats=false"
    ])
    
    # 2. Wait 3 seconds and trigger BFA Gateway registration
    await asyncio.sleep(3)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.get("http://127.0.0.1:8080/register/auto")
    except Exception:
        pass


@app.websocket("/_stcore/stream")
@app.websocket("/{path:path}")
async def websocket_proxy(websocket: WebSocket, path: str = ""):
    """Bi-directional WebSocket proxying for Streamlit UI real-time session stream."""
    requested_subprotocols = websocket.scope.get("subprotocols", [])
    subprotocol = requested_subprotocols[0] if requested_subprotocols else None
    
    if subprotocol:
        await websocket.accept(subprotocol=subprotocol)
    else:
        await websocket.accept()

    streamlit_ws_url = f"ws://127.0.0.1:{STREAMLIT_PORT}/_stcore/stream"
    if path and path != "_stcore/stream":
        streamlit_ws_url = f"ws://127.0.0.1:{STREAMLIT_PORT}/{path}"
        
    try:
        connect_kwargs = {}
        if requested_subprotocols:
            connect_kwargs["subprotocols"] = requested_subprotocols

        async with websockets.connect(streamlit_ws_url, **connect_kwargs) as target_ws:
            async def forward_client_to_streamlit():
                try:
                    while True:
                        data = await websocket.receive()
                        if data.get("type") == "websocket.disconnect":
                            break
                        if "text" in data and data["text"] is not None:
                            await target_ws.send(data["text"])
                        elif "bytes" in data and data["bytes"] is not None:
                            await target_ws.send(data["bytes"])
                except Exception:
                    pass

            async def forward_streamlit_to_client():
                try:
                    async for message in target_ws:
                        if isinstance(message, str):
                            await websocket.send_text(message)
                        else:
                            await websocket.send_bytes(message)
                except Exception:
                    pass

            task_client = asyncio.create_task(forward_client_to_streamlit())
            task_streamlit = asyncio.create_task(forward_streamlit_to_client())

            done, pending = await asyncio.wait(
                [task_client, task_streamlit],
                return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
    except (WebSocketDisconnect, Exception) as e:
        print(f"[WebSocket Proxy Closed]: {e}")


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
async def proxy_streamlit(request: Request, path: str):
    """Proxies HTTP web requests to Streamlit running on port 8501."""
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
