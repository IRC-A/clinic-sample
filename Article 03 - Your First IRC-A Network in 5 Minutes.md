---
title: "Your First IRC-A Network in 5 Minutes: A Multi-Agent Medical Clinic with BFA Gateway, MCP and Streamlit"
published: false
description: "Hands-on tutorial: spin up a BFA Gateway, register a Triage agent, specialist agents and an MCP booking server, and watch them discover each other semantically."
tags: ai, agents, mcp, python
series: "IRC-A: Agents on the Wire"
cover_image:
canonical_url:
---


# Hands-on tutorial: spin up a BFA Gateway, register a Triage agent, specialist agents and an MCP booking server, and watch them discover each other semantically."

In the [previous article](#) we migrated a real project from n8n to IRC-A and saw the bugs that made the framework stronger. Now it's your turn to build.

Most "multi-agent" demos are one LLM with a long prompt pretending to be a team. We're going to build the real thing: **a medical clinic where independent agents — a Triage agent, three specialists, and an appointment-booking MCP server — discover each other through a BFA Gateway and cooperate without knowing one another exists.**

By the end you'll have:

- A **BFA Gateway** running (semantic routing + cryptographic registration).
- A **Main Agent** with session memory, context reduction and response synthesis.
- A **Triage Agent** that classifies patient intents and routes to the right specialty.
- **Specialist Agents** (Pediatrics, Oncology, General Medicine).
- A mock **MCP server** for booking appointments.
- A **Streamlit UI** to talk to the whole network.

No agent knows any other agent. No graphs, no edges, no hardcoded endpoints. Let's go.

---

## Requirements

All you need is Docker (for the Gateway) and Python with the SDK plus its companions:

```bash
pip install bfa-irc-a-sdk==0.3.0.dev14 pyseto cryptography pydantic httpx
```

- **`bfa-irc-a-sdk`** — the SDK: `BFAAgent`, `BFAInteractiveAgent`, `BFAMCP` and friends.
- **`pyseto`** — PASETO v4.public tokens (the DETs used for delegated execution).
- **`cryptography`** — Ed25519 keys for the registration handshake and token signatures.
- **`pydantic`** — schema validation for agent cards and tool I/O.
- **`httpx`** — async HTTP client for P2P invocation between agents and tools.

---

## Step 0 — The BFA Gateway (the routing core)

The fastest way to run the coordination server is Docker:

```bash
docker pull sandrog77/bfa-gateway
docker run -d -p 8000:8000 --name bfa-gateway sandrog77/bfa-gateway
```

That's it. The Gateway is now ready to accept agent and MCP registrations via a cryptographic handshake, and to route natural-language queries semantically (FAISS vector search over capability metadata — zero LLM tokens spent on routing).

> **Note:** the Gateway holds no business logic and no database connections. It's a semantic registry + security token issuer. Execution happens peer-to-peer between agents.

### Embeddings: mock by default, real when you want them

One detail you'll notice the moment the container boots: the Gateway prints a startup diagnostic telling you exactly which credentials it found and which embedding engine it's using:

```
=== [BFA GATEWAY STARTUP - ENVIRONMENT & CREDENTIALS DIAGNOSTIC] ===
🔹 OPENAI_API_KEY        : <NOT SET>
🔹 GOOGLE_API_KEY        : <NOT SET>
🔹 TAVILY_API_KEY        : <NOT SET>
🔹 LANGSMITH_API_KEY     : <NOT SET>
🔹 LLM_PROVIDER          : <NOT SET>
🔹 BFA_USE_MOCK_EMBEDDINGS: true
🔹 BFA_USE_OPENAI_EMBEDDINGS: false
🔹 BFA_REGISTRY_DB_PATH  : bfa_registry_db.json
```

**Out of the box, the Gateway runs with mocked embeddings.** No API key, no cost, no external calls — the FAISS index still works, which is perfect for this 5-minute quickstart and for CI/offline environments. The trade-off: mock embeddings don't capture real semantic similarity, so routing relies on closer keyword matches.

When you're ready for real semantic routing, pass your OpenAI key to the container and flip the flag:

```bash
docker run -d -p 8000:8000 \
  -e OPENAI_API_KEY=sk-your-key-here \
  -e BFA_USE_OPENAI_EMBEDDINGS=true \
  --name bfa-gateway sandrog77/bfa-gateway
```

For this tutorial the mock is fine — everything below works exactly the same either way.

---

## The architecture at a glance

```
┌────────────┐      ┌──────────────────┐
│ Streamlit  │─────▶│   Main Agent     │  (memory, context
│    UI      │◀─────│ (BFAInteractive) │   reduction, synthesis)
└────────────┘      └────────┬─────────┘
                             │ delegate_task
                             ▼
                    ┌─────────────────┐
                    │   BFA Gateway   │  semantic discovery (FAISS)
                    └────────┬────────┘
              ┌──────────────┼───────────────┐
              ▼              ▼               ▼
      ┌────────────┐  ┌─────────────┐  ┌──────────────┐
      │   Triage   │  │ Specialists │  │  Booking MCP │
      │   Agent    │  │ (Peds/Onc/  │  │ (@mcp.tool)  │
      │            │  │  General)   │  │              │
      └────────────┘  └─────────────┘  └──────────────┘
```

Every box registers itself with the Gateway. Every box can be replaced, removed, or rewritten in another language — the network won't notice.

---

## Step 1 — The Main Agent (`main_agent.py`)

The Main Agent is the only component the user talks to. It inherits from `BFAInteractiveAgent`, which gives it session memory and Gateway delegation out of the box:

```python
from bfa_sdk import BFAInteractiveAgent

class MainAgent(BFAInteractiveAgent):
    def __init__(self):
        super().__init__(
            agent_id="main_agent",
            name="Clinic Receptionist",
            # NOTE: description is the ROUTING CONTRACT — keep it
            # narrow so the Gateway never routes medical questions here
            description=(
                "Front-desk conversational agent of the clinic. "
                "Greets patients, keeps the conversation flowing, "
                "and delegates medical questions and bookings to the network."
            ),
            tags=["reception", "chat", "front-desk"],
        )
```

Four things happen inside this agent, and each one is deliberate:

**1. Registration.** On startup, the agent performs a cryptographic handshake with the Gateway and lands in the FAISS index. From that moment, it's discoverable.

**2. Session memory (`MemoryStack`).** The agent keeps the dialogue history per session, so follow-ups like *"and for my daughter?"* work.

**3. Context reduction.** Before delegating, the agent uses a quick LLM pass to compress the conversational history into one clean, atomic query:

```python
# NOT the whole chat history — just the distilled intent:
reduced_query = await self.reduce_context(user_message)
# "my daughter has had a fever since yesterday, she's 4"
# becomes -> "pediatric consultation for fever in 4-year-old child"
```

This is crucial for two reasons: **routing quality** (FAISS works better on clean intent than on messy conversation) and **token cost** (you never drag the full history downstream).

**4. Delegation + synthesis.** The reduced query goes to the Gateway via `delegate_task`; whatever specialist or tool answers, the Main Agent re-wraps it using the session history into an empathetic, human-readable response:

```python
specialist_reply = await self.delegate_task(reduced_query)
final_reply = await self.synthesize(user_message, specialist_reply)
```

The user talks to one agent. The network does the rest.

---

## Step 2 — The Triage Agent (`triage.py`)

Triage is the first clinical filter: it interprets the patient's need and decides the specialty. It inherits from `BFAAgent` (with an `AsyncOpenAI` brain):

```python
from bfa_sdk import BFAAgent
from openai import AsyncOpenAI

class TriageAgent(BFAAgent):
    def __init__(self):
        super().__init__(
            agent_id="triage_agent",
            name="Triage Agent",
            description=(
                "Evaluates a patient's request in natural language and "
                "determines the correct medical specialty: pediatrics, "
                "oncology, or general medicine."
            ),
            tags=["triage", "classification", "routing", "medical"],
            examples=[
                "my 5-year-old has a rash",
                "I need an oncology follow-up",
                "I have a persistent cough",
            ],
        )
        self.llm = AsyncOpenAI()

    async def handle(self, query: str) -> str:
        response = await self.llm.chat.completions.create(
            model="gpt-4.1-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": TRIAGE_SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
        )
        return response.choices[0].message.content
```

Two design notes here:

- **The system prompt must contain a clear inventory of available specialties.** Triage can only route to what it knows exists. An ambiguous inventory means misrouted patients — this is the same "routing contract" lesson from Article 02, one level down.
- `temperature=0`: classification is not the place for creativity.

---

## Step 3 — A Specialist Agent (`pediatrics.py`)

Specialists follow the exact same pattern. The only things that change are the identity metadata and the system prompt:

```python
class PediatricsAgent(BFAAgent):
    def __init__(self):
        super().__init__(
            agent_id="pediatrics_agent",
            name="Pediatrics Specialist",
            description=(
                "Pediatric consultation agent. Handles health questions "
                "about babies, children and teenagers: symptoms, "
                "development, vaccination, nutrition."
            ),
            tags=["pediatrics", "children", "health"],
            examples=[
                "my baby has a fever",
                "vaccination schedule for a 2-year-old",
            ],
        )
```

Same `handle()`, different system prompt (pediatric-focused, with clear scope limits and a "this is not a diagnosis" guardrail).

> **🎯 Your turn:** implement `oncology.py` and `general_medicine.py` following this pattern. If you can copy the pattern twice without opening the docs, the SDK is doing its job. Full working code is in the repo (link at the end).

---

## Step 4 — The Booking MCP Server (`booking_mcp.py`)

Agents talk. Tools *do*. For appointment booking we expose a tool server with `BFAMCP` and the `@mcp.tool` decorator:

```python
from bfa_sdk import BFAMCP

mcp = BFAMCP(
    server_id="booking_mcp",
    name="Appointment Booking",
    description="Books, reschedules and cancels clinic appointments.",
    tags=["booking", "appointments", "schedule"],
)

@mcp.tool(
    name="book_appointment",
    description="Book a medical appointment for a given specialty and date.",
    tags=["booking", "create"],
    examples=["book a pediatrics appointment for tomorrow morning"],
)
async def book_appointment(specialty: str, date: str, patient_name: str) -> dict:
    # mock logic — swap in your real scheduling system here
    return {"status": "confirmed", "specialty": specialty,
            "date": date, "patient": patient_name}
```

Register it with the Gateway (note: the **root base URL**, the Gateway discovers the endpoints itself):

```bash
curl -X POST "http://localhost:8000/register/mcp?url=http://localhost:8003&channels=%23clinic"
```

From this second on, any agent on the network can discover and call `book_appointment` semantically — with a signed DET (Delegated Execution Token) attached to the authorization. Nobody configured anything.

---

## Step 5 — The Streamlit UI

The UI is deliberately thin: Streamlit talks to the Main Agent over HTTP/JSON-RPC, renders the chat, and nothing else. All intelligence lives in the network. Swap Streamlit for WhatsApp, a web app, or a voice interface — the network doesn't care. That's the point.

---

## What you just built

- **A network, not a workflow.** Add a dermatology agent tomorrow: write it, register it, done. No rewiring.
- **Semantic discovery for free.** FAISS routes intent; no LLM tokens burned on routing.
- **Security by default.** Cryptographic handshake on registration, signed DETs on every delegation.
- **A cheap bill.** As we saw in Article 02, this pattern keeps full interactions in the hundreds of tokens.

👉 **Full working project:** [github.com/IRC-A/clinic-sample](https://github.com/IRC-A/clinic-sample)

In the next article we go under the hood: **how the FAISS semantic routing actually works**, and why agent descriptions are the real routing contract.

---

*Building something with agents? Try the clinic sample, break it, and tell me what broke — that's how this framework gets better. Comments open.* 🏥📡
