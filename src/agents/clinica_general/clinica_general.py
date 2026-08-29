import os
import json
import httpx
import asyncio
from typing import Dict, Any, Optional
from google import genai
from google.genai import types

from src.config import config
from src.security.det_validator import issue_det_ticket


class ClinicaGeneralAgent:
    """
    General Medicine Specialist Agent built with Google ADK & Gemini 3.5 Pro for 'clinic-sample'.
    Authorized Channels: ['#citas', '#staff', '#historial-medico', '#vademecum']
    Capabilities: Pure BFA Gateway Late-Binding Semantic Discovery (POST /discover) for general practice EHR records, 
    drug safety, and non-repudiation evolutions over BFA Gateway network.
    """

    def __init__(self, doctor_id: str = "MED-201", api_key: Optional[str] = None):
        self.agent_id = "clinica-general-agent"
        self.doctor_id = doctor_id
        self.specialty = "Clinica General"
        self.name = "Clinica General Specialist Agent"
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
            "You are the General Medicine Specialist AI Assistant for 'Clinica del Dr. Cureta', built on Google ADK and Gemini 3.5 Pro.\n"
            "Your role is to assist primary care doctors in evaluating adult clinical histories, checking contraindications, "
            "and writing diagnostic evolutions with Zero-Trust non-repudiation audit trails.\n\n"
            "AUTHORIZED CHANNELS: #citas, #staff, #historial-medico, #vademecum.\n"
            "IMPORTANT: Rely 100% on dynamic user input and real data returned by BFA Gateway discovery. NEVER use hardcoded mock strings."
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
        """100% Dynamic Agent Execution with Gemini 3.5 Pro."""
        audit_trail = []

        lowered = user_message.lower()
        if any(kw in lowered for kw in ["vademecum", "contraindicacion", "drug", "medicamento", "alergia", "allergy", "prescribe", "receta"]):
            target_channel = "#vademecum"
        else:
            target_channel = "#historial-medico"

        disc_exec = await self.discover_and_execute(
            user_message,
            target_channel,
            {"paciente_id": paciente_id, "medico_id": self.doctor_id, "query": user_message}
        )
        audit_trail.append({"channel": target_channel, "action": f"discover:{target_channel}", "det": disc_exec["det"], "params": disc_exec["params"]})

        bfa_result = disc_exec.get("result", {})

        if self.client:
            try:
                prompt = (
                    f"Doctor ID: {self.doctor_id} ({self.specialty})\n"
                    f"Patient ID: {paciente_id}\n"
                    f"User Prompt: '{user_message}'\n\n"
                    f"BFA Gateway Discovery Data ({target_channel}): {json.dumps(bfa_result, ensure_ascii=False)}"
                )
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
                text_res = f"🩺 **Clinica General Specialist Console ({self.specialty})**\nPatient ID: {paciente_id}\nPrompt: '{user_message}'\nBFA Gateway Response: {json.dumps(bfa_result, ensure_ascii=False)}"
        else:
            text_res = f"🩺 **Clinica General Specialist Console ({self.specialty})**\nDoctor ID: {self.doctor_id} | Patient ID: {paciente_id}\nPrompt: '{user_message}'\nBFA Gateway Data: {json.dumps(bfa_result, ensure_ascii=False)}"

        return {
            "response": text_res,
            "patient_id": paciente_id,
            "audit_trail": audit_trail,
            "ehr_record": bfa_result
        }
