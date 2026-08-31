import os
import sys
import json
import httpx
import asyncio
import subprocess
import websockets
import logging
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

class PingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        # Suppress logging for high-frequency health checks, register/auto, and stream health pings
        if any(kw in msg for kw in ["agent-card.json", "/tools", "/register/auto", "_stcore/health", "_stcore/stream"]):
            if "GET" in msg or "WebSocket" in msg:
                return False
        return True

logging.getLogger("uvicorn.access").addFilter(PingFilter())

TOOLS_REGISTRY = {
    "mcp_citas": [
        {
            "name": "agendar_turno",
            "description": "Agenda, reserva, consulta y confirma turnos o citas médicas para pacientes en la clínica en el canal #citas. Schedule, book, check, and confirm medical appointments and calendar slots for patients on #citas channel.",
            "inputSchema": {"type": "object", "properties": {"paciente_nombre": {"type": "string"}, "paciente_id": {"type": "string"}, "especialidad": {"type": "string"}, "fecha": {"type": "string"}, "hora": {"type": "string"}}},
            "annotations": {
                "tags": ["citas", "turnos", "agendar", "booking", "schedule", "appointments", "pediatria", "clinica", "oncologia"],
                "examples": [
                    "quiero un turno para pediatria",
                    "agendar turno para Juan Perez",
                    "reservar cita para el proximo lunes",
                    "solicito una cita medica",
                    "confirmar mi turno",
                    "necesito un turno",
                    "I want an appointment",
                    "schedule appointment for Pediatrics",
                    "book a slot for next Monday",
                    "appointment for John Doe",
                    "confirm booking",
                    "check available slots and book appointment"
                ]
            }
        }
    ],
    "mcp_staff": [
        {
            "name": "consultar_directorio",
            "description": "Consulta el directorio médico de la clínica y las especialidades de los doctores. Consults clinic medical directory, specialties, and physician licenses.",
            "inputSchema": {"type": "object", "properties": {"especialidad": {"type": "string"}}},
            "annotations": {
                "tags": ["staff", "directorio", "directory", "doctors", "medicos"],
                "examples": [
                    "consultar medicos en directorio",
                    "show me the medical directory",
                    "buscar doctores por especialidad",
                    "find doctors in General Medicine"
                ]
            }
        },
        {
            "name": "consultar_guardia",
            "description": "Consulta qué médicos están de guardia activa para emergencias y turnos vigentes. Queries active on-call emergency physicians, shifts, and duty schedules.",
            "inputSchema": {"type": "object", "properties": {"especialidad": {"type": "string"}}},
            "annotations": {
                "tags": ["staff", "guardia", "on-call", "emergency", "shifts"],
                "examples": [
                    "quien esta de guardia en Pediatria",
                    "who is on-call for Pediatrics",
                    "medicos de guardia hoy",
                    "active emergency duty staff"
                ]
            }
        }
    ],
    "mcp_ehr": [
        {
            "name": "consultar_historial",
            "description": "Obtiene la historia clínica electrónica e historial médico confidencial del paciente. Fetches confidential electronic health record EHR and clinical medical history for a patient.",
            "inputSchema": {"type": "object", "properties": {"paciente_id": {"type": "string"}}},
            "annotations": {
                "tags": ["historial-medico", "ehr", "medical-history", "records"],
                "examples": [
                    "consultar historial de paciente 101",
                    "fetch medical history for patient 101",
                    "ver ficha medica del paciente",
                    "show clinical records"
                ]
            }
        },
        {
            "name": "guardar_evolucion",
            "description": "Registra una nueva evolución médica o diagnóstico firmado con ticket DET de no repudio. Persists diagnostic medical evolution and notes with non-repudiation SHA-256 hash and DET ticket.",
            "inputSchema": {"type": "object", "properties": {"paciente_id": {"type": "string"}, "diagnostico": {"type": "string"}}},
            "annotations": {
                "tags": ["historial-medico", "evolucion", "medical-evolution", "diagnosis"],
                "examples": [
                    "guardar evolucion diagnostica",
                    "record new clinical evolution",
                    "save patient progress notes",
                    "guardar notas de evolucion"
                ]
            }
        }
    ],
    "mcp_vademecum": [
        {
            "name": "validar_contraindicaciones",
            "description": "Evalúa contraindicaciones farmacológicas, interacciones de medicamentos y seguridad de alergias del paciente. Evaluates pharmacological contraindications, drug-allergy safety, and drug-drug interactions.",
            "inputSchema": {"type": "object", "properties": {"medicamento": {"type": "string"}}},
            "annotations": {
                "tags": ["vademecum", "farmacia", "drugs", "allergies", "safety"],
                "examples": [
                    "validar contraindicaciones de Amoxicilina",
                    "check contraindications for Penicillin",
                    "es seguro recetar este medicamento",
                    "validate drug-drug interactions"
                ]
            }
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


from src.mcp_servers.mcp_citas import agendar_turno
from src.mcp_servers.mcp_staff import consultar_directorio, consultar_guardia
from src.mcp_servers.mcp_ehr import consultar_historial, guardar_evolucion
from src.mcp_servers.mcp_vademecum import validar_contraindicaciones
from src.agents.triage.triage import TriageAgent
from src.agents.pediatria.pediatria import PediatriaAgent
from src.agents.clinica_general.clinica_general import ClinicaGeneralAgent
from src.agents.oncologia.oncologia import OncologiaAgent

TOOL_FUNCTIONS = {
    "agendar_turno": agendar_turno,
    "consultar_turnos": agendar_turno,
    "consultar_directorio": consultar_directorio,
    "consultar_guardia": consultar_guardia,
    "consultar_historial": consultar_historial,
    "guardar_evolucion": guardar_evolucion,
    "validar_contraindicaciones": validar_contraindicaciones
}

AGENTS_INSTANCES = {}


def get_agent_instance(agent_slug: str):
    if agent_slug not in AGENTS_INSTANCES:
        if agent_slug == "triage":
            AGENTS_INSTANCES[agent_slug] = TriageAgent()
        elif agent_slug == "pediatria":
            AGENTS_INSTANCES[agent_slug] = PediatriaAgent()
        elif agent_slug == "clinica-general":
            AGENTS_INSTANCES[agent_slug] = ClinicaGeneralAgent()
        elif agent_slug == "oncologia":
            AGENTS_INSTANCES[agent_slug] = OncologiaAgent()
    return AGENTS_INSTANCES.get(agent_slug)


class MCPDiscoveryMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            path_str = str(request.url.path).strip("/")
            
            # 1. FastMCP Tools Endpoints (GET for discovery, POST for execution)
            if "mcp" in path_str:
                parts = path_str.split("/")
                raw_node = parts[0].replace("-", "_")
                srv_key = raw_node if raw_node.startswith("mcp_") else f"mcp_{raw_node}"
                
                if request.method == "GET":
                    tools = TOOLS_REGISTRY.get(srv_key, TOOLS_REGISTRY.get(raw_node, []))
                    return JSONResponse(content=tools, headers={"Content-Type": "application/json"})
                elif request.method == "POST":
                    body_bytes = await request.body()
                    body_data = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
                    tool_name = body_data.get("tool") or body_data.get("name")
                    tool_args = body_data.get("arguments") or body_data.get("params") or {}
                    
                    func = TOOL_FUNCTIONS.get(tool_name)
                    if func:
                        import inspect
                        sig = inspect.signature(func)
                        valid_args = {k: v for k, v in tool_args.items() if k in sig.parameters}
                        if "det_token" in sig.parameters and "delegated_token" in tool_args and "det_token" not in valid_args:
                            valid_args["det_token"] = tool_args["delegated_token"]
                        res = func(**valid_args)
                        if isinstance(res, str) and res.strip().startswith("{"):
                            try:
                                return JSONResponse(content=json.loads(res))
                            except Exception:
                                pass
                        return JSONResponse(content={"result": res})
                
            # 2. Cognitive Agent Endpoints (GET for Agent Card, POST for JSON-RPC SendMessage)
            if "agent" in path_str:
                for agent_slug, card_data in AGENTS_CARDS.items():
                    if agent_slug in path_str:
                        if request.method == "GET":
                            return JSONResponse(content=card_data, headers={"Content-Type": "application/json"})
                        elif request.method == "POST":
                            body_bytes = await request.body()
                            body_data = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
                            
                            params = body_data.get("params", {})
                            msg_obj = params.get("message", {})
                            query = ""
                            if isinstance(msg_obj, dict):
                                parts = msg_obj.get("parts", [])
                                if parts and isinstance(parts[0], dict):
                                    query = parts[0].get("text", "")
                            elif isinstance(params, dict) and "query" in params:
                                query = params.get("query", "")
                            elif "query" in body_data:
                                query = body_data.get("query", "")
                                
                            agent_inst = get_agent_instance(agent_slug)
                            if agent_inst:
                                res = await agent_inst.run(query)
                                text_out = res.get("response", str(res)) if isinstance(res, dict) else str(res)
                                return JSONResponse(content={
                                    "jsonrpc": "2.0",
                                    "result": {
                                        "message": {
                                            "role": 2,
                                            "parts": [{"text": text_out}]
                                        }
                                    },
                                    "id": body_data.get("id", 1)
                                })
        except Exception as e:
            print(f"[Fleet Server Route Error]: {e}")
            return JSONResponse(
                content={"error": "Fleet Internal Server Error", "detail": str(e)},
                status_code=500
            )
            
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
            "pediatria-agent": (f"{base_url}/agent/pediatria", "#public,#citas,#staff,#historial-medico,#vademecum"),
            "clinica-general-agent": (f"{base_url}/agent/clinica-general", "#public,#citas,#staff,#historial-medico,#vademecum"),
            "oncologia-agent": (f"{base_url}/agent/oncologia", "#public,#citas,#staff,#historial-medico,#vademecum"),
            "triage-agent": (f"{base_url}/agent/triage", "#public,#citas,#staff")
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
    
    # 2. Trigger BFA Gateway registration as background task with retry logic
    async def _do_auto_registration():
        print("[Auto-Register] Waiting for BFA Gateway to be ready...", flush=True)
        await asyncio.sleep(5)
        for attempt in range(10):
            print(f"[Auto-Register] Triggering registration (Attempt {attempt+1}/10)...", flush=True)
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    res = await client.get("http://127.0.0.1:8080/register/auto")
                    res_data = res.json() if res.status_code == 200 else {}
                    has_error = any("error" in str(v) for v in res_data.values()) if res_data else True
                    
                    if res.status_code == 200 and not has_error:
                        print(f"[Auto-Register] Registration completed successfully: {res.text}", flush=True)
                        return
                    else:
                        print(f"[Auto-Register] Attempt {attempt+1}/10 failed: {res.text}. Retrying in 5s...", flush=True)
            except Exception as e:
                print(f"[Auto-Register] Attempt {attempt+1}/10 failed with exception: {e}. Retrying in 5s...", flush=True)
            await asyncio.sleep(5)
        print("[Auto-Register] Failed to complete auto-registration after 10 attempts.", flush=True)

    asyncio.create_task(_do_auto_registration())


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
