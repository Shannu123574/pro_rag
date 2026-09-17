# RELEASE NOTES (v1.0.0)

## Current Capabilities
- **Evidence-First Generation:** Validates generated claims against retrieved evidence and rejects unsupported output under the evaluated release tests.
- **Strict Structural Validation:** Applies programmatic claim and citation validation before returning the response.
- **Deterministic Fallback:** Falls back to a deterministic exact-match engine based on lexical relevance if the remote LLM fails.
- **Contradiction Handling:** Detects conflicting retrieved chunks to avoid generating contradictory answers.

## Provider
- Utilizes gpt-4.1-mini via OpenAI for fluid multi-concept synthesis.

## Security Behavior
- **Prompt Injection:** Unsupported claims injected by adversarial prompts are rejected by the validation layer under the tested conditions.
- **No Database Exposure:** PostgreSQL is strictly isolated via Docker networks / Render private networking.

## Deployment State
- **Local Docker:** VERIFIED
- **GitHub:** VERIFIED
- **Render configuration:** VERIFIED
- **Public Render deployment:** NOT DEPLOYED
- **HTTPS public deployment:** NOT TESTED

## Known Limitations
- The deterministic fallback has strict lexical boundaries and may abstain from valid answers if the lexical semantic intent is poorly aligned.
- Public deployment is pending external manual authentication via the Render dashboard.
