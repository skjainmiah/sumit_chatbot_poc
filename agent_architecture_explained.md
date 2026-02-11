# Agent Architecture: Complete Guide

> Why agents, when to use MCP, when to use A2A, and how to choose between single vs multi-agent.

---

## 1. What is an Agent?

An **AI Agent** is an LLM that goes beyond simple question-answering by having:

| Capability | Description |
|-----------|-------------|
| **Reasoning** | Understands intent and plans multi-step approaches |
| **Tool Use** | Calls external tools (databases, APIs, files) to get real data |
| **Autonomy** | Decides *which* tools to call and *when*, without hardcoded flows |
| **Iteration** | Loops: reasons → acts → observes result → reasons again until done |

An agent is essentially: **LLM + Tools + Loop**

---

## 2. Why Do We Need Agents? (With vs Without)

### WITHOUT an Agent (Plain LLM)

```
User: "How many ships arrived at Mumbai port last week?"

Plain LLM Response:
  "I don't have access to your database, but typically
   you could query your port management system..."
```

**Problems without agents:**
- LLM has **no access** to your databases, APIs, or real-time data
- Can only respond from training data (stale, generic)
- Cannot execute actions (insert records, send emails, trigger workflows)
- Every integration must be **hardcoded** by a developer (if/else chains)
- No dynamic decision-making — the system can only do what was pre-programmed

### WITH an Agent

```
User: "How many ships arrived at Mumbai port last week?"

Agent thinks:
  → I need to query the cargo_operations database
  → I'll use the SQL tool to run a query
  → SELECT COUNT(*) FROM vessel_arrivals
     WHERE port='Mumbai' AND arrival_date >= '2026-02-04'
  → Result: 47 vessels

Agent Response:
  "47 ships arrived at Mumbai port in the last week.
   The busiest day was Wednesday with 12 arrivals."
```

### Comparison Table

| Aspect | Without Agent | With Agent |
|--------|--------------|------------|
| Data access | Training data only | Live databases, APIs, files |
| Accuracy | Often hallucinated | Grounded in real data |
| Actions | Cannot perform any | Can execute workflows |
| Adaptability | Fixed responses | Dynamic reasoning per query |
| Maintenance | Hardcoded logic for every case | Agent figures out the approach |
| User experience | Generic answers | Specific, actionable answers |

---

## 3. What is MCP (Model Context Protocol)?

**MCP** is a **standardized protocol** that defines how an agent connects to external tools and data sources.

Think of it as **USB for AI** — just like USB provides a standard way to plug any device into a computer, MCP provides a standard way to plug any tool into an agent.

### MCP Architecture

```
┌──────────┐         ┌────────────┐         ┌──────────────┐
│  Agent   │ ◄─MCP─► │ MCP Server │ ◄─────► │  Database    │
│  (Host)  │         │ (Adapter)  │         │  (Resource)  │
└──────────┘         └────────────┘         └──────────────┘
```

**Key components:**
- **MCP Host**: The agent/application that needs tool access
- **MCP Server**: A lightweight adapter that exposes a tool's capabilities in a standardized format
- **MCP Client**: Built into the host, speaks the MCP protocol

### Why MCP Matters

**Before MCP:**
```
Agent ──custom code──► PostgreSQL
Agent ──different code──► REST API
Agent ──another format──► File System
Agent ──yet another──► Web Search
(Every tool needs custom integration code)
```

**After MCP:**
```
Agent ──MCP──► PostgreSQL MCP Server  ──► PostgreSQL
Agent ──MCP──► API MCP Server         ──► REST API
Agent ──MCP──► Filesystem MCP Server  ──► File System
Agent ──MCP──► Search MCP Server      ──► Web Search
(One protocol, any tool)
```

### Where is MCP Used?

| Architecture | MCP Used? | How |
|-------------|-----------|-----|
| **Single Agent** | Yes | The single agent connects to all its tools via MCP |
| **Multi-Agent** | Yes | Each specialized agent connects to its own tools via MCP |

**MCP is used in BOTH architectures.** Every agent that needs to access external tools uses MCP regardless of whether it's the only agent or one of many.

---

## 4. What is A2A (Agent-to-Agent Protocol)?

**A2A** is Google's open protocol that enables **agents to communicate with each other** — discover capabilities, delegate tasks, exchange results, and coordinate work.

### A2A Architecture

```
┌──────────────┐                    ┌──────────────┐
│  Agent A     │ ◄───A2A Protocol──►│  Agent B     │
│  (Client)    │    Task Cards      │  (Server)    │
│              │    Status Updates  │              │
│              │    Artifacts       │              │
└──────────────┘                    └──────────────┘
```

**Key concepts:**
- **Agent Card**: A JSON file describing what an agent can do (like a resume)
- **Task**: A unit of work sent from one agent to another
- **Artifact**: The output/result returned by the receiving agent
- **Streaming**: Real-time updates on task progress

### Where is A2A Used?

| Architecture | A2A Used? | Why |
|-------------|-----------|-----|
| **Single Agent** | **No** | Only one agent exists — no agent-to-agent communication needed |
| **Multi-Agent** | **Yes** | Multiple agents need to discover, delegate, and coordinate with each other |

**A2A is ONLY for multi-agent architectures.** It solves the problem of "how do agents talk to each other?"

---

## 5. Single Agent Architecture

> See: `single_agent_architecture.svg`

### When to Use Single Agent

- **Focused domain**: Your chatbot deals with one domain (e.g., database queries)
- **Simple workflows**: Tasks can be completed in a linear sequence
- **Limited tool set**: Agent needs 3-5 tools maximum
- **Lower complexity**: You don't need specialized reasoning for different sub-tasks
- **Faster development**: Easier to build, test, and debug

### How It Works

```
User Query
    │
    ▼
┌─────────────────────────────┐
│     Single LLM Agent        │
│  ┌────────────────────────┐ │
│  │ 1. Understand query    │ │
│  │ 2. Plan approach       │ │
│  │ 3. Call tool via MCP   │ │
│  │ 4. Process result      │ │
│  │ 5. Respond to user     │ │
│  └────────────────────────┘ │
└─────────────────────────────┘
    │ MCP
    ▼
[Database] [API] [Files] [Search]
```

### Protocols Used
- **MCP**: Yes — to connect agent to tools
- **A2A**: No — only one agent, no inter-agent communication needed

### Real Example (Your Chatbot)

Your current Sumit Chatbot uses a **single-agent architecture**:
- One LLM agent handles all user queries
- Connects to PostgreSQL and MSSQL databases via tool calling
- Generates SQL, executes queries, and returns formatted results

---

## 6. Multi-Agent Architecture

> See: `multi_agent_architecture.svg`

### When to Use Multi-Agent

- **Complex workflows**: Tasks require multiple specialized skills
- **Domain diversity**: Different parts of a task need different expertise
- **Parallelization**: Sub-tasks can run simultaneously for speed
- **Scalability**: You want to add new capabilities without modifying existing agents
- **Reliability**: Specialized agents are more accurate than one generalist
- **Large tool sets**: Too many tools for one agent to manage effectively (10+)

### How It Works

```
User Query
    │
    ▼
┌─────────────────────┐
│  Orchestrator Agent  │  ← Plans & delegates
└─────────────────────┘
    │ A2A Protocol
    ├──────────────┬──────────────┬──────────────┐
    ▼              ▼              ▼              ▼
┌────────┐  ┌──────────┐  ┌───────────┐  ┌──────────┐
│  SQL   │  │ Research │  │ Analytics │  │  Action  │
│ Agent  │  │  Agent   │  │   Agent   │  │  Agent   │
└────────┘  └──────────┘  └───────────┘  └──────────┘
    │MCP        │MCP          │MCP           │MCP
    ▼           ▼             ▼              ▼
 [Database]  [Web/Docs]   [Charts/BI]   [External APIs]
```

### Protocols Used
- **MCP**: Yes — each agent connects to its specialized tools via MCP
- **A2A**: Yes — orchestrator delegates to specialists and collects results

### Real Example

A shipping analytics platform might use:
1. **Orchestrator**: Receives "Give me a full report on Q1 fleet performance"
2. **SQL Agent** (via A2A): Queries cargo and maintenance databases
3. **Analytics Agent** (via A2A): Processes the data, creates charts
4. **Research Agent** (via A2A): Pulls market benchmarks from the web
5. **Report Agent** (via A2A): Compiles everything into a formatted report

---

## 7. MCP vs A2A — Summary Comparison

| Aspect | MCP | A2A |
|--------|-----|-----|
| **Purpose** | Agent ↔ Tool connection | Agent ↔ Agent communication |
| **Analogy** | USB port (plug in any device) | HTTP for agents (agents talk to agents) |
| **Single Agent** | Yes (required) | No (not needed) |
| **Multi-Agent** | Yes (each agent uses it) | Yes (required for coordination) |
| **Who created it** | Anthropic | Google |
| **What it standardizes** | Tool discovery & invocation | Agent discovery, task delegation, results |
| **Direction** | Agent calls a tool | Agent delegates to another agent |
| **Complementary?** | Yes — MCP and A2A work together in multi-agent systems |

### How They Work Together

```
                    A2A (agent-to-agent)
Orchestrator  ◄──────────────────────────►  SQL Agent
                                               │
                                               │ MCP (agent-to-tool)
                                               ▼
                                           PostgreSQL
```

- **A2A** handles the communication between the Orchestrator and the SQL Agent
- **MCP** handles the SQL Agent's connection to the actual PostgreSQL database
- They operate at **different layers** and are **complementary, not competing**

---

## 8. Decision Framework: Which Architecture to Choose?

```
START
  │
  ├─ Is the task focused on a single domain?
  │   ├─ YES ──► Can one agent handle all tools (< 5-7)?
  │   │           ├─ YES ──► SINGLE AGENT + MCP
  │   │           └─ NO  ──► MULTI-AGENT + MCP + A2A
  │   └─ NO ───► MULTI-AGENT + MCP + A2A
  │
  ├─ Does the task require parallel processing?
  │   ├─ YES ──► MULTI-AGENT + MCP + A2A
  │   └─ NO  ──► SINGLE AGENT + MCP (start simple)
  │
  └─ Will the system grow to add new capabilities frequently?
      ├─ YES ──► MULTI-AGENT + MCP + A2A (each new capability = new agent)
      └─ NO  ──► SINGLE AGENT + MCP
```

### Rule of Thumb

> **Start with a single agent. Move to multi-agent only when complexity demands it.**

Single agent is simpler to build, debug, and maintain. Only add the complexity of multi-agent when you genuinely need specialization, parallelization, or scalability.

---

## 9. Quick Reference

| You Need... | Use |
|-------------|-----|
| An LLM that queries your database | Single Agent + MCP |
| A chatbot with web search + DB + file access | Single Agent + MCP |
| A system where different AI specialists collaborate | Multi-Agent + MCP + A2A |
| To add new AI capabilities without changing existing ones | Multi-Agent + MCP + A2A |
| Maximum simplicity and fastest development | Single Agent + MCP |
| Enterprise-scale AI orchestration | Multi-Agent + MCP + A2A |
