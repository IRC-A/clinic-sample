import os
import json
from fastapi import FastAPI
from starlette.responses import JSONResponse

app = FastAPI(title="FastMCP Tool Endpoints for BFA Gateway")

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
            "annotations": {"tags": ["staff", "directorio"], "examples": ["consultar meidcos en directorio"]}
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


@app.post("/invoke")
def invoke_tool(payload: dict):
    return JSONResponse(content={"status": "success", "data": payload})
