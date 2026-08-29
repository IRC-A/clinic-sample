import os
import json
import httpx
import asyncio
from src.config import config

MCP_SERVERS_METADATA = [
    {
        "node_id": "mcp-citas",
        "channels": "#citas",
        "name": "mcp_citas",
        "tools": [
            {
                "name": "consultar_turnos",
                "description": "Queries available medical appointment slots for clinic specialties.",
                "channels": ["#citas"]
            },
            {
                "name": "agendar_turno",
                "description": "Schedules and confirms a medical appointment slot generating a DET booking ticket.",
                "channels": ["#citas"]
            }
        ]
    },
    {
        "node_id": "mcp-staff",
        "channels": "#staff",
        "name": "mcp_staff",
        "tools": [
            {
                "name": "consultar_directorio",
                "description": "Consults clinic medical directory and physician licenses.",
                "channels": ["#staff"]
            },
            {
                "name": "consultar_guardia",
                "description": "Queries active on-call emergency physicians and duty shifts.",
                "channels": ["#staff"]
            }
        ]
    },
    {
        "node_id": "mcp-ehr",
        "channels": "#historial-medico",
        "name": "mcp_ehr",
        "tools": [
            {
                "name": "consultar_historial",
                "description": "Fetches confidential electronic health record EHR for patient ID.",
                "channels": ["#historial-medico"]
            },
            {
                "name": "guardar_evolucion",
                "description": "Persists diagnostic medical evolution with non-repudiation SHA-256 hash and DET PASETO ticket.",
                "channels": ["#historial-medico"]
            }
        ]
    },
    {
        "node_id": "mcp-vademecum",
        "channels": "#vademecum",
        "name": "mcp_vademecum",
        "tools": [
            {
                "name": "validar_contraindicaciones",
                "description": "Evaluates pharmacological contraindications, drug-allergy safety, and drug-drug interactions.",
                "channels": ["#vademecum"]
            }
        ]
    }
]


async def register_all_mcp_servers_with_gateway(gateway_url: str = None) -> bool:
    """Registers all FastMCP servers with BFA Gateway so Indexed MCP Tools > 0."""
    target_url = (gateway_url or config.bfa_gateway_url).rstrip("/")
    
    print(f"📡 Registering FastMCP Servers with BFA Gateway: {target_url}")
    success_count = 0
    
    async with httpx.AsyncClient(timeout=8.0) as client:
        for srv in MCP_SERVERS_METADATA:
            try:
                # 1. Try registering via POST /register/mcp
                res = await client.post(
                    f"{target_url}/register/mcp",
                    params={
                        "url": f"http://127.0.0.1:8080/{srv['node_id']}",
                        "channels": srv["channels"],
                        "node_id": srv["node_id"]
                    },
                    json={"tools": srv["tools"]},
                    headers={"Authorization": f"Bearer {config.bfa_api_key}"}
                )
                if res.status_code in [200, 201]:
                    print(f"  ✅ Registered {srv['node_id']} on channel {srv['channels']}")
                    success_count += 1
                else:
                    # 2. Try registering via POST /mint or alternative endpoint
                    print(f"  ℹ️ Server {srv['node_id']} status: {res.status_code}")
            except Exception as e:
                print(f"  ⚠️ Could not register {srv['node_id']}: {e}")
                
    return success_count > 0


if __name__ == "__main__":
    asyncio.run(register_all_mcp_servers_with_gateway())
