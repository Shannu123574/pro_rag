from app.llm import generate_structured
import os

os.environ["LLM_PROVIDER"] = "openai"
try:
    result = generate_structured("Answer the following", "The pond is checked at 9 AM.", "When is the pond checked?")
    print("Provider:", os.environ.get("LLM_PROVIDER"))
    print("Model:", os.environ.get("LLM_MODEL"))
    print("Status: SUCCESS")
    print("Output:", result)
except Exception as e:
    print("Provider:", os.environ.get("LLM_PROVIDER"))
    print("Model:", os.environ.get("LLM_MODEL"))
    print("Status: BLOCKED")
    print("Exception:", str(e))
