import sys; sys.path.append('.')
from tests.dataset import EVAL_DATASET
from app.generation import answer
from app.retrieval import retrieve_with_diagnostics

for case in EVAL_DATASET:
    q = case['question']
    chunks, _ = retrieve_with_diagnostics(q)
    ans = answer(q, chunks)
    print(f'Q: {q}')
    print(f'A: {ans["answer"]}')
