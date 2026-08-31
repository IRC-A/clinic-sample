import os
import json
import httpx
import asyncio
from typing import Dict, Any, Optional
from google import genai
from google.genai import types

from bfa_sdk.core.agent import BFAAgent
from src.config import config
from src.security.det_validator import issue_det_ticket


class OncologiaAgent(BFAAgent):
    """
    Oncology Specialist Agent built with Google ADK & Gemini 3.5 Pro for 'clinic-sample'.
    Adheres strictly to the IRC-A (Internet Relay Chat for Agents) Architecture Whitepaper.
    
    IRC-A Core Principle:
    "An intelligent agent should never know the ecosystem it runs in. It should only know
    its own responsibility (oncology, carcinomas, chemotherapy side effects). Discovery is an infrastructure concern."
    """

    def __init__(self, doctor_id: str = "MED-401", url: Optional[str] = None, api_key: Optional[str] = None):
        base_app_url = os.getenv("HEALTHCARE_APP_URL", "https://fortified-healthcare-fleet-hmwmve5bjq-uc.a.run.app").rstrip("/")
        agent_url = url or os.getenv("ONCOLOGIA_PUBLIC_URL", f"{base_app_url}/agent/oncologia")
        gateway_url = config.bfa_gateway_url

        super().__init__(
            agent_id="oncologia-agent",
            name="Oncologia Agent",
            description=(
                "Oncology specialist: evaluates oncology-related symptoms (carcinomas, chemotherapy side-effects, "
                "febrile neutropenia, uncontrolled pain) and provides supportive care recommendations."
            ),
            tags=["oncologia", "cancer", "quimioterapia", "carcinoma"],
            examples=[
                "tengo fiebre despues de la quimioterapia",
                "diagnostico y evaluacion de carcinoma u oncologia",
                "dolor intenso en sitio de tumor"
            ],
            url=agent_url,
            gateway_url=gateway_url
        )

        self.channels = ["#public", "#citas", "#staff", "#historial-medico", "#vademecum"]

        self.doctor_id = doctor_id
        self.specialty = "Oncology"
        self.model = "gemini-3.6-flash"

        self.api_key = api_key or config.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        self.client = None
        if self.api_key and self.api_key != "your_gemini_api_key_here":
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception:
                self.client = None

        self.system_instruction = (
            "You are the Oncology Specialist AI Assistant for 'Clinica del Dr. Cureta', built on Google ADK and Gemini 3.5 Pro.\n"
            "You specialize in oncology and carcinomas (chemotherapy toxicity, tumor evaluation, febrile neutropenia).\n"
            "You do NOT possess local databases or hardcoded medical records in your memory.\n"
            "All capability discovery and external data retrieval are performed late-binding over the IRC-A BFA Gateway network.\n"
            "Rely strictly on the BFA Gateway discovery payload and your oncological medical reasoning to provide concise, professional guidance."
        )

    async def discover_and_execute(self, semantic_query: str, target_channel: str, restricted_params: Dict[str, Any]) -> Dict[str, Any]:
        """IRC-A Late-Binding Semantic Discovery (GET /resolve) & Execution via BFA Gateway."""
        gateway_url = (self.gateway_url or config.bfa_gateway_url).rstrip("/")
        det_data = issue_det_ticket(self.agent_id, target_channel, restricted_params)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(
                    f"{gateway_url}/resolve",
                    params={"query": semantic_query},
                    headers={"Authorization": f"Bearer {config.bfa_api_key}"}
                )
                if res.status_code != 200:
                    return {
                        "result": {
                            "status": "error",
                            "http_code": res.status_code,
                            "error_message": f"BFA Gateway /resolve returned {res.status_code}: {res.text}"
                        },
                        "det": det_data,
                        "params": restricted_params
                    }

                resolve_data = res.json()
                best = resolve_data.get("best")
                if not best:
                    return {
                        "result": {
                            "status": "error",
                            "http_code": 404,
                            "error_message": f"No capability found on BFA Gateway matching '{semantic_query}'"
                        },
                        "det": det_data,
                        "params": restricted_params
                    }

                target_data = best.get("data", {})
                target_type = best.get("type", "tool")
                server_url = target_data.get("server_url") or target_data.get("url")

                if target_type == "tool":
                    tool_url = f"{server_url.rstrip('/')}/tools" if not server_url.endswith("/tools") else server_url
                    args = dict(restricted_params)
                    args["det_token"] = det_data["det_token"]
                    inv_res = await client.post(
                        tool_url,
                        json={"tool": best.get("skill"), "arguments": args},
                        headers={"Authorization": f"Bearer {config.bfa_api_key}"}
                    )
                    data_out = inv_res.json() if inv_res.status_code == 200 else {"error": inv_res.text}
                else:
                    inv_res = await client.post(
                        server_url,
                        json={
                            "jsonrpc": "2.0",
                            "method": "SendMessage",
                            "params": {"message": {"role": 1, "parts": [{"text": semantic_query}]}},
                            "id": 1
                        },
                        headers={"Authorization": f"Bearer {config.bfa_api_key}", "x-det": det_data["det_token"]}
                    )
                    data_out = inv_res.json() if inv_res.status_code == 200 else {"error": inv_res.text}

                return {"result": data_out, "discovery": resolve_data, "det": det_data, "params": restricted_params}
        except Exception as e:
            return {
                "result": {
                    "status": "gateway_unreachable",
                    "error_message": f"🚫 BFA Gateway Connection Error ({gateway_url}): {e}"
                },
                "det": det_data,
                "params": restricted_params
            }

    async def _get_llm_completion(self, system_instruction: str, prompt: str) -> str:
        """Resilient non-blocking LLM completion helper with OpenAI primary and Gemini fallback."""
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=openai_key)
                completion = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=700
                )
                if completion.choices and completion.choices[0].message.content:
                    return completion.choices[0].message.content
            except Exception as oe:
                print(f"[{self.agent_id}] OpenAI error: {oe}. Trying Gemini fallback...")

        if self.client:
            try:
                if hasattr(self.client, "aio") and hasattr(self.client.aio, "models"):
                    response = await self.client.aio.models.generate_content(
                        model=self.model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            temperature=0.1,
                            max_output_tokens=700
                        )
                    )
                else:
                    import asyncio
                    response = await asyncio.to_thread(
                        self.client.models.generate_content,
                        model=self.model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            temperature=0.1,
                            max_output_tokens=700
                        )
                    )
                if response and getattr(response, "text", None):
                    return response.text
            except Exception as e:
                print(f"[{self.agent_id}] Gemini error: {e}")

        return f"⚠️ Resiliency Failure: Both OpenAI and Gemini are currently unavailable."

    async def run(self, user_message: str, paciente_id: str = "101", context: Any = None) -> Dict[str, Any]:
        """Pure IRC-A Cognitive Agent Reasoning Loop with Gemini 3.5 Pro."""
        audit_trail = []
        lowered = user_message.lower()

        if any(kw in lowered for kw in ["vademecum", "contraindicacion", "drug", "medicamento", "alergia", "allergy", "quimioterapia", "chemo"]):
            target_channel = "#vademecum"
            semantic_query = "validar contraindicaciones"
        else:
            target_channel = "#historial-medico"
            semantic_query = "consultar historial"

        disc_exec = await self.discover_and_execute(
            semantic_query,
            target_channel,
            {"paciente_id": paciente_id, "medico_id": self.doctor_id, "query": user_message}
        )
        audit_trail.append({"channel": target_channel, "action": f"discover:{target_channel}", "det": disc_exec["det"], "params": disc_exec["params"]})

        bfa_result = disc_exec.get("result", {})

        try:
            prompt = (
                f"Doctor ID: {self.doctor_id} ({self.specialty})\n"
                f"Patient ID: {paciente_id}\n"
                f"Clinical Query / Prompt: '{user_message}'\n\n"
                f"IRC-A BFA Gateway Discovery Payload ({target_channel}):\n{json.dumps(bfa_result, ensure_ascii=False, indent=2)}\n\n"
                "Instruction: Provide clear oncological clinical guidance and answer the prompt based strictly on the IRC-A payload and oncological reasoning."
            )
            text_res = await self._get_llm_completion(self.system_instruction, prompt)
        except Exception as e:
            text_res = f"⚠️ Inference Resiliency Error: {e}\n\n**Raw IRC-A BFA Gateway Discovery Payload ({target_channel}):**\n```json\n{json.dumps(bfa_result, ensure_ascii=False, indent=2)}\n```"

        return {
            "response": text_res,
            "patient_id": paciente_id,
            "audit_trail": audit_trail,
            "ehr_record": bfa_result
        }
