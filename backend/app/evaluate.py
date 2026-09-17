import json
from pathlib import Path
from app.retrieval import retrieve

def evaluate(path="data/eval/questions.jsonl"):
    rows=[json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]
    hits=0
    for row in rows:
        sources={c.source for c,_ in retrieve(row["question"])}
        hits += row.get("expected_source") in sources
    score=hits/max(1,len(rows))
    print({"retrieval_recall_at_k":score,"n":len(rows)})
    return score
