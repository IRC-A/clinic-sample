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

    # repo root: ../../.. from src/agents/<agent>/
    repo_env = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
    )
    load_dotenv(repo_env)
    # then agent-local .env
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except Exception:
    pass

# Defaults and env (can be overridden in the folder .env)
gateway_url = os.getenv("BFA_GATEWAY_URL", "http://127.0.0.1:8000")
agent_public_url = os.getenv(
    "PEDIATRIA_PUBLIC_URL", os.getenv("AGENT_URL", "http://127.0.0.1:8004")
)
openai_api_key = os.getenv("OPENAI_API_KEY", None)


class PediatriaAgent(BFAAgent):
    """Pediatrics specialist agent.

    Description (for FAISS indexing):
    Expert in pediatric primary care for infants, children and adolescents. Assists with
    symptom assessment (fever, cough, rash, vomiting, diarrhea), vaccination schedules,
    growth and nutrition guidance, developmental milestones, urgent-care triage, and
    when to refer to specialty care. Returns concise recommendations, severity level,
    and suggested next steps. Use for pediatric health inquiries only.
    """

    def __init__(self, url: str):
        super().__init__(
            agent_id="pediatria-agent",
            name="Pediatria Agent",
            description=(
                "Pediatrics specialist: evaluates symptoms in infants and children, provides "
                "vaccination guidance, growth and nutrition advice, developmental screening, "
                "and urgent-care triage. Returns severity and recommended next steps."
            ),
            tags=["pediatria", "niños", "infantes", "vacunas", "crecimiento"],
            examples=[
                "mi bebe tiene fiebre y no come",
                "¿cuando le toca la proxima vacuna a mi hijo?",
                "mi hija tiene un sarpullido rojo",
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
        # Use LLM to summarize/answer if available
        if self.openai_client:
            try:
                resp = await self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a pediatrician assistant for 'Clinica del Dr. Cureta'. "
                                "Answer concisely and include severity and next steps. "
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
                print(f"[Pediatria Agent LLM Error]: {e}")

        return f"Pediatria Agent: puedo ayudar con consultas pediátricas. Resumen: '{user_message}'"


agent = PediatriaAgent(url=agent_public_url)
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
    bind_port = int(os.getenv("PORT", 8004))
    print(f"Starting Pediatria Agent server on {bind_host}:{bind_port}...")
    uvicorn.run(app, host=bind_host, port=bind_port, log_level="info")
