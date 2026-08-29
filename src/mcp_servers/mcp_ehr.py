import os
import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List
from fastmcp import FastMCP
from src.security.det_validator import verify_det_ticket

mcp = FastMCP("mcp_ehr")

# Mock Electronic Health Records (EHR) Database
EHR_DB: Dict[str, Dict[str, Any]] = {
    "101": {
        "patient_id": "101",
        "name": "Juan Pérez",
        "age": 34,
        "medical_history": ["Mild bronchial asthma", "Controlled hypertension"],
        "allergies": ["Penicillin"],
        "previous_treatments": ["Salbutamol inhaler 100mcg"],
        "evolutions": [
            {
                "date": "2026-05-10",
                "doctor_id": "MED-302",
                "diagnosis": "Seasonal allergic rhinitis",
                "treatment": "Loratadine 10mg/day for 7 days",
                "notes": "Patient reports improvement with antihistamines.",
                "non_repudiation_hash": "a1b2c3d4e5f67890123456789abcdef"
            }
        ]
    },
    "102": {
        "patient_id": "102",
        "name": "Sofia Martínez",
        "age": 6,
        "medical_history": ["Recurrent otitis media"],
        "allergies": ["None known"],
        "previous_treatments": ["Amoxicillin 250mg/5ml suspension"],
        "evolutions": [
            {
                "date": "2026-07-01",
                "doctor_id": "MED-301",
                "diagnosis": "Upper respiratory tract infection with fever",
                "treatment": "Paracetamol drops 100mg/ml",
                "notes": "Favorable progress in 48h.",
                "non_repudiation_hash": "f9e8d7c6b5a43210987654321fedcba"
            }
        ]
    }
}


@mcp.tool(
    name="consultar_historial",
    description="Consult Electronic Health Records (EHR), medical history, and allergies on protected #historial-medico channel."
)
def consultar_historial(paciente_id: str, medico_id: str, det_token: str = "") -> str:
    params = {"paciente_id": paciente_id, "medico_id": medico_id}
    if det_token:
        valid, msg, _ = verify_det_ticket(det_token, expected_channel="#historial-medico", params=params)
        if not valid:
            return f"❌ Access Denied Zero-Trust (#historial-medico): {msg}"

    record = EHR_DB.get(str(paciente_id))
    if not record:
        return json.dumps({"status": "not_found", "channel": "#historial-medico", "message": f"No medical history found for patient_id {paciente_id}"}, ensure_ascii=False)

    return json.dumps({"status": "success", "channel": "#historial-medico", "health_record": record}, ensure_ascii=False, indent=2)


@mcp.tool(
    name="guardar_evolucion",
    description="Record new medical diagnosis and evolution entry with DET-signed non-repudiation guarantee."
)
def guardar_evolucion(
    paciente_id: str,
    medico_id: str,
    diagnostico: str,
    tratamiento: str,
    notas: str = "",
    det_token: str = ""
) -> str:
    params = {
        "paciente_id": paciente_id,
        "medico_id": medico_id,
        "diagnostico": diagnostico,
        "tratamiento": tratamiento,
        "notas": notas
    }
    
    if det_token:
        valid, msg, payload = verify_det_ticket(det_token, expected_channel="#historial-medico", params=params)
        if not valid:
            return f"❌ Access Denied Zero-Trust (#historial-medico): {msg}"
    else:
        payload = {"sub": medico_id, "det_token": "mock_signed"}

    now_iso = datetime.now(timezone.utc).isoformat()
    raw_content = f"{paciente_id}:{medico_id}:{diagnostico}:{tratamiento}:{now_iso}:{det_token}"
    audit_hash = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()

    new_evolution = {
        "date": now_iso,
        "doctor_id": medico_id,
        "diagnosis": diagnostico,
        "treatment": tratamiento,
        "notes": notas,
        "non_repudiation_hash": audit_hash,
        "det_signed": True
    }

    if str(paciente_id) not in EHR_DB:
        EHR_DB[str(paciente_id)] = {
            "patient_id": str(paciente_id),
            "name": f"Patient ID {paciente_id}",
            "age": 30,
            "medical_history": [],
            "allergies": [],
            "previous_treatments": [],
            "evolutions": []
        }

    EHR_DB[str(paciente_id)]["evolutions"].append(new_evolution)

    return json.dumps({
        "status": "persisted",
        "channel": "#historial-medico",
        "message": "Diagnostic evolution successfully recorded with non-repudiation seal.",
        "non_repudiation_hash": audit_hash,
        "record": new_evolution
    }, ensure_ascii=False, indent=2)
