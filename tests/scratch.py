from app.generation import get_generator, build_evidence
from app.retrieval import retrieve
from app.context_packer import select_generation_evidence

questions = [
    "Why should I add agricultural lime to the pond?",
    "Is the pH supposed to fluctuate by more than 0.5 units in a day?",
    "My shrimp are acting lethargic and dying suddenly with marks on their shells. What virus might this be?",
    "What is the minimum acceptable dissolved O2 level?",
    "I am a new farm operator trying to figure out how to feed adult shrimp. Can you tell me exactly what percentage of protein the pellets should have and the specific times I am supposed to feed them every single day?"
]

generator = get_generator()

for question in questions:
    evidence = retrieve(question)
    packed_evidence = select_generation_evidence(question, evidence)
    context = build_evidence(packed_evidence)
    sanitized_context = context.replace("<", "&lt;").replace(">", "&gt;")
    
    prompt = f"Answer the following question using the provided evidence. You must quote the exact words from the evidence that answer the question.\n\nEvidence:\n{sanitized_context}\n\nQuestion: {question}\nAnswer:"
    
    result = generator(prompt, max_new_tokens=256, do_sample=False)
    print(f"Q: {question}")
    print(f"A: {result[0]['generated_text'].strip()}\n")
