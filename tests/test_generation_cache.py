import sys; sys.path.append('.')
from unittest.mock import patch
from app.generation import answer, _generation_cache

class MockChunk:
    def __init__(self, id, source, content, page):
        self.id = id
        self.source = source
        self.content = content
        self.page = page

def test_cache_hit_and_miss():
    _generation_cache.clear()
    q = "test query"
    
    chunk1 = MockChunk(id="chunk_1", source="doc1", content="evidence text", page=1)
    chunk2 = MockChunk(id="chunk_2", source="doc2", content="evidence text 2", page=1)
    
    evidence = [(chunk1, 0.9)]
    
    with patch("app.generation.generate_structured") as mock_generate:
        from app.llm import GenerationResult, Claim
        mock_generate.return_value = GenerationResult(
            answer="generated answer",
            claims=[Claim(text="generated answer", citations=["S1"], support="direct")],
            abstain=False,
            reason=None
        )
        res1 = answer(q, evidence)
        assert res1["answer"] == "generated answer"
        assert mock_generate.call_count == 1
        
        res2 = answer(q, evidence)
        assert res2["answer"] == "generated answer"
        assert mock_generate.call_count == 1
        
        res3 = answer("different question", evidence)
        assert res3["answer"] == "generated answer"
        assert mock_generate.call_count == 2
        
        evidence2 = [(chunk2, 0.8)]
        res4 = answer(q, evidence2)
        assert res4["answer"] == "generated answer"
        assert mock_generate.call_count == 3
