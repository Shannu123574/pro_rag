class MockProvider:
    def __init__(self):
        pass

    def generate(self, system, prompt, **kwargs):
        # Case 10: Perfect
        if 'perfect' in prompt:
            return '{"answer": "Perfect.", "claims": [{"text": "Perfect.", "citations": ["S1"], "support": "supported"}]}'
        # Case 3: Unsupported
        if 'unsupported' in prompt:
            return '{"answer": "Unsupported.", "claims": [{"text": "Unsupported.", "citations": ["S1"], "support": "unsupported"}]}'
        # Case 4: Wrong citation
        if 'wrong' in prompt:
            return '{"answer": "Wrong.", "claims": [{"text": "Wrong.", "citations": ["S99"], "support": "supported"}]}'
        # Case 8: Malformed
        if 'malformed' in prompt:
            return '{"answer": "Malformed"'
        
        return '{"answer": "Default", "claims": []}'
