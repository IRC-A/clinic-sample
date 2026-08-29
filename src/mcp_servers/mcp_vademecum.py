import os
import json
from typing import Dict, Any, List
from fastmcp import FastMCP
from src.security.det_validator import verify_det_ticket

mcp = FastMCP("mcp_vademecum")

VADEMECUM_DB: List[Dict[str, Any]] = [
    {
        "brand_name": "Amoxidal 500",
        "active_ingredient": "Amoxicillin",
        "drug_family": "Beta-lactam / Penicillins",
        "standard_dosage": "500mg every 8 hours",
        "contraindications": ["Penicillin Allergy", "Severe Renal Impairment"],
        "interactions": ["Methotrexate", "Warfarin"]
    },
    {
        "brand_name": "Ventolin Inhaler",
        "active_ingredient": "Salbutamol",
        "drug_family": "Beta-2 Agonist Bronchodilators",
        "standard_dosage": "100-200mcg as needed",
        "contraindications": ["Salbutamol Hypersensitivity", "Severe Tachyarrhythmias"],
        "interactions": ["Non-selective beta-blockers (Propranolol)"]
    },
    {
        "brand_name": "Ibupirac 600",
        "active_ingredient": "Ibuprofen",
        "drug_family": "NSAIDs",
        "standard_dosage": "400-600mg every 8 hours with meals",
        "contraindications": ["Active Peptic Ulcer", "NSAID Allergy", "Severe Heart Failure"],
        "interactions": ["Aspirin", "Oral Anticoagulants", "Enalapril"]
    },
    {
        "brand_name": "Paracetamol Drops",
        "active_ingredient": "Paracetamol",
        "drug_family": "Analgesic Antipyretics",
        "standard_dosage": "10-15mg/kg per dose in children",
        "contraindications": ["Severe Hepatic Impairment"],
        "interactions": ["Alcohol", "High-dose Warfarin"]
    }
]


@mcp.tool(
    name="buscar_medicamento",
    description="Search drugs, active ingredients, and dosages in pharmacological catalog (#vademecum)."
)
def buscar_medicamento(query: str, det_token: str = "") -> str:
    params = {"query": query}
    if det_token:
        valid, msg, _ = verify_det_ticket(det_token, expected_channel="#vademecum", params=params)
        if not valid:
            return f"❌ Access Denied Zero-Trust (#vademecum): {msg}"

    matches = [
        med for med in VADEMECUM_DB
        if query.lower() in med["brand_name"].lower()
        or query.lower() in med["active_ingredient"].lower()
        or query.lower() in med["drug_family"].lower()
    ]
    return json.dumps({"status": "success", "channel": "#vademecum", "results": matches}, ensure_ascii=False, indent=2)


@mcp.tool(
    name="validar_contraindicaciones",
    description="Evaluate drug interactions and clinical contraindications based on patient medical history."
)
def validar_contraindicaciones(
    medicamento: str,
    paciente_alergias: List[str],
    otros_medicamentos: List[str] = None,
    det_token: str = ""
) -> str:
    if otros_medicamentos is None:
        otros_medicamentos = []

    params = {
        "medicamento": medicamento,
        "paciente_alergias": paciente_alergias,
        "otros_medicamentos": otros_medicamentos
    }
    if det_token:
        valid, msg, _ = verify_det_ticket(det_token, expected_channel="#vademecum", params=params)
        if not valid:
            return f"❌ Access Denied Zero-Trust (#vademecum): {msg}"

    alerts = []
    med_info = None

    for m in VADEMECUM_DB:
        if medicamento.lower() in m["brand_name"].lower() or medicamento.lower() in m["active_ingredient"].lower():
            med_info = m
            break

    if not med_info:
        return json.dumps({"status": "warning", "channel": "#vademecum", "message": f"Medication '{medicamento}' not found in vademecum."}, ensure_ascii=False)

    # Check allergies (e.g., Penicillin allergy vs Amoxicillin)
    for allergy in paciente_alergias:
        if "penicillin" in allergy.lower() or "penicilina" in allergy.lower():
            if "amoxicillin" in med_info["active_ingredient"].lower() or "amoxicilina" in med_info["active_ingredient"].lower() or "penicillin" in med_info["drug_family"].lower():
                alerts.append(f"CRITICAL: Patient has recorded allergy to '{allergy}' and prescribed drug is '{med_info['active_ingredient']}'. CONTRAINDICATED.")

    # Check drug interactions
    for other in otros_medicamentos:
        for inter in med_info["interactions"]:
            if other.lower() in inter.lower():
                alerts.append(f"WARNING: Potential interaction between '{med_info['brand_name']}' and '{other}'.")

    is_safe = len(alerts) == 0

    return json.dumps({
        "status": "success",
        "channel": "#vademecum",
        "evaluated_medication": med_info["brand_name"],
        "is_safe": is_safe,
        "safety_alerts": alerts
    }, ensure_ascii=False, indent=2)
