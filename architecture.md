# Architecture

```mermaid
flowchart TD
    U[User goal] --> A[Agent loop]
    M[(Long-term memory<br/>memory.json)] -->|recall| A
    A -->|messages + tool specs| L[LLM<br/>Claude API]
    L -->|text / tool_use| A
    A -->|validated call| R[Tool registry]
    R --> T1[calculator]
    R --> T2[read/write/list files<br/>sandboxed workspace]
    R --> T3[http_get<br/>public hosts only]
    R --> T4[remember / recall]
    R --> T5[finish]
    R -->|observation| A
    A -->|events| TR[(trace.jsonl)]
    T4 --> M
    T5 --> OUT[Final answer]
    A -->|max_steps hit| STOP[Safe stop]
```

## Guardrails
| Risk | Control |
|---|---|
| Runaway loops | `max_steps` hard cap |
| File escape | `realpath` check confined to `workspace/` |
| SSRF | `http_get` blocks private/loopback/link-local IPs |
| Code injection | calculator uses AST whitelist, no `eval` |
| Tool misuse | `allowed_tools` allow-list |
| Tool crashes | errors returned as observations so the model can recover |
