# The Fortified Healthcare Fleet: Extending Google ADK with IRC-A Zero-Trust Runtime Governance on Google Cloud

[![Google All Things Agentic Hackathon](https://img.shields.io/badge/Google%20Hackathon-The%20Fortified%20Enterprise%20Fleet-4285F4?style=for-the-badge&logo=google)](https://devpost.com)
[![Prizes](https://img.shields.io/badge/Total%20Prizes-%24750%2C000%20USD-34A853?style=for-the-badge&logo=google)](https://devpost.com)
[![Google ADK](https://img.shields.io/badge/Google%20ADK-Gemini%203.5-34A853?style=for-the-badge&logo=google)](https://ai.google.dev)
[![Terraform IaC](https://img.shields.io/badge/Terraform-GCP%20Cloud%20Run-7B42BC?style=for-the-badge&logo=terraform)](https://www.terraform.io)
[![IRC-A Protocol](https://img.shields.io/badge/IRC--A-Zero--Trust%20Runtime-EA4335?style=for-the-badge)](https://github.com/IRC-A/clinic-sample)

Submitted to the **Google All Things Agentic Hackathon** (Devpost, **$750,000 USD Total Prize Pool**) competing for **1st Place ($50,000 USD)** in the track: **"The Fortified Enterprise Fleet"** (Corporate discovery, Zero-Trust runtime access, policy enforcement, Model Armor, and execution isolation).

---

## 📌 Features and Functionality

High-stakes corporate environments—such as clinical healthcare, financial systems, and enterprise legal ops—demand strict runtime access control and deterministic security bounds for autonomous AI agent fleets. While LLM-driven agents powered by **Google ADK** provide remarkable cognitive reasoning, raw agent execution without network-level isolation risks prompt injection attacks, unauthorized scope creep, and data leakage.

**The Fortified Healthcare Fleet** solves this by pairing **Google ADK (Gemini 3.5 Flash & Gemini 3.5 Pro)** with **IRC-A (Internet Relay Chat for Agents)** protocol and the **BFA (Backend for Agents)** design pattern deployed on **Google Cloud Platform (GCP)** via **Terraform Infrastructure as Code (IaC)**.

- **Official Repositories:**
  - **BFA Gateway Infrastructure:** [`https://github.com/IRC-A/bfa-gateway`](https://github.com/IRC-A/bfa-gateway)
  - **Fortified Healthcare Fleet App:** [`https://github.com/IRC-A/clinic-sample`](https://github.com/IRC-A/clinic-sample)
- **Dual-View Web Interface (`app.py`):**
  - **Patient Triage Portal:** Allows patients to query medical specialties, check on-call doctors, and book appointments via Gemini 3.5 Flash.
  - **Specialist Medical Console:** Empowers licensed doctors to consult EHR clinical records, evaluate drug interactions in the vademecum, and record diagnostic evolutions via Gemini 3.5 Pro.
- **Zero-Trust Live Audit Panel:** Real-time visual sidebar logging active agent identities, channel permission masks, GCP FAISS semantic discovery traces, and PASETO v4.public ephemeral DET ticket inspection.
- **Prompt Injection & Scope Creep Neutralization:** Indirect prompt injections attempting to extract confidential medical records through public triage channels are automatically blocked by GCP BFA Gateway channel masking.
- **Non-Repudiation Audit Logs:** Clinical evolutions are written with SHA-256 parameter digests and signed PASETO v4 tickets.

---

## 🏗️ System Architecture Diagram

```mermaid
graph TD
    UI[Streamlit Dual-View Interface app.py] -->|Patient Queries| TA[Triage Agent - Gemini 3.5 Flash]
    UI -->|Doctor Consultations| DA[Doctor Agent - Gemini 3.5 Pro]
    
    subgraph Google Cloud Platform GCP
        BFA[BFA Gateway - Cloud Run Service]
        FAISS[FAISS Vector Registry - Late-Binding Discovery]
        POLICY[Zero-Trust Policy Engine & Channel Masking]
        DET[PASETO v4.public Ephemeral Ticket Issuer]
        
        BFA --> FAISS
        BFA --> POLICY
        BFA --> DET
    end
    
    TA -->|Channel Mask: #citas, #staff| BFA
    DA -->|Channel Mask: #citas, #staff, #historial-medico, #vademecum| BFA
    
    BFA -->|Verified Token| MCP1[mcp_citas - #citas]
    BFA -->|Verified Token| MCP2[mcp_staff - #staff]
    BFA -->|Verified Token| MCP3[mcp_ehr - #historial-medico]
    BFA -->|Verified Token| MCP4[mcp_vademecum - #vademecum]
```

---

## ⚡ BFA Gateway Discovery & Onboarding Patterns

The solution supports two dynamic discovery & onboarding modes for FastMCP tool servers and Google ADK agents:

1. **Auto-Registration via `.env`:**
   When configured with `BFA_GATEWAY_URL=https://irc-a-gateway-hmwmve5bjq-uc.a.run.app`, agents and FastMCP servers automatically register their node identity, channel masks, and tool descriptions with the remote BFA Gateway during startup initialization.

2. **Hot-Onboarding via cURL (On-the-Fly Registration):**
   If a gateway URL is not set in environment variables at boot time, new tools and agents can be onboarded dynamically in production ("hot-onboarding") by sending a JSON payload via `cURL` to the GCP BFA Gateway endpoint without restarting any services:

```bash
curl -X POST "https://irc-a-gateway-hmwmve5bjq-uc.a.run.app/api/v1/registry/onboard" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer bfa_gcp_hackathon_demo_key_2026" \
     -d '{
           "node_id": "mcp-laboratorio",
           "channel": "#laboratorio",
           "name": "mcp_laboratorio",
           "description": "Deterministic clinical laboratory analysis lookup",
           "endpoint": "http://127.0.0.1:8015/mcp"
         }'
```

---

## 🛠️ Infrastructure as Code (Terraform) & Tech Stack

- **Infrastructure as Code:** Terraform (`terraform/main.tf`, `variables.tf`, `outputs.tf`).
- **Official Repositories:** [`IRC-A/bfa-gateway`](https://github.com/IRC-A/bfa-gateway) & [`IRC-A/clinic-sample`](https://github.com/IRC-A/clinic-sample).
- **AI Model Stack:** Gemini 3.5 Flash (low-latency triage) and Gemini 3.5 Pro (deep clinical reasoning).
- **Agent Framework:** Google ADK (`google-adk`), Google GenAI SDK (`google-genai`).
- **Cloud Infrastructure:** Google Cloud Platform (GCP) Cloud Run (`BFA_GATEWAY_URL`), Vertex AI / Google AI Studio API.
- **Network & Governance:** IRC-A Protocol, BFA Architecture.
- **Security & Authorization:** PASETO v4.public (Ed25519) Ephemeral DET Tickets, `pyseto`, `cryptography`.
- **Tool Protocol:** FastMCP (`fastmcp`), A2A Standard.
- **User Interface:** Streamlit 1.42+ (`app.py`).

---

## ☁️ Google Cloud Deployment Instructions (Terraform)

The entire fleet (BFA Gateway + Streamlit App & Google ADK Agents) can be provisioned and deployed to **Google Cloud Run** using Terraform IaC:

### Automated GCP Terraform Deployment Script
```bash
./deploy_gcp.sh
```

### Manual Terraform Step-by-Step
```bash
# 1. Build & Push App Container Image to GCP
gcloud builds submit --tag "gcr.io/YOUR_GCP_PROJECT_ID/fortified-healthcare-fleet:latest" -f Dockerfile .

# 2. Initialize and Apply Terraform
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your GCP project_id and GEMINI_API_KEY

terraform init
terraform apply -auto-approve
```

---

## 🚀 Local Spin-Up Instructions

```bash
# 1. Clone repo & activate environment
git clone https://github.com/IRC-A/clinic-sample.git
cd clinic-sample
git checkout hackathon/google-adk

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Run Automated Demo
./run_demo.sh

# 3. Launch Streamlit Web UI
streamlit run app.py
```

---

## 📹 Demo Video Outline (~4 min)

1. **0:00 - 0:45 (Problem & Overview):** Enterprise AI security challenges, prompt injection risks in healthcare, and introduction of **The Fortified Healthcare Fleet** using Google ADK & Gemini 3.5 on Google Cloud.
2. **0:45 - 2:00 (Flow A - Legitimate Ops):** Patient uses Triage Portal to book appointment $\rightarrow$ Specialist Doctor opens Medical Console, reviews EHR history, validates vademecum contraindications, and persists diagnostic evolution with PASETO v4.public DET signature.
3. **2:00 - 3:15 (Flow B - Injection Defense):** Attacker attempts prompt injection via Triage chat to extract confidential EHR records $\rightarrow$ Zero-Trust BFA Gateway blocks channel resolution, neutralizing attack.
4. **3:15 - 4:00 (GCP Proof & Terraform IaC):** Demonstration of Cloud Run production endpoint (`https://irc-a-gateway-hmwmve5bjq-uc.a.run.app`), Terraform deployment pipeline, live DET inspector, and FAISS vector discovery trace.

---

## 📄 License & Credits
Submitted to the **Google All Things Agentic Hackathon** by the **IRC-A Open Protocol Team**. Powered by Google ADK, Gemini 3.5 Flash/Pro, and Google Cloud Platform.
