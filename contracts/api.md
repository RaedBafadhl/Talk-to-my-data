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
      "sql": "SELECT ... FROM sales JOIN products ... WHERE ...",
      "summary": "Total headphone revenue in the Netherlands last quarter was €142,300, up 8% from the previous quarter.",
      "table": [
        {"month": "2025-10", "revenue": 45200},
        {"month": "2025-11", "revenue": 48900},
        {"month": "2025-12", "revenue": 48200}
      ],
      "chart": {
        "type": "line",
        "x_field": "month",
        "y_field": "revenue"
      }
    }

| Field | Type | Notes |
|---|---|---|
| status | string | `"ok"` |
| sql | string | The generated SQL, shown for transparency/debugging |
| summary | string | Plain-English answer, shown first in the UI |
| table | array of objects | The aggregated result rows |
| chart | object or null | `null` if the result doesn't suit a chart (e.g. a single number) |

---

### Response — clarification needed

    {
      "status": "needs_clarification",
      "clarification_question": "When you say 'sales', do you mean revenue in euros, or units sold?"
    }

The frontend shows `clarification_question` as the assistant's message. The user's next message is sent back with `clarification_answer` filled in and the same `conversation_id`, so the backend can combine it with the original question.

---

### Response — error case

    {
      "status": "error",
      "message": "Something went wrong generating a safe query. Try rephrasing your question."
    }

Used for: SQL generation failure after retries, validation layer rejecting a query as unsafe, or a database execution error. Never expose raw stack traces or internal error details to the frontend.

---

## Rules both sides must follow

- **Read-only, always.** The backend never generates or executes anything other than `SELECT` statements. Any generated SQL containing `INSERT`, `UPDATE`, `DELETE`, `DROP`, or similar is rejected before execution.
- **`chart` is optional.** The frontend must handle `chart: null` gracefully — not every answer needs a visual.
- **Timeouts.** If the backend hasn't responded within 15 seconds, the frontend shows a friendly timeout message rather than hanging indefinitely.
