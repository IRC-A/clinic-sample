import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

# Load .env file from repository root if present
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))


@dataclass
class Config:
    """Central configuration for Google ADK Agents and FastMCP servers."""
    
    # GCP BFA Gateway Settings (Live Production Endpoint)
    bfa_gateway_url: str = os.getenv(
        "BFA_GATEWAY_URL", "https://irc-a-gateway-hmwmve5bjq-uc.a.run.app"
    ).rstrip("/")
    bfa_api_key: str = os.getenv("BFA_API_KEY", "bfa_gcp_hackathon_demo_key_2026")
    
    # Google AI / Gemini API Credentials
    gemini_api_key: str = os.getenv(
        "GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", "")
    )
    
    # PASETO DET Ticket Keys
    det_public_key_path: str = os.getenv(
        "DET_PUBLIC_KEY_PATH", "./keys/gateway_public.pem"
    )
    det_private_key_path: str = os.getenv(
        "DET_PRIVATE_KEY_PATH", "./keys/gateway_private.pem"
    )
    
    # Agent Authorized Channel Masks
    triage_channels: List[str] = field(
        default_factory=lambda: os.getenv("TRIAGE_CHANNELS", "#citas,#staff").split(",")
    )
    doctor_channels: List[str] = field(
        default_factory=lambda: os.getenv(
            "DOCTOR_CHANNELS", "#citas,#staff,#historial-medico,#vademecum"
        ).split(",")
    )
    
    # Server network settings
    host: str = os.getenv("HOST", "0.0.0.0")
    public_url: str = os.getenv("PUBLIC_URL", "http://127.0.0.1:8000")


config = Config()
