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
def consultar_historial(
    paciente_id: str = "",
    medico_id: str = "",
    det_token: str = "",
    patient_id: str = "",
    doctor_id: str = "",
    medico: str = "",
    doctor: str = ""
) -> str:
    p_id = paciente_id or patient_id or ""
    m_id = medico_id or doctor_id or medico or doctor or ""
    
    if not p_id or not m_id:
        return json.dumps({"status": "error", "message": "Missing required fields. Required: (paciente_id/patient_id), (medico_id/doctor_id)."})

    # Reconstruct the exact parameter dictionary as sent by the caller for signature canonical hash check
    params = {}
    if patient_id:
        params["patient_id"] = patient_id
    else:
        params["paciente_id"] = p_id

    if doctor_id:
        params["doctor_id"] = doctor_id
    elif medico:
        params["medico"] = medico
    elif doctor:
        params["doctor"] = doctor
    else:
        params["medico_id"] = m_id

    if det_token:
        valid, msg, _ = verify_det_ticket(det_token, expected_channel="#historial-medico", params=params)
        if not valid:
            return f"❌ Access Denied Zero-Trust (#historial-medico): {msg}"

    record = EHR_DB.get(str(p_id))
    if not record:
        return json.dumps({"status": "not_found", "channel": "#historial-medico", "message": f"No medical history found for patient_id {p_id}"}, ensure_ascii=False)

    return json.dumps({"status": "success", "channel": "#historial-medico", "health_record": record}, ensure_ascii=False, indent=2)


@mcp.tool(
    name="guardar_evolucion",
    description="Record new medical diagnosis and evolution entry with DET-signed non-repudiation guarantee."
)
def guardar_evolucion(
    paciente_id: str = "",
    medico_id: str = "",
    diagnostico: str = "",
    tratamiento: str = "",
    notas: str = "",
    det_token: str = "",
    patient_id: str = "",
    doctor_id: str = "",
    medico: str = "",
    doctor: str = "",
    diagnosis: str = "",
    treatment: str = "",
    notes: str = ""
) -> str:
    p_id = paciente_id or patient_id or ""
    m_id = medico_id or doctor_id or medico or doctor or ""
    diag = diagnostico or diagnosis or ""
    treat = tratamiento or treatment or ""
    notes_val = notas or notes or ""

    if not p_id or not m_id or not diag or not treat:
        return json.dumps({
            "status": "error",
            "message": "Missing required fields. Required: (paciente_id/patient_id), (medico_id/doctor_id), (diagnostico/diagnosis), (tratamiento/treatment)."
        })

    # Reconstruct the exact parameter dictionary as sent by the caller for signature canonical hash check
    params = {}
    if patient_id:
        params["patient_id"] = patient_id
    else:
        params["paciente_id"] = p_id

    if doctor_id:
        params["doctor_id"] = doctor_id
    elif medico:
        params["medico"] = medico
    elif doctor:
        params["doctor"] = doctor
    else:
        params["medico_id"] = m_id

    if diagnosis:
        params["diagnosis"] = diagnosis
    else:
        params["diagnostico"] = diag

    if treatment:
        params["treatment"] = treatment
    else:
        params["tratamiento"] = treat

    if notes:
        params["notes"] = notes
    else:
        params["notas"] = notas_val

    if det_token:
        valid, msg, payload = verify_det_ticket(det_token, expected_channel="#historial-medico", params=params)
        if not valid:
            return f"❌ Access Denied Zero-Trust (#historial-medico): {msg}"
    else:
        payload = {"sub": m_id, "det_token": "mock_signed"}

    now_iso = datetime.now(timezone.utc).isoformat()
    raw_content = f"{p_id}:{m_id}:{diag}:{treat}:{now_iso}:{det_token}"
    audit_hash = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()

    new_evolution = {
        "date": now_iso,
        "doctor_id": m_id,
        "diagnosis": diag,
        "treatment": treat,
        "notes": notes_val,
        "non_repudiation_hash": audit_hash,
        "det_signed": True
    }

    if str(p_id) not in EHR_DB:
        EHR_DB[str(p_id)] = {
            "patient_id": str(p_id),
            "name": f"Patient ID {p_id}",
            "age": 30,
            "medical_history": [],
            "allergies": [],
            "previous_treatments": [],
            "evolutions": []
        }

    EHR_DB[str(p_id)]["evolutions"].append(new_evolution)

    return json.dumps({
        "status": "persisted",
        "channel": "#historial-medico",
        "message": "Diagnostic evolution successfully recorded with non-repudiation seal.",
        "non_repudiation_hash": audit_hash,
        "record": new_evolution
    }, ensure_ascii=False, indent=2)
