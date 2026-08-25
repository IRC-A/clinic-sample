import os
import uvicorn
from starlette.responses import JSONResponse
from a2a.server.agent_execution.context import RequestContext
from bfa_sdk.core.agent import BFAAgent

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

# Attempt to load repo-level .env first, then a local .env in the agent folder (both optional)
try:
    from dotenv import load_dotenv

    repo_env = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
    )
    load_dotenv(repo_env)
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except Exception:
    pass

# Defaults and env (can be overridden in the folder .env)
gateway_url = os.getenv("BFA_GATEWAY_URL", "http://127.0.0.1:8000")
agent_public_url = os.getenv(
    "CLINICA_PUBLIC_URL", os.getenv("AGENT_URL", "http://127.0.0.1:8005")
)
openai_api_key = os.getenv("OPENAI_API_KEY", None)


class ClinicaGeneralAgent(BFAAgent):
    """General clinic agent.

    Description (for FAISS indexing):
    Primary care and general medicine specialist. Handles common adult medical complaints
    (respiratory, gastrointestinal, musculoskeletal, dermatologic, chronic disease follow-up),
    medication questions, preventive care, and referral recommendations. Returns concise
    differential, severity, and recommended next steps (self-care, primary appointment, ER).
    """

    def __init__(self, url: str):
        super().__init__(
            agent_id="clinica-general-agent",
            name="Clinica General Agent",
            description=(
                "General clinic specialist: evaluates common adult complaints, offers "
                "triage guidance, medication clarification, chronic-care reminders, "
                "and referral suggestions. Returns short action-oriented advice."
            ),
            tags=["salud", "clinica", "medicina general", "triage"],
            examples=[
                "tengo dolor de garganta desde hace 3 dias",
                "la pastilla X me produce mareos, que hago?",
                "necesito control de hipertension",
            ],
            url=url,
            gateway_url=gateway_url,
        )
        self.openai_client = (
            AsyncOpenAI(api_key=openai_api_key)
            if (AsyncOpenAI and openai_api_key)
            else None
        )

    async def run(self, user_message: str, context: RequestContext) -> str:
        if self.openai_client:
            try:
                resp = await self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a primary care doctor assistant for 'Clinica del Dr. Cureta'. "
                                "Provide concise triage and next steps. "
                                "Important: There is only ONE branch of the clinic. Do NOT ask which branch they want to visit. "
                                "If booking an appointment, only ask for the patient's name, day, and time."
                            ),
                        },
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0.2,
                    max_tokens=400,
                )
                return resp.choices[0].message.content.strip()
            except Exception as e:
                print(f"[Clinica General Agent LLM Error]: {e}")

        return f"Clínica General: puedo ayudar con consultas de medicina general. Resumen: '{user_message}'"


agent = ClinicaGeneralAgent(url=agent_public_url)
app = agent.app


async def _health_check(request):
    return JSONResponse(
        {
            "status": "ok",
            "agent_id": getattr(agent, "agent_id", None),
            "name": getattr(agent, "name", None),
        }
    )


app.add_route("/", _health_check, methods=["GET"])


if __name__ == "__main__":
    bind_host = os.getenv("HOST", "0.0.0.0")
    bind_port = int(os.getenv("PORT", 8005))
    print(f"Starting Clinica General Agent server on {bind_host}:{bind_port}...")
    uvicorn.run(app, host=bind_host, port=bind_port, log_level="info")
