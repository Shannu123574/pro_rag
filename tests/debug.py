from fastapi.testclient import TestClient
from app.main import app
import time

client = TestClient(app)
with client:
    for _ in range(60):
        try:
            if client.get("/health").json()["status"] == "ok":
                break
        except Exception:
            pass
        time.sleep(1)

res = client.post("/query", json={"question": "Why should I add agricultural lime to the pond?"})
print(res.json().get("diagnostics", {}).get("best_retrieval_score", None))
