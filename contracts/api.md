# API Contract

This defines how the frontend and backend talk to each other. Everyone should build against this shape — the frontend can use fake responses matching this exact structure before the real backend exists, and the backend must return exactly this structure once it's built.

---

## Endpoint: `POST /ask`

### Request

    {
      "question": "What were total headphone sales in the Netherlands last quarter?",
      "conversation_id": "abc123",
      "clarification_answer": null
    }

| Field | Type | Notes |
|---|---|---|
| question | string | The user's question in plain English |
| conversation_id | string | Groups messages into one conversation, so context can be reused |
| clarification_answer | string or null | Set when this message is answering a previous clarification question |

---

### Response — normal case (question answered directly)

    {
      "status": "ok",
      "sql":
