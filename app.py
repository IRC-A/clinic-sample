import os
import json
import asyncio
from datetime import datetime, timezone
import streamlit as st

from src.config import config
from src.security.det_validator import issue_det_ticket, verify_det_ticket
from src.agents.triage_agent import TriageAgent
from src.agents.doctor_agent import DoctorAgent

# Page setup
st.set_page_config(
    page_title="The Fortified Healthcare Fleet — IRC-A & Google ADK",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS styling with Dark Glassmorphism and Healthcare Accents
st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(135deg, #0b132b 0%, #1c2541 50%, #0b132b 100%);
        color: #f8fafc;
    }
    header[data-testid="stHeader"] { background: transparent !important; }
    section[data-testid="stSidebar"] {
        background-color: rgba(15, 23, 42, 0.85) !important;
        backdrop-filter: blur(16px);
        border-right: 1px solid rgba(56, 189, 248, 0.2);
    }
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #38bdf8 0%, #818cf8 50%, #c084fc 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        color: #94a3b8;
        font-size: 1.0rem;
        margin-bottom: 1.5rem;
    }
    .badge-gcp {
        background: rgba(56, 189, 248, 0.15);
        color: #38bdf8;
        border: 1px solid rgba(56, 189, 248, 0.4);
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        display: inline-block;
    }
    .badge-authorized {
        background: rgba(34, 197, 94, 0.15);
        color: #4ade80;
        border: 1px solid rgba(34, 197, 94, 0.4);
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-denied {
        background: rgba(239, 68, 68, 0.15);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.4);
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Initialize Session State
if "messages_triage" not in st.session_state:
    st.session_state.messages_triage = [
        {"role": "assistant", "content": "👋 Hello! Welcome to the **Patient Portal (Triage)** of Dr. Cureta Clinic. How can I help you find a doctor or schedule an appointment today?"}
    ]

if "messages_doctor" not in st.session_state:
    st.session_state.messages_doctor = [
        {"role": "assistant", "content": "🩺 **Specialist Medical Console (Google ADK / Gemini 3.5 Pro)** initialized. Select a Patient ID to evaluate clinical history, check drug contraindications in vademecum, and record signed diagnostic evolutions."}
    ]

if "audit_logs" not in st.session_state:
    st.session_state.audit_logs = []

# Sidebar — Zero-Trust Live Audit Panel
with st.sidebar:
    st.image("https://img.icons8.com/fluency/64/hospital-2.png", width=56)
    st.markdown("### **BFA Gateway & Zero-Trust Audit**")
    st.markdown('<span class="badge-gcp">☁️ GCP Remote Production Gateway</span>', unsafe_allow_html=True)
    st.caption(f"**Endpoint:** `{config.bfa_gateway_url}`")

    st.markdown("---")
    st.markdown("#### **Active Identity & Channel Masking**")

    active_view = st.radio("Select View / User Role", ["Patient Portal (Triage)", "Doctor Specialist Console"])

    if active_view == "Patient Portal (Triage)":
        active_role = "triage-agent (Gemini 3.5 Flash)"
        authorized = ["#citas", "#staff"]
        denied = ["#historial-medico", "#vademecum"]
    else:
        active_role = "doctor-agent (Gemini 3.5 Pro)"
        authorized = ["#citas", "#staff", "#historial-medico", "#vademecum"]
        denied = []

    st.markdown(f"**Active Identity:** `{active_role}`")
    st.markdown("**Authorized Channels:**")
    for ch in authorized:
        st.markdown(f"- <span class=\"badge-authorized\">{ch}</span>", unsafe_allow_html=True)

    st.markdown("**Denied / Masked Channels:**")
    if denied:
        for ch in denied:
            st.markdown(f"- <span class=\"badge-denied\">{ch}</span>", unsafe_allow_html=True)
    else:
        st.caption("No channels denied for authorizing physician role.")

    st.markdown("---")
    st.markdown("#### **Live DET Ticket Inspector (PASETO v4.public)**")
    
    sample_det = issue_det_ticket(
        agent_id="triage-agent" if "Triage" in active_view else "doctor-agent",
        channel="#citas" if "Triage" in active_view else "#historial-medico",
        params={"patient_id": "101", "timestamp": datetime.now(timezone.utc).isoformat()}
    )
    
    with st.expander("🔍 Inspect Ephemeral DET Token", expanded=False):
        st.code(sample_det["det_token"][:65] + "...", language="text")
        st.json(sample_det["payload"])
        st.markdown(f"**PASETO Signature:** `v4.public (Ed25519)`")
        st.markdown(f"**params_hash:** `{sample_det['params_hash'][:16]}...`")

    st.markdown("---")
    st.markdown("#### **Semantic Discovery (FAISS Trace)**")
    with st.expander("📡 Discovery Registry Logs", expanded=False):
        st.caption("GCP Gateway FAISS vector search trace for late-binding tools:")
        st.code("#citas -> FastMCP Citas Server (0.98 similarity)\n#staff -> FastMCP Staff Server (0.95 similarity)\n#historial-medico -> FastMCP EHR Server (0.99 similarity)\n#vademecum -> FastMCP Vademecum Server (0.97 similarity)")

# Main Interface Layout
st.markdown('<div class="main-title">The Fortified Healthcare Fleet</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Google ADK & Gemini 3.5 with IRC-A Zero-Trust Runtime Governance on Google Cloud</div>', unsafe_allow_html=True)

if active_view == "Patient Portal (Triage)":
    st.subheader("🤖 View 1: Patient Portal (Triage / Public Reception)")
    st.info("💡 **Authorized Channels:** `#citas`, `#staff`. **Zero-Trust Enforcement:** Access attempts to `#historial-medico` will be masked and rejected.")

    for msg in st.session_state.messages_triage:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("Enter your request (e.g. 'I need to book a Pediatrics appointment' or test prompt injection)...")
    if user_input:
        st.session_state.messages_triage.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Processing with Gemini 3.5 Flash & BFA Gateway..."):
                triage_agent = TriageAgent()
                result = asyncio.run(triage_agent.run(user_input))
                st.markdown(result["response"])

                if result.get("blocked"):
                    st.error("🚨 Prompt Injection / Scope Creep Neutralized by GCP BFA Gateway Channel Masking Policy.")

        st.session_state.messages_triage.append({"role": "assistant", "content": result["response"]})

else:
    st.subheader("🩺 View 2: Specialist Medical Console (Pediatrics / General / Oncology)")
    st.success("🔒 **Medical Authentication:** Active National Medical License. **Authorized Channels:** `#citas`, `#staff`, `#historial-medico`, `#vademecum`.")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("#### **Patient Chart**")
        paciente_id = st.selectbox("Select Patient", ["101", "102"], index=0)
        medico_id = st.text_input("Doctor ID", value="MED-301")
        especialidad = st.selectbox("Specialty", ["Pediatrics", "General Medicine", "Oncology"])

        st.markdown("#### **Quick Actions**")
        btn_historial = st.button("📄 Consult Clinical History", use_container_width=True)
        btn_vademecum = st.button("💊 Validate Amoxicillin Prescription", use_container_width=True)

    with col2:
        for msg in st.session_state.messages_doctor:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        doctor_input = st.chat_input("Clinical consultation or medical prescription...")

        query = None
        if btn_historial:
            query = f"Consult complete clinical history for patient {paciente_id}"
        elif btn_vademecum:
            query = f"Validate Amoxicillin prescription for patient {paciente_id}"
        elif doctor_input:
            query = doctor_input

        if query:
            st.session_state.messages_doctor.append({"role": "user", "content": query})
            with st.chat_message("user"):
                st.markdown(query)

            with st.chat_message("assistant"):
                with st.spinner("Deep Clinical Reasoning with Gemini 3.5 Pro..."):
                    doctor_agent = DoctorAgent(medico_id=medico_id, especialidad=especialidad)
                    res = asyncio.run(doctor_agent.run(query, paciente_id=paciente_id))
                    st.markdown(res["response"])

                    if res.get("audit_trail"):
                        st.markdown("---")
                        st.caption("🛡️ **Zero-Trust Audit Trail (DET Signed Operations):**")
                        for entry in res["audit_trail"]:
                            det_info = entry.get("det", {})
                            st.code(f"Channel: {entry['channel']} | Tool: {entry['action']} | DET Token: {det_info.get('det_token', '')[:45]}...", language="text")

            st.session_state.messages_doctor.append({"role": "assistant", "content": res["response"]})
