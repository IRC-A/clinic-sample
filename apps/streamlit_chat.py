import os
import uuid
import json
from datetime import datetime
from pathlib import Path
import httpx
import streamlit as st

# Hospital display name (default in English)
HOSPITAL_NAME = os.environ.get("HOSPITAL_NAME", "Dr. Cureta Clinic")

# --- Streamlit Page Configuration -----------------------------------
st.set_page_config(
    page_title=f"CRM Agents — {HOSPITAL_NAME}",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- URL del Agente Interactivo Principal (main-agent) ----------------------
ENTRY_AGENT_URL = os.environ.get(
    "ENTRY_AGENT_URL",
    os.environ.get("MAIN_AGENT_URL", "http://127.0.0.1:8310"),
).rstrip("/")

# Fallback para ejecución local fuera de Docker
if "localhost" in ENTRY_AGENT_URL or "127.0.0.1" in ENTRY_AGENT_URL:
    TARGET_A2A_URL = ENTRY_AGENT_URL
else:
    TARGET_A2A_URL = ENTRY_AGENT_URL


# --- Session State --------------------------------------------------------
if "session_id" not in st.session_state:
    st.session_state.session_id = f"crm_session_{uuid.uuid4().hex[:8]}"

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": f"Hi! 👋 Welcome to {HOSPITAL_NAME}. I'm the Interactive CRM Chatbot. How can I help you today?",
        }
    ]


# --- Custom CSS Styles (Dark Glassmorphism) ----------
st.markdown(
    """
    <style>
    .stApp { background: linear-gradient(135deg, #0f172a 0%, #1e1e2e 100%); color: #f8fafc; }
    header[data-testid="stHeader"] { background: transparent !important; }
    section[data-testid="stSidebar"] { background-color: rgba(30,41,59,0.7) !important; backdrop-filter: blur(12px); border-right:1px solid rgba(255,255,255,0.05); }
    .glass-card { background: rgba(30,41,59,0.5); backdrop-filter: blur(10px); border-radius: 12px; padding: 1rem; margin-bottom:1rem; }
    .status-badge-online { display:inline-flex; align-items:center; background: rgba(16,185,129,0.12); color:#10b981; border-radius:20px; padding:4px 10px; }
    .status-badge-offline { display:inline-flex; align-items:center; background: rgba(239,68,68,0.12); color:#ef4444; border-radius:20px; padding:4px 10px; }
    .main-title { font-size:2.0rem; font-weight:800; background: linear-gradient(90deg,#38bdf8 0%,#818cf8 100%); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
    </style>
    """,
    unsafe_allow_html=True,
)


# --- Function to check A2A connection to the main interactive agent ------------------------
def check_agent_health(url: str) -> bool:
    try:
        for target in [url, "http://localhost:8310", "http://127.0.0.1:8310"]:
            try:
                res = httpx.get(
                    f"{target.rstrip('/')}/.well-known/agent-card.json", timeout=1.5
                )
                if res.status_code == 200:
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


# --- Function to send A2A JSON-RPC message to interactive agent -----------------------------
def send_a2a_message(user_text: str, session_id: str) -> str:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "SendMessage",
        "params": {
            "message": {
                "role": "ROLE_USER",
                "message_id": f"msg_{uuid.uuid4().hex[:6]}",
                "context_id": session_id,
                "parts": [{"text": user_text}],
            }
        },
    }
    headers = {"Content-Type": "application/json", "A2A-Version": "1.0"}

    urls_to_try = [TARGET_A2A_URL, "http://localhost:8310", "http://127.0.0.1:8310"]
    urls_to_try = list(dict.fromkeys(urls_to_try))

    last_error = None
    for url in urls_to_try:
        endpoint = url.rstrip("/") + "/"
        try:
            with httpx.Client(timeout=30.0) as client:
                res = client.post(endpoint, json=payload, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    if "result" in data and "message" in data["result"]:
                        parts = data["result"]["message"].get("parts", [])
                        if parts and "text" in parts[0]:
                            return parts[0]["text"]
                    if "error" in data:
                        return f"⚠️ Error del agente: {data['error'].get('message', 'Error desconocido')}"
                last_error = f"HTTP {res.status_code}: {res.text}"
        except Exception as e:
            last_error = str(e)

    return f"❌ Could not connect to the BFA interactive agent. ({last_error})"


# --- Sidebar -----------------------------------------------------------------
with st.sidebar:
    st.image("https://img.icons8.com/fluency/48/hospital-2.png", width=64)
    st.markdown(f"### **{HOSPITAL_NAME} — IRC-A Control Panel**")

    is_online = check_agent_health(TARGET_A2A_URL)
    if is_online:
        st.markdown(
            '<div class="status-badge-online">🟢 Agent Online</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="status-badge-offline">🔴 Agent Offline</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("#### **Session Information**")
    st.caption(f"**Session ID:** `{st.session_state.session_id}`")
    st.caption(f"**Gateway Target:** `{TARGET_A2A_URL}`")

    if st.button("🔄 Restart Session / Clear Chat", use_container_width=True):
        st.session_state.session_id = f"crm_session_{uuid.uuid4().hex[:8]}"
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Session restarted! 👋 How can I help you?",
            }
        ]
        st.rerun()

    st.markdown("---")
    # Dynamic frequent queries (persisted locally in `data/suggestions.json`)
    SUG_FILE = os.environ.get("SUGGESTIONS_FILE", "data/suggestions.json")

    def load_suggestions():
        p = Path(SUG_FILE)
        if not p.exists():
            return []
        try:
            with p.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return []

    def save_suggestions(items):
        p = Path(SUG_FILE)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(items, fh, ensure_ascii=False, indent=2)
        tmp.replace(p)

    def bump_suggestion(text: str):
        items = load_suggestions()
        key = text.strip()
        if not key:
            return
        now = datetime.utcnow().isoformat()
        for it in items:
            if it.get("text") == key:
                it["count"] = it.get("count", 0) + 1
                it["last_used"] = now
                save_suggestions(items)
                return
        # new suggestion
        items.append({"text": key, "count": 1, "last_used": now})
        save_suggestions(items)

    suggestions = load_suggestions()
    # sort by count desc then recent
    suggestions = sorted(
        suggestions, key=lambda x: (-x.get("count", 0), x.get("last_used", ""))
    )
    prompt_to_send = None
    if suggestions:
        st.markdown("#### Frequent Queries")
        for s in suggestions[:6]:
            label = s.get("text")
            if st.button(label, use_container_width=True):
                prompt_to_send = label


# --- Main Area ----------------------------------------------------------
st.markdown(
    f'<div class="main-title">CRM Agents — {HOSPITAL_NAME}</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="sub-title">Reasoning Layer (IRC-A / BFA Architecture) for EspoCRM</div>',
    unsafe_allow_html=True,
)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Write your query about clients, contacts or reports...")
query = prompt_to_send or user_input

if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    # Comprobar conexión al main-agent antes de enviar
    is_online_now = check_agent_health(TARGET_A2A_URL)
    if not is_online_now:
        response_text = "❌ Interactive agent is offline. Verify the `main-agent` connection before retrying."
        with st.chat_message("assistant"):
            st.markdown(response_text)
    else:
        # Respuesta del asistente
        with st.chat_message("assistant"):
            with st.spinner("Reasoning and consulting the BFA agent network..."):
                response_text = send_a2a_message(query, st.session_state.session_id)
                st.markdown(response_text)

        # Si provino de una sugerencia, actualizar contador
        try:
            if "bump_suggestion" in globals() and prompt_to_send:
                bump_suggestion(prompt_to_send)
        except Exception:
            pass

    # Guardar en memoria de sesión
    st.session_state.messages.append({"role": "assistant", "content": response_text})
