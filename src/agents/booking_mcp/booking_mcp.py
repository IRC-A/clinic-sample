import os
import uvicorn
from bfa_sdk.core.mcp import BFAMCP

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

gateway_url = os.getenv("BFA_GATEWAY_URL", "http://127.0.0.1:8000")

# Instanciar el servidor MCP
mcp = BFAMCP(
    name="Booking MCP Mockup",
    node_id="booking-mcp",
    gateway_url=gateway_url
)

@mcp.tool(
    name="agendar_turno",
    description="Agenda un turno medico para cualquier especialidad en la Clinica del Dr. Cureta.",
    tags=["turnos", "agendar", "reservar", "calendario", "cita", "medico"],
    examples=["necesito agendar un turno", "agendar turno para Juan Perez el viernes a las 15"]
)
def agendar_turno(paciente: str, dia: str, horario: str) -> str:
    """
    Agenda un turno médico.
    :param paciente: Nombre del paciente.
    :param dia: Día del turno (ej: Lunes, 2026-08-25).
    :param horario: Horario del turno (ej: 15:30).
    """
    print(f"[Booking MCP] Solicitud recibida: Agendar turno para {paciente} el {dia} a las {horario}.")
    return f"Turno agendado exitosamente para {paciente} el dia {dia} a las {horario}."

app = mcp.app

import threading

def _register_thread():
    import time
    import asyncio
    time.sleep(2)
    public_url = os.getenv("PUBLIC_URL", "http://127.0.0.1:8010")
    print(f"Registrando MCP en el Gateway usando URL {public_url}...", flush=True)
    asyncio.run(mcp.register_with_gateway(gateway_url, public_url))

threading.Thread(target=_register_thread, daemon=True).start()

if __name__ == "__main__":
    bind_host = os.getenv("HOST", "0.0.0.0")
    bind_port = int(os.getenv("PORT", 8010))
    print(f"Starting Booking MCP server on {bind_host}:{bind_port}...")
    uvicorn.run(app, host=bind_host, port=bind_port, log_level="info")
