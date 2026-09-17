from app.generation import answer
import os

os.environ["LLM_PROVIDER"] = "openai"

class MockChunk:
    def __init__(self, id, content):
        self.id = id
        self.content = content
        self.source = "test.txt"
        self.page = 1

chunk = MockChunk("123", "Pond 7 is checked twice daily.")
res = answer("How often is Pond 7 checked?", [(chunk, 0.9)])
print(res)
