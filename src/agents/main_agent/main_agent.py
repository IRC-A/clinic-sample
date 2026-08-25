import os
import logging
import uvicorn
from bfa_sdk.core.interactive_agent import BFAInteractiveAgent, MemoryStack

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


class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "GET /tools" not in record.getMessage()


logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

logging.info("------------ main_agent.py logs -------------")


class MainAgent(BFAInteractiveAgent):

    def __init__(self, url: str, hospital_name: str, gateway_url: str | None = None):
        # English description for FAISS / indexing and UI
        description = (
            f"Interactive frontend welcome agent for {hospital_name}. "
            "Greets users, and ask how you can help."
        )
        # Do not auto-register with the gateway for local demo use by setting gateway_url=None
        super().__init__(
            agent_id="main-agent",
            name="Interactive Chatbot",
            description=description,
            tags=["chat", "support", "welcome"],
            examples=["hello", "good afternoon", "who are you"],
            url=url,
            gateway_url=gateway_url,
        )

    @property
    def gateway_public_key(self):
        return None

    @gateway_public_key.setter
    def gateway_public_key(self, value):
        pass

    async def handle_interaction(
        self, session_id: str, user_message: str, memory: MemoryStack
    ) -> str:
        print(f"[Chatbot] Message received in session {session_id}: {user_message}")

        # 1. If the user requests the internal conversational history for the session:
        if "history" in user_message.lower() or "historial" in user_message.lower():
            session_data = memory.get_session(session_id)
            return (
                f"[Chatbot] Session memory: {len(session_data['history'])} messages. "
                f"Invoked agents/tools: {list(session_data['invoked_agents'])}"
            )

        # 2. Reduce the user message based on conversation history
        session_data = memory.get_session(session_id)
        history = session_data.get("history", [])
        
        reduced_query = user_message
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=openai_key)
            
            history_text = "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in history])
            
            system_prompt = (
                "You are an AI context manager for a medical routing gateway. "
                "Read the conversation history and output a SINGLE, clear, standalone query that represents the user's FULL current need. "
                "Remove all conversational redundancies, but keep all accumulated details (patient name, day, time, specialty). "
                "For example, if history shows they want a pediatric appointment on August 10 and they just replied 'yes' or 'Sandro, on Thursday', "
                "you should output: 'Agendar turno pediatria paciente Sandro jueves 10 agosto'. "
                "If it's just a greeting, output 'saludar'. "
                "IMPORTANT: Output ONLY the reduced query, nothing else."
            )
            
            try:
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Conversation history:\n{history_text}\n\nReduced query:"}
                    ],
                    temperature=0.0
                )
                reduced_query = response.choices[0].message.content.strip()
                print(f"[MainAgent] Reduced query from LLM: {reduced_query}")
            except Exception as e:
                print(f"[MainAgent] Reduction error: {e}")

        # 3. Delegate by intent to the BFA Gateway using the reduced query
        try:
            raw_result = await self.delegate_task(reduced_query, session_id)
            if not raw_result:
                return "[Chatbot] At this moment I can't help with that."
                
            # 4. Synthesize the final response using the context
            if openai_key:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=openai_key)
                
                synthesis_prompt = (
                    f"You are the frontend receptionist for {self.name}. "
                    "You have just delegated a user request to a specialist agent or system. "
                    "Below is the raw response returned by the internal system. "
                    "Your job is to read the conversation history and the raw response, and formulate a final, natural, empathetic, and professional reply to the user. "
                    "Do NOT add new medical advice or change the facts of the raw response. Just present it conversationally. "
                    "If the raw response is already conversational, just pass it through or polish it slightly."
                )
                
                try:
                    synth_response = await client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": synthesis_prompt},
                            {"role": "user", "content": f"Conversation history:\n{history_text}\n\nInternal system response:\n{raw_result}\n\nFinal reply to user:"}
                        ],
                        temperature=0.3
                    )
                    final_result = synth_response.choices[0].message.content.strip()
                    print(f"[MainAgent] Synthesized response: {final_result}")
                    return final_result
                except Exception as e:
                    print(f"[MainAgent] Synthesis error: {e}")
                    return raw_result
            else:
                return raw_result
                
        except Exception as err:
            print(f"[Chatbot] Delegation error: {err}")
            return f"[Chatbot] Error delegating the request: {err}"


# Initialize dynamically from env variables
agent_port = int(os.environ.get("MAIN_AGENT_PORT", os.getenv("PORT", "8310")))
agent_url = os.environ.get("MAIN_AGENT_URL", f"http://main-agent:{agent_port}")
# Default hospital name in English
hospital_name = os.environ.get("HOSPITAL_NAME", "Dr. Cureta Clinic")
gateway_url = os.environ.get("BFA_GATEWAY_URL", "").strip()
# Prefer agent-local .env explicit value when present (allows empty to disable registration)
try:
    agent_local_env = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(agent_local_env):
        with open(agent_local_env, "r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip().startswith("BFA_GATEWAY_URL"):
                    # format: BFA_GATEWAY_URL=... (allow empty)
                    _, val = line.split("=", 1)
                    gateway_url = val.strip()
                    break
except Exception:
    pass

# Leave environment variables intact; gateway_url controls registration behavior

if not gateway_url:
    # Run a lightweight standalone Starlette app for local demo (no gateway registration)
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.requests import Request
    import json

    app = Starlette()

    async def _agent_card(request: Request):
        return JSONResponse(
            {
                "agent_id": "main-agent",
                "name": "Interactive Chatbot",
                "description": "Interactive Agent. This agent responds to requests from final users. Always asks for help from the BFA Gateway to check who can help with the answer.",
                "version": "dev",
            }
        )

    async def _jsonrpc(request: Request):
        try:
            payload = await request.json()
            # support SendMessage RPC
            params = payload.get("params", {})
            message = params.get("message", {})
            parts = message.get("parts", [])
            text = parts[0].get("text", "") if parts else ""
            resp = {
                "jsonrpc": "2.0",
                "id": payload.get("id"),
                "result": {
                    "message": {"parts": [{"text": f"[main-agent] Echo: {text}"}]}
                },
            }
            return JSONResponse(resp)
        except Exception as e:
            return JSONResponse(
                {"jsonrpc": "2.0", "id": None, "error": {"message": str(e)}},
                status_code=500,
            )

    # add routes explicitly
    app.add_route("/.well-known/agent-card.json", _agent_card, methods=["GET"])
    app.add_route("/", _jsonrpc, methods=["POST"])

    # add tools route
    async def _tools(request):
        return JSONResponse({"status": "ok"})

    app.add_route("/tools", _tools, methods=["GET"])
else:
    agent = MainAgent(url=agent_url, hospital_name=hospital_name)
    app = agent.app

if hasattr(app, "add_route"):
    from starlette.responses import JSONResponse

    async def _tools(request):
        return JSONResponse({"status": "ok"})

    app.add_route("/tools", _tools, methods=["GET"])

if __name__ == "__main__":
    print(f"Starting Interactive Chatbot Agent server on port {agent_port}...")
    uvicorn.run(app, host="0.0.0.0", port=agent_port, log_level="info")
