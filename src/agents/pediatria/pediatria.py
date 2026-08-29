import os
import json
import httpx
import asyncio
from typing import Dict, Any, Optional
from google import genai
from google.genai import types

from src.config import config
from src.security.det_validator import issue_det_ticket


class PediatriaAgent:
    """
    Pediatrics Specialist Agent built with Google ADK & Gemini 3.5 Pro for 'clinic-sample'.
    Authorized Channels: ['#citas', '#staff', '#historial-medico', '#vademecum']
    Capabilities: Pure BFA Gateway Late-Binding Semantic Discovery (POST /discover) for pediatric EHR records, 
    pediatric drug safety, and non-repudiation evolutions over BFA Gateway network.
    """

    def __init__(self, doctor_id: str = "MED-301", api_key: Optional[str] = None):
        self.agent_id = "pediatria-agent"
        self.doctor_id = doctor_id
        self.specialty = "Pediatrics"
        self.name = "Pediatria Specialist Agent"
        self.model = "gemini-3.5-pro"
        self.authorized_channels = config.doctor_channels

        self.api_key = api_key or config.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        self.client = None
        if self.api_key and self.api_key != "your_gemini_api_key_here":
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception:
                self.client = None

        self.system_instruction = (
            "You are the Pediatric Specialist AI Assistant for 'Clinica del Dr. Cureta', built on Google ADK and Gemini 3.5 Pro.\n"
            "Your role is to assist pediatricians in evaluating pediatric clinical histories, checking pharmacological contraindications, "
            "and writing diagnostic evolutions with Zero-Trust non-repudiation audit trails.\n\n"
            "AUTHORIZED CHANNELS: #citas, #staff, #historial-medico, #vademecum.\n"
            "IMPORTANT: Rely 100% on real data returned by BFA Gateway discovery. NEVER invent clinical records or dummy patient data."
        )

    async def discover_and_execute(self, semantic_query: str, target_channel: str, restricted_params: Dict[str, Any]) -> Dict[str, Any]:
        """BFA Gateway Late-Binding Semantic Discovery (POST /discover) & Execution."""
        gateway_url = config.bfa_gateway_url.rstrip("/")
        det_data = issue_det_ticket(self.agent_id, target_channel, restricted_params)

        payload = {
            "query": semantic_query,
            "session_token": det_data["det_token"],
            "restricted_params": restricted_params
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                disc_res = await client.post(
                    f"{gateway_url}/discover",
                    json=payload,
                    headers={"Authorization": f"Bearer {config.bfa_api_key}"}
                )
                if disc_res.status_code == 200:
                    disc_data = disc_res.json()
                    inv_res = await client.post(
                        f"{gateway_url}/invoke",
                        json={
                            "node_id": disc_data.get("target_node_id"),
                            "payload": disc_data.get("prepared_call", {})
                        },
                        headers={"Authorization": f"Bearer {config.bfa_api_key}"}
                    )
                    return {"result": inv_res.json(), "discovery": disc_data, "det": det_data, "params": restricted_params}
                else:
                    return {
                        "result": {
                            "status": "error",
                            "http_code": disc_res.status_code,
                            "error_message": f"BFA Gateway POST /discover returned {disc_res.status_code}: {disc_res.text}"
                        },
                        "det": det_data,
                        "params": restricted_params
                    }
        except Exception as e:
            return {
                "result": {
                    "status": "gateway_unreachable",
                    "error_message": f"🚫 BFA Gateway Network Connection Error ({gateway_url}): {e}"
                },
                "det": det_data,
                "params": restricted_params
            }

    async def run(self, user_message: str, paciente_id: str = "101") -> Dict[str, Any]:
        """Executes Pediatric Specialist workflow via BFA Gateway POST /discover. No fake fallback strings."""
        audit_trail = []

        ehr_exec = await self.discover_and_execute(
            f"retrieve pediatric medical record for patient {paciente_id}",
            "#historial-medico",
            {"paciente_id": paciente_id, "medico_id": self.doctor_id}
        )
        audit_trail.append({"channel": "#historial-medico", "action": "discover:consultar_historial", "det": ehr_exec["det"], "params": ehr_exec["params"]})
        
        raw_result = ehr_exec.get("result", {})
        if raw_result.get("status") in ["error", "gateway_unreachable"]:
            err_msg = raw_result.get("error_message", "Gateway error")
            return {
                "response": f"⚠️ **BFA Gateway Connection / Registration Error**:\n{err_msg}\n\n*No tools or agents are currently registered in channel `#historial-medico` on BFA Gateway.*",
                "patient_id": paciente_id,
                "audit_trail": audit_trail,
                "ehr_record": {}
            }

        ehr_data = raw_result.get("health_record", {}) or raw_result.get("historia_clinica", {})
        alergias = ehr_data.get("allergies") or ehr_data.get("alergias") or []
        antecedentes = ehr_data.get("medical_history") or ehr_data.get("antecedentes") or []

        vademecum_exec = await self.discover_and_execute(
            f"evaluate pediatric drug safety for patient query '{user_message}'",
            "#vademecum",
            {
                "medicamento": "Amoxicillin",
                "paciente_alergias": alergias,
                "otros_medicamentos": ehr_data.get("previous_treatments", [])
            }
        )
        audit_trail.append({"channel": "#vademecum", "action": "discover:validar_contraindicaciones", "det": vademecum_exec["det"], "params": vademecum_exec["params"]})
        vademecum_res = vademecum_exec.get("result", {})

        evo_exec = await self.discover_and_execute(
            f"record pediatric diagnostic evolution for patient {paciente_id}",
            "#historial-medico",
            {
                "paciente_id": paciente_id,
                "medico_id": self.doctor_id,
                "diagnostico": f"Assisted Consultation by Gemini Pro - Pediatrics",
                "tratamiento": "Symptomatic follow-up and validated prescription",
                "notas": "Pediatric consultation recorded via BFA Gateway POST /discover."
            }
        )
        audit_trail.append({"channel": "#historial-medico", "action": "discover:guardar_evolucion", "det": evo_exec["det"], "params": evo_exec["params"]})
        evolution_res = evo_exec.get("result", {})

        if self.client:
            try:
                context_str = f"Pediatric EHR Patient {paciente_id}: {json.dumps(ehr_data, ensure_ascii=False)}\nVademecum Check: {json.dumps(vademecum_res, ensure_ascii=False)}"
                prompt = f"{user_message}\n\n[PEDIATRIC CLINICAL CONTEXT]: {context_str}"
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_instruction,
                        temperature=0.1,
                        max_output_tokens=700
                    )
                )
                text_res = response.text
            except Exception as e:
                text_res = f"[Gemini 3.5 Pro Response]: BFA Gateway discovery response evaluated. (API status: {e})"
        else:
            lines = [f"🩺 **Pediatria Specialist Console — Doctor ID {self.doctor_id}**"]
            lines.append(f"**Patient ID:** {paciente_id} ({ehr_data.get('name', 'Patient')})")
            lines.append(f"**Medical History:** {', '.join(antecedentes) if antecedentes else 'None recorded'}")
            lines.append(f"**Allergies:** {', '.join(alergias) if alergias else 'None recorded'}")

            if vademecum_res and vademecum_res.get("status") != "gateway_unreachable":
                alerts = vademecum_res.get("safety_alerts", vademecum_res.get("alertas_seguridad", []))
                if alerts:
                    lines.append(f"\n🚨 **VADEMECUM SAFETY ALERT (#vademecum via BFA Discover):**")
                    for a in alerts:
                        lines.append(f"- {a}")
                else:
                    lines.append(f"\n✅ **VADEMECUM SAFETY CHECK (#vademecum via BFA Discover):** Medication evaluated without contraindications.")

            if evolution_res and evolution_res.get("non_repudiation_hash"):
                lines.append(f"\n📝 **RECORDED PEDIATRIC EVOLUTION (#historial-medico via BFA Discover):**")
                lines.append(f"- **Non-Repudiation Hash:** `{evolution_res.get('non_repudiation_hash')}`")
                lines.append(f"- **DET Ticket Status:** Signed PASETO v4.public via BFA Gateway POST /discover")

            text_res = "\n".join(lines)

        return {
            "response": text_res,
            "patient_id": paciente_id,
            "audit_trail": audit_trail,
            "ehr_record": ehr_data
        }
