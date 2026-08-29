import os
import json
from typing import Dict, Any, List
from fastmcp import FastMCP
from src.security.det_validator import verify_det_ticket

mcp = FastMCP("mcp_citas")

# Mock database for appointments
APPOINTMENTS_DB: List[Dict[str, Any]] = [
    {
        "appointment_id": "TUR-101",
        "specialty": "Pediatrics",
        "doctor_id": "MED-301",
        "doctor_name": "Dr. Ana López",
        "date": "2026-08-28",
        "time": "10:00",
        "status": "AVAILABLE"
    },
    {
        "appointment_id": "TUR-102",
        "specialty": "General Medicine",
        "doctor_id": "MED-302",
        "doctor_name": "Dr. Carlos Gómez",
        "date": "2026-08-28",
        "time": "11:30",
        "status": "AVAILABLE"
    },
    {
        "appointment_id": "TUR-103",
        "specialty": "Oncology",
        "doctor_id": "MED-303",
        "doctor_name": "Dr. Roberto Rossi",
        "date": "2026-08-29",
        "time": "14:00",
        "status": "AVAILABLE"
    }
]


@mcp.tool(
    name="consultar_turnos",
    description="Check appointment availability and doctor schedules by medical specialty or date on #citas channel."
)
def consultar_turnos(
    especialidad: str = "All",
    fecha: str = "2026-08-28",
    det_token: str = ""
) -> str:
    params = {"especialidad": especialidad, "fecha": fecha}
    if det_token:
        valid, msg, _ = verify_det_ticket(det_token, expected_channel="#citas", params=params)
        if not valid:
            return f"❌ Access Denied: {msg}"

    matching = [
        t for t in APPOINTMENTS_DB
        if (especialidad.lower() in ["all", "todas"] or especialidad.lower() in t["specialty"].lower())
    ]
    return json.dumps({"status": "success", "channel": "#citas", "available_slots": matching}, ensure_ascii=False, indent=2)


@mcp.tool(
    name="agendar_turno",
    description="Reserves a deterministic medical appointment in the clinic calendar."
)
def agendar_turno(
    paciente_nombre: str,
    paciente_id: str,
    medico_id: str,
    especialidad: str,
    fecha: str,
    hora: str,
    det_token: str = ""
) -> str:
    params = {
        "paciente_nombre": paciente_nombre,
        "paciente_id": paciente_id,
        "medico_id": medico_id,
        "especialidad": especialidad,
        "fecha": fecha,
        "hora": hora
    }
    if det_token:
        valid, msg, _ = verify_det_ticket(det_token, expected_channel="#citas", params=params)
        if not valid:
            return f"❌ Access Denied: {msg}"

    new_slot = {
        "appointment_id": f"TUR-{len(APPOINTMENTS_DB) + 200}",
        "patient_name": paciente_nombre,
        "patient_id": paciente_id,
        "doctor_id": medico_id,
        "specialty": especialidad,
        "date": fecha,
        "time": hora,
        "status": "CONFIRMED"
    }
    APPOINTMENTS_DB.append(new_slot)
    return json.dumps({
        "status": "confirmed",
        "channel": "#citas",
        "message": f"Appointment successfully scheduled for {paciente_nombre} with Doctor {medico_id}.",
        "booking": new_slot
    }, ensure_ascii=False, indent=2)
