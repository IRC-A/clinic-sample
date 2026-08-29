# The Fortified Healthcare Fleet: Extending Google ADK with IRC-A Zero-Trust Runtime Governance on Google Cloud

[![Google ADK](https://img.shields.io/badge/Google%20ADK-Gemini%203.5-34A853?style=for-the-badge&logo=google)](https://ai.google.dev)
[![Terraform IaC](https://img.shields.io/badge/Terraform-GCP%20Cloud%20Run-7B42BC?style=for-the-badge&logo=terraform)](https://www.terraform.io)
[![IRC-A Protocol](https://img.shields.io/badge/IRC--A-Zero--Trust%20Runtime-EA4335?style=for-the-badge)](https://github.com/IRC-A/clinic-sample)

Submitted to the **Google All Things Agentic Hackathon** under the track: **"The Fortified Enterprise Fleet"** (Corporate discovery, Zero-Trust runtime access, policy enforcement, Model Armor, and execution isolation).

---

## 📌 Technical Overview

High-stakes corporate environments—such as clinical healthcare, financial systems, and enterprise legal ops—demand strict runtime access control and deterministic security bounds for autonomous AI agent fleets. While LLM-driven agents powered by **Google ADK** provide remarkable cognitive reasoning, raw agent execution without network-level isolation risks prompt injection attacks, unauthorized scope creep, and data leakage.

**The Fortified Healthcare Fleet** addresses this by pairing **Google ADK (Gemini 3.5 Flash & Gemini 3.5 Pro)** with the **IRC-A (Internet Relay Chat for Agents)** protocol and **BFA (Backend for Agents)** design pattern deployed on **Google Cloud Platform (GCP)** via **Terraform Infrastructure as Code (IaC)**.

### Official Repositories
- **BFA Gateway Infrastructure:** [`https://github.com/IRC-A/bfa-gateway`](https://github.com/IRC-A/bfa-gateway)
- **Fortified Healthcare Fleet App:** [`https://github.com/IRC-A/clinic-sample`](https://github.com/IRC-A/clinic-sample)

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

## ⚡ Key Architectural Concepts

- **Dual-View Web Interface (`app.py`):**
  - **Patient Triage Portal:** Allows patients to query medical specialties, check on-call doctors, and book appointments via Gemini 3.5 Flash.
  - **Specialist Medical Console:** Empowers licensed doctors to consult EHR clinical records, evaluate drug interactions in the vademecum, and record diagnostic evolutions via Gemini 3.5 Pro.
- **Zero-Trust Live Audit Panel:** Real-time visual sidebar logging active agent identities, channel permission masks, GCP FAISS semantic discovery traces, and PASETO v4.public ephemeral DET ticket inspection.
- **Prompt Injection & Scope Creep Neutralization:** Indirect prompt injections attempting to extract confidential medical records through public triage channels are automatically blocked by GCP BFA Gateway channel masking.
- **Non-Repudiation Audit Logs:** Clinical evolutions are written with SHA-256 parameter digests and signed PASETO v4 tickets.

---

## 🛠️ Infrastructure as Code (Terraform) & Tech Stack

- **Infrastructure as Code:** Terraform (`terraform/main.tf`, `variables.tf`, `outputs.tf`).
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

---

## 📄 License & Credits
Submitted to the **Google All Things Agentic Hackathon** by the **IRC-A Open Protocol Team**. Powered by Google ADK, Gemini 3.5 Flash/Pro, and Google Cloud Platform.
