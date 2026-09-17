# PUBLIC DEMO SCRIPT

1. **Open Application:** Navigate to the public HTTPS URL.
2. **Explain Problem:** "LLMs hallucinate. We need a system mathematically constrained to only output facts backed by citations."
3. **Ingest Evidence:** Upload the sample operational document.
4. **Ask Supported Question:** Query a complex workflow explicitly contained in the document.
5. **Show Retrieved Evidence:** Highlight how the backend retrieves precisely the semantic chunks.
6. **Show Grounded Answer:** Point to the exact generated output.
7. **Show Citation:** Click the [S1] tag to prove the mathematical link back to the ingested text.
8. **Ask Multi-Concept Question:** Ask a question requiring two distinct chunks to answer.
9. **Ask Unsupported Question:** Query a plausible-sounding fact NOT in the document.
10. **Show Abstention:** Show how the system refuses to answer rather than guessing.
11. **Show Contradiction Handling:** Ingest a contradictory document and show how the system detects the conflict.
12. **Explain Provider Fallback:** Explain how the deterministic exact-match fallback engine engages if the LLM API fails, ensuring zero hallucinations even under outage conditions.
