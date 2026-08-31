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
    name="agendar_turno",
    description="Agenda, reserva, consulta y confirma turnos o citas médicas para pacientes en la clínica. Schedule, book, check, and confirm medical appointments and calendar slots on #citas channel."
)
def agendar_turno(
    paciente_nombre: str = "Paciente",
    paciente_id: str = "101",
    medico_id: str = "",
    especialidad: str = "Pediatria",
    fecha: str = "2026-09-07",
    hora: str = "18:00",
    det_token: str = "",
    query: str = ""
) -> str:
    # Auto-resolve doctor ID and name from specialty if not supplied
    spec_lower = (especialidad or "").lower()
    if not medico_id:
        if "pediatr" in spec_lower:
            medico_id = "MED-301"
            doctor_name = "Dra. Ana López"
            resolved_spec = "Pediatria"
        elif "oncol" in spec_lower:
            medico_id = "MED-303"
            doctor_name = "Dr. Roberto Rossi"
            resolved_spec = "Oncologia"
        else:
            medico_id = "MED-302"
            doctor_name = "Dr. Carlos Gómez"
            resolved_spec = "Clinica General"
    else:
        doctor_name = "Dr. Asignado"
        resolved_spec = especialidad

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
        "appointment_id": f"TUR-{len(APPOINTMENTS_DB) + 201}",
        "patient_name": paciente_nombre if paciente_nombre else "Paciente",
        "patient_id": paciente_id if paciente_id else "101",
        "doctor_id": medico_id,
        "doctor_name": doctor_name,
        "specialty": resolved_spec,
        "date": fecha if fecha else "2026-09-07",
        "time": hora if hora else "18:00",
        "status": "CONFIRMED"
    }
    APPOINTMENTS_DB.append(new_slot)
    
    return json.dumps({
        "status": "confirmed",
        "channel": "#citas",
        "message": f"Turno agendado y confirmado exitosamente para {new_slot['patient_name']} en {new_slot['specialty']} con {doctor_name} el día {new_slot['date']} a las {new_slot['time']} hs.",
        "booking": new_slot,
        "available_slots": [
            {"specialty": resolved_spec, "doctor_name": doctor_name, "date": new_slot["date"], "time": new_slot["time"], "status": "CONFIRMED"}
        ]
    }, ensure_ascii=False, indent=2)
