# POST-DEPLOY VERIFICATION

Execute these exact tests once the URL is live.

| Test | Expected | Actual | Status |
| :--- | :--- | :--- | :--- |
| public URL | Opens in browser | | |
| HTTPS | Valid certificate | | |
| frontend | UI loads fully | | |
| /health | Returns 200 OK | | |
| /ready | Returns 200 OK | | |
| ingestion | Demo document indexed | | |
| supported question | Grounded answer returned | | |
| citation | Valid [S1] mapping | | |
| multi-concept | Accurate combined facts | | |
| unsupported query | Graceful abstention | | |
| contradiction | Conflict-safe response | | |
| provider | OpenAI returns valid data | | |
| fallback | Deterministic engine kicks in if provider fails | | |
| browser refresh | UI state refreshes safely | | |
