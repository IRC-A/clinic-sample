import os
import json
from typing import Dict, Any, List
from fastmcp import FastMCP
from src.security.det_validator import verify_det_ticket

mcp = FastMCP("mcp_staff")

STAFF_DB: List[Dict[str, Any]] = [
    {
        "doctor_id": "MED-301",
        "name": "Dr. Ana López",
        "specialty": "Pediatrics",
        "license_number": "MN-88421",
        "license_status": "ACTIVE",
        "on_call": True,
        "on_call_shift": "24hs"
    },
    {
        "doctor_id": "MED-302",
        "name": "Dr. Carlos Gómez",
        "specialty": "General Medicine",
        "license_number": "MN-45120",
        "license_status": "ACTIVE",
        "on_call": True,
        "on_call_shift": "08:00 - 20:00"
    },
    {
        "doctor_id": "MED-303",
        "name": "Dr. Roberto Rossi",
        "specialty": "Oncology",
        "license_number": "MN-99102",
        "license_status": "ACTIVE",
        "on_call": False,
        "on_call_shift": "N/A"
    }
]


@mcp.tool(
    name="consultar_directorio",
    description="Query medical staff directory and specialties on #staff channel."
)
def consultar_directorio(especialidad: str = "", det_token: str = "") -> str:
    params = {"especialidad": especialidad}
    if det_token:
        valid, msg, _ = verify_det_ticket(det_token, expected_channel="#staff", params=params)
        if not valid:
            return f"❌ Access Denied: {msg}"

    result = [
        m for m in STAFF_DB
        if not especialidad or especialidad.lower() in m["specialty"].lower()
    ]
    return json.dumps({"status": "success", "channel": "#staff", "directory": result}, ensure_ascii=False, indent=2)


@mcp.tool(
    name="validar_matricula",
    description="Validate if a physician's medical license is active and valid."
)
def validar_matricula(medico_id: str, matricula: str, det_token: str = "") -> str:
    params = {"medico_id": medico_id, "matricula": matricula}
    if det_token:
        valid, msg, _ = verify_det_ticket(det_token, expected_channel="#staff", params=params)
        if not valid:
            return f"❌ Access Denied: {msg}"

    for doc in STAFF_DB:
        if doc["doctor_id"] == medico_id or doc["license_number"] == matricula:
            return json.dumps({
                "status": "valid",
                "channel": "#staff",
                "is_valid": doc["license_status"] == "ACTIVE",
                "doctor": doc
            }, ensure_ascii=False, indent=2)

    return json.dumps({"status": "not_found", "channel": "#staff", "is_valid": False}, ensure_ascii=False)


@mcp.tool(
    name="consultar_guardia",
    description="Query directory of active on-call emergency physicians."
)
def consultar_guardia(especialidad: str = "", det_token: str = "") -> str:
    params = {"especialidad": especialidad}
    if det_token:
        valid, msg, _ = verify_det_ticket(det_token, expected_channel="#staff", params=params)
        if not valid:
            return f"❌ Access Denied: {msg}"

    on_call = [
        m for m in STAFF_DB
        if m["on_call"] and (not especialidad or especialidad.lower() in m["specialty"].lower())
    ]
    return json.dumps({"status": "success", "channel": "#staff", "on_call_doctors": on_call}, ensure_ascii=False, indent=2)
