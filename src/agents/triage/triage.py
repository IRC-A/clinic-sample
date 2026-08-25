import os
import uvicorn
import asyncio
from a2a.server.agent_execution.context import RequestContext
from bfa_sdk.core.agent import BFAAgent

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

from starlette.responses import JSONResponse

# Load repo-level .env first, then agent-local .env (optional)
try:
    from dotenv import load_dotenv

    repo_env = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
    )
    load_dotenv(repo_env)
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except Exception:
    pass

# If IRCA_CHANNELS is set in env, ensure it's present in os.environ
if os.getenv("IRCA_CHANNELS"):
    os.environ["IRCA_CHANNELS"] = os.getenv("IRCA_CHANNELS")
gateway_url = os.getenv("BFA_GATEWAY_URL", "http://127.0.0.1:8000")
agent_public_url = os.getenv(
    "PUBLIC_URL", os.getenv("AGENT_URL", "http://127.0.0.1:8003")
)

openai_api_key = os.getenv("OPENAI_API_KEY", None)


class TriageAgent(BFAAgent):

    def __init__(self, url: str):
        super().__init__(
            agent_id="triage-agent",
            name="Triage Agent",
            description=(
                "You are the Triage Agent for Hospital Booking. Your task is to identify "
                "the user's needs and route them to the appropriate agent."
            ),
            tags=["triage", "Triage", "Booking", "info", "concierge"],
            examples=[
                "I need book a room",
                "I want a room for 2 adults and 1 child",
                "Do you have swimming pool?",
                "Is near to beach",
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
                response = await self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a Triage AI Agent for 'Clinica del Dr. Cureta'. \n"
                                "Your task is to identify the user's needs and reach the right agent for routing the user request. \n"
                                "Important: There is only ONE branch of the clinic. Do NOT ask the user which branch they want to visit. "
                                "If a user wants to book an appointment, only ask for their name, preferred day, and time."
                            ),
                        },
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0.1,
                    max_tokens=350,
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                print(f"[{self.name} Agent LLM Error]: {e}")

        return f"Hello! I am {self.name}. I'm Digital Receptionist for Hospital Costa Do Mar. How can I help you today: '{user_message}'?"


agent = TriageAgent(url=agent_public_url)
app = agent.app


async def _health_check(request):
    """Simple GET root used by gateway discovery and health checks."""
    payload = {
        "status": "ok",
        "agent_id": getattr(agent, "agent_id", None),
        "name": getattr(agent, "name", None),
    }
    return JSONResponse(payload)


# Starlette apps don't provide FastAPI-style decorator helpers like `app.get`.
# Use `add_route` so gateway discovery can call GET /
app.add_route("/", _health_check, methods=["GET"])


if __name__ == "__main__":
    bind_host = os.getenv("HOST", "0.0.0.0")
    bind_port = int(os.getenv("PORT", 8003))
    print(f"Starting Triage Agent server on {bind_host}:{bind_port}...")
    uvicorn.run(app, host=bind_host, port=bind_port, log_level="info")
