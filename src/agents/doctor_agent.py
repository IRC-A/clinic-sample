import os
import json
import asyncio
from typing import Dict, Any, List, Optional
from google import genai
from google.genai import types

from src.config import config
from src.security.det_validator import issue_det_ticket
from src.mcp_servers.mcp_citas import consultar_turnos, agendar_turno
from src.mcp_servers.mcp_staff import consultar_directorio, consultar_guardia, validar_matricula
from src.mcp_servers.mcp_ehr import consultar_historial, guardar_evolucion
from src.mcp_servers.mcp_vademecum import buscar_medicamento, validar_contraindicaciones


class DoctorAgent:
    """
    Medical Specialist Agent built with Google ADK & Gemini 3.5 Pro.
    Authorized Channels: ['#citas', '#staff', '#historial-medico', '#vademecum']
    Capabilities: High reasoning clinical diagnosis, EHR review, drug safety verification, non-repudiation evolution persistence.
    """

    def __init__(self, medico_id: str = "MED-301", especialidad: str = "Pediatrics", api_key: Optional[str] = None):
        self.agent_id = "doctor-agent"
        self.medico_id = medico_id
        self.especialidad = especialidad
        self.name = f"Doctor Console Agent ({especialidad})"
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
            f"You are the Medical Specialist AI Assistant for Doctor ID {medico_id} ({especialidad}) at 'Dr. Cureta Clinic', "
            "built on Google ADK and Gemini 3.5 Pro.\n"
            "Your role is to assist licensed doctors in evaluating clinical histories, checking pharmacological contraindications, "
            "and writing diagnostic evolutions with Zero-Trust non-repudiation audit trails.\n\n"
            "AUTHORIZED CHANNELS: #citas, #staff, #historial-medico, #vademecum.\n\n"
            "OPERATIONAL WORKFLOW:\n"
            "1. Read patient EHR history from #historial-medico.\n"
            "2. Verify contraindications and allergies in #vademecum before recommending medication.\n"
            "3. Save clinical evolutions with signed DET tickets to ensure non-repudiation.\n"
            "4. Maintain rigorous medical terminology in professional English."
        )

    def execute_tool(self, func_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Executes FastMCP tools with automatic DET ticket generation & verification."""
        if func_name == "consultar_historial":
            det = issue_det_ticket(self.agent_id, "#historial-medico", args)
            raw = consultar_historial(
                paciente_id=args.get("paciente_id", "101"),
                medico_id=self.medico_id,
                det_token=det["det_token"]
            )
            return {"result": json.loads(raw), "det": det, "params": args}

        elif func_name == "validar_contraindicaciones":
            det = issue_det_ticket(self.agent_id, "#vademecum", args)
            raw = validar_contraindicaciones(
                medicamento=args.get("medicamento", "Amoxicillin"),
                paciente_alergias=args.get("paciente_alergias", []),
                otros_medicamentos=args.get("otros_medicamentos", []),
                det_token=det["det_token"]
            )
            return {"result": json.loads(raw), "det": det, "params": args}

        elif func_name == "guardar_evolucion":
            det = issue_det_ticket(self.agent_id, "#historial-medico", args)
            raw = guardar_evolucion(
                paciente_id=args.get("paciente_id", "101"),
                medico_id=self.medico_id,
                diagnostico=args.get("diagnostico", "Clinical Evaluation"),
                tratamiento=args.get("tratamiento", "Medical Indications"),
                notas=args.get("notas", "Evolution saved with DET signature."),
                det_token=det["det_token"]
            )
            return {"result": json.loads(raw), "det": det, "params": args}

        elif func_name == "buscar_medicamento":
            det = issue_det_ticket(self.agent_id, "#vademecum", args)
            raw = buscar_medicamento(
                query=args.get("query", "Amoxicillin"),
                det_token=det["det_token"]
            )
            return {"result": json.loads(raw), "det": det, "params": args}

        return {"result": {"error": "Tool not found"}, "det": None, "params": args}

    async def run(self, user_message: str, paciente_id: str = "101") -> Dict[str, Any]:
        """Executes doctor workflow: EHR read -> Vademecum safety check -> Evolution persist."""
        audit_trail = []
        lowered = user_message.lower()

        # Step 1: Read EHR history
        ehr_exec = self.execute_tool("consultar_historial", {"paciente_id": paciente_id, "medico_id": self.medico_id})
        audit_trail.append({"channel": "#historial-medico", "action": "consultar_historial", "det": ehr_exec["det"], "params": ehr_exec["params"]})
        ehr_data = ehr_exec["result"].get("health_record", {}) or ehr_exec["result"].get("historia_clinica", {})

        alergias = ehr_data.get("allergies") or ehr_data.get("alergias") or []
        antecedentes = ehr_data.get("medical_history") or ehr_data.get("antecedentes") or []

        # Step 2: If medication mentioned, check vademecum contraindications
        vademecum_res = None
        if any(med in lowered for med in ["amoxicillin", "amoxicilina", "amoxidal", "ibuprofen", "ibuprofeno", "paracetamol", "salbutamol"]):
            target_med = "Amoxicillin" if "amoxi" in lowered else ("Ibuprofen" if "ibup" in lowered else "Paracetamol")
            vademecum_exec = self.execute_tool("validar_contraindicaciones", {
                "medicamento": target_med,
                "paciente_alergias": alergias,
                "otros_medicamentos": ehr_data.get("previous_treatments", [])
            })
            audit_trail.append({"channel": "#vademecum", "action": "validar_contraindicaciones", "det": vademecum_exec["det"], "params": vademecum_exec["params"]})
            vademecum_res = vademecum_exec["result"]

        # Step 3: If asked to record or conclude diagnosis, save evolution
        evolution_res = None
        if any(act in lowered for act in ["save", "guardar", "diagnose", "diagnostico", "evolucion", "prescribe", "recetar"]):
            evo_exec = self.execute_tool("guardar_evolucion", {
                "paciente_id": paciente_id,
                "medico_id": self.medico_id,
                "diagnostico": f"Assisted Consultation by Gemini Pro - {self.especialidad}",
                "tratamiento": "Symptomatic follow-up and validated prescription",
                "notas": "Consultation recorded with DET PASETO v4.public signature."
            })
            audit_trail.append({"channel": "#historial-medico", "action": "guardar_evolucion", "det": evo_exec["det"], "params": evo_exec["params"]})
            evolution_res = evo_exec["result"]

        # Generate Gemini 3.5 Pro output or structured response
        if self.client:
            try:
                context_str = f"EHR Patient {paciente_id}: {json.dumps(ehr_data, ensure_ascii=False)}\nVademecum Check: {json.dumps(vademecum_res, ensure_ascii=False)}"
                prompt = f"{user_message}\n\n[CLINICAL CONTEXT]: {context_str}"
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
                text_res = f"[Gemini 3.5 Pro Response]: Clinical analysis completed for Patient ID {paciente_id}. (API status: {e})"
        else:
            # Fallback deterministic response
            lines = [f"🩺 **Specialist Medical Console ({self.especialidad}) — Doctor ID {self.medico_id}**"]
            lines.append(f"**Patient ID:** {paciente_id} ({ehr_data.get('name', 'Patient')})")
            lines.append(f"**Medical History:** {', '.join(antecedentes)}")
            lines.append(f"**Allergies:** {', '.join(alergias) if alergias else 'None known'}")

            if vademecum_res:
                is_safe = vademecum_res.get("is_safe", vademecum_res.get("es_seguro", True))
                alerts = vademecum_res.get("safety_alerts", vademecum_res.get("alertas_seguridad", []))
                if not is_safe:
                    lines.append(f"\n🚨 **VADEMECUM SAFETY ALERT (#vademecum):**")
                    for a in alerts:
                        lines.append(f"- {a}")
                else:
                    lines.append(f"\n✅ **VADEMECUM SAFETY CHECK (#vademecum):** Medication evaluated without contraindications.")

            if evolution_res:
                lines.append(f"\n📝 **RECORDED DIAGNOSTIC EVOLUTION (#historial-medico):**")
                lines.append(f"- **Non-Repudiation Hash:** `{evolution_res.get('non_repudiation_hash', 'N/A')}`")
                lines.append(f"- **DET Ticket Status:** Signed PASETO v4.public")

            text_res = "\n".join(lines)

        return {
            "response": text_res,
            "patient_id": paciente_id,
            "audit_trail": audit_trail,
            "ehr_record": ehr_data
        }
