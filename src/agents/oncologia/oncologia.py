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
    "ONCOLOGIA_PUBLIC_URL", os.getenv("AGENT_URL", "http://127.0.0.1:8006")
)
openai_api_key = os.getenv("OPENAI_API_KEY", None)


class OncologiaAgent(BFAAgent):
    """Oncology specialist agent.

    Description (for FAISS indexing):
    Specialist in oncology: symptom evaluation related to oncology patients, chemotherapy side-effect
    guidance, symptom triage for urgent oncologic complications (febrile neutropenia, uncontrolled pain,
    signs of infection), and supportive care recommendations. Provides clear next-step advice and
    when to seek immediate medical attention.
    """

    def __init__(self, url: str):
        super().__init__(
            agent_id="oncologia-agent",
            name="Oncologia Agent",
            description=(
                "Oncology specialist: evaluates oncology-related symptoms, guides on chemotherapy side effects, "
                "triage for urgent oncologic complications, and provides supportive care recommendations."
            ),
            tags=["oncologia", "cancer", "quimioterapia", "complicaciones"],
            examples=[
                "tengo fiebre despues de la quimioterapia",
                "que hago si tengo nauseas intensas?",
                "dolor intenso en el sitio de tumor",
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
                                "You are an oncology specialist assistant for 'Clinica del Dr. Cureta'. "
                                "Provide triage and immediate next steps when necessary. "
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
                print(f"[Oncologia Agent LLM Error]: {e}")

        return f"Oncologia: puedo ayudar con consultas oncológicas. Resumen: '{user_message}'"


agent = OncologiaAgent(url=agent_public_url)
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
    bind_port = int(os.getenv("PORT", 8006))
    print(f"Starting Oncologia Agent server on {bind_host}:{bind_port}...")
    uvicorn.run(app, host=bind_host, port=bind_port, log_level="info")
