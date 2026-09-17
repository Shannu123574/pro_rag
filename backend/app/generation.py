import re
import hashlib
from typing import List, Dict, Any, Tuple
from app.config import settings
from app.llm import generate_structured
from app.context_packer import select_generation_evidence
from app.evidence_extractor import compose_deterministic_answer

_generation_cache: Dict[tuple, Any] = {}
ABSTENTION_MESSAGE = "I don't have sufficient evidence in the knowledge base to answer that."

def evidence_is_sufficient(evidence: List[Tuple[Any, float]]) -> bool:
    if not evidence:
        return False
    best_score = float(evidence[0][1])
    if best_score >= 0.0:
        return True
    return False

def format_citations(packed_evidence, valid_citations_set):
    citations = []
    for i, (chunk, score) in enumerate(packed_evidence, 1):
        if i in valid_citations_set:
            citations.append({
                "id": f"S{i}",
                "source": chunk.source,
                "page": chunk.page,
                "score": float(score),
                "text": chunk.content[:200],
                "evidence_support": "strong"
            })
    return citations

def answer(question: str, evidence: List[Tuple[Any, float]]):
    if not evidence_is_sufficient(evidence):
        return {
            "answer": ABSTENTION_MESSAGE,
            "citations": [],
            "confidence": "low",
            "diagnostics": {"abstained": True, "reason": "Insufficient evidence score"}
        }

    packed_evidence = select_generation_evidence(question, evidence)
    
    evidence_parts = []
    for i, (chunk, _) in enumerate(packed_evidence, 1):
        evidence_parts.append(f"[S{i}] {chunk.content}")
    evidence_text = "\n".join(evidence_parts)

    evidence_signature = hashlib.md5(
        "".join(str(chunk.id) for chunk, _ in packed_evidence).encode("utf-8")
    ).hexdigest()
    
    normalized_q = question.lower().strip()
    cache_key = (
        normalized_q, 
        evidence_signature, 
        settings.llm_provider, 
        settings.llm_model
    )
    
    if cache_key in _generation_cache:
        return _generation_cache[cache_key]

    det_result = compose_deterministic_answer(question, packed_evidence)
    
    if det_result.get("conflict"):
        response = {
            "answer": det_result["answer"],
            "citations": [],
            "confidence": "high",
            "diagnostics": {"abstained": True, "reason": "Contradictory evidence detected"}
        }
        _generation_cache[cache_key] = response
        return response

    try:
        result = generate_structured(prompt="", evidence_text=evidence_text, question=question)
    except Exception:
        det_citations = set()
        for c in det_result["citations"]:
            nums = re.findall(r'\d+', c)
            if nums:
                det_citations.add(int(nums[0]))
        response = {
            "answer": det_result["answer"],
            "citations": format_citations(packed_evidence, det_citations),
            "confidence": "high" if det_citations else "low",
            "diagnostics": {
                "abstained": det_result["answer"] == ABSTENTION_MESSAGE, 
                "unsupported_claims": 0,
                "provider": "deterministic",
                "model": "evidence-first"
            }
        }
        _generation_cache[cache_key] = response
        return response
    
    if result.abstain:
        response = {
            "answer": ABSTENTION_MESSAGE,
            "citations": [],
            "confidence": "low",
            "diagnostics": {
                "abstained": True, 
                "unsupported_claims": 0,
                "provider": settings.llm_provider,
                "model": settings.llm_model
            }
        }
        _generation_cache[cache_key] = response
        return response

    valid_citations = set()
    unsupported_claims = 0
    
    for claim in result.claims:
        if claim.support == "unsupported" or not claim.citations:
            unsupported_claims += 1
        else:
            for cit in claim.citations:
                nums = re.findall(r'\d+', cit)
                if nums:
                    idx = int(nums[0])
                    if 1 <= idx <= len(packed_evidence):
                        valid_citations.add(idx)
                    
    if unsupported_claims > 0:
        det_citations = set()
        for c in det_result["citations"]:
            nums = re.findall(r'\d+', c)
            if nums:
                det_citations.add(int(nums[0]))
                
        response = {
            "answer": det_result["answer"],
            "citations": format_citations(packed_evidence, det_citations),
            "confidence": "high" if det_citations else "low",
            "diagnostics": {
                "abstained": det_result["answer"] == ABSTENTION_MESSAGE, 
                "unsupported_claims": 0,
                "provider": "deterministic",
                "model": "evidence-first"
            }
        }
    else:
        response = {
            "answer": result.answer,
            "citations": format_citations(packed_evidence, valid_citations),
            "confidence": "high" if valid_citations else "low",
            "diagnostics": {
                "abstained": False, 
                "unsupported_claims": unsupported_claims,
                "provider": settings.llm_provider,
                "model": settings.llm_model
            }
        }
    
    _generation_cache[cache_key] = response
    if len(_generation_cache) > 1000:
        _generation_cache.pop(next(iter(_generation_cache)))
        
    return response
