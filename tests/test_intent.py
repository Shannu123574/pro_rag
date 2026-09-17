from app.evidence_extractor import compose_deterministic_answer

class MockChunk:
    def __init__(self, id, content):
        self.id = id
        self.content = content

chunk = MockChunk("123", "Pond 7 is checked twice daily. Morning checks measure DO and temperature. Evening checks include turbidity.")
result = compose_deterministic_answer("Why is Pond 7 checked twice daily?", [(chunk, 0.9)])
print("Result for WHY question:", result["answer"])
