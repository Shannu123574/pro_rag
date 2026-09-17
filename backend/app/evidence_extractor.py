import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class EvidenceClaim(BaseModel):
    claim_text: str
    source_id: str
    chunk_id: str
    numeric_entities: List[Dict[str, Any]] = []

def extract_numeric_entities(text: str) -> List[Dict[str, Any]]:
    entities = []
    pattern = r'(\d+(?:\.\d+)?)\s*([a-zA-Z/°%]+)'
    matches = re.finditer(pattern, text)
    for match in matches:
        value_str = match.group(1)
        unit = match.group(2).lower()
        entities.append({"value": float(value_str), "unit": unit, "sentence": text.lower()})
    return entities

def extract_claims_from_chunk(chunk_content: str, chunk_id: str, source_idx: int) -> List[EvidenceClaim]:
    claims = []
    sentences = re.split(r'(?<=[.!?])\s+', chunk_content.strip())
    for sent in sentences:
        sent = sent.strip()
        if len(sent) > 5:
            claims.append(EvidenceClaim(
                claim_text=sent, source_id=f"S{source_idx}", chunk_id=str(chunk_id),
                numeric_entities=extract_numeric_entities(sent)
            ))
    return claims

def get_semantic_context(text: str) -> set:
    words = set(re.findall(r'\w+', text))
    stop_words = {'the', 'is', 'for', 'be', 'should', 'of', 'in', 'at', 'a', 'to', 'and', 'are', 'was', 'were'}
    return words - stop_words

def detect_conflicts(claims: List[EvidenceClaim]) -> Optional[str]:
    unit_map = {}
    for claim in claims:
        for ent in claim.numeric_entities:
            unit = ent["unit"]
            if unit not in unit_map:
                unit_map[unit] = []
            unit_map[unit].append((ent["value"], ent["sentence"], claim.source_id))
            
    for unit, entries in unit_map.items():
        if len(entries) > 1:
            for i in range(len(entries)):
                for j in range(i + 1, len(entries)):
                    val1, ctx1, src1 = entries[i]
                    val2, ctx2, src2 = entries[j]
                    if val1 != val2:
                        sem1 = get_semantic_context(ctx1)
                        sem2 = get_semantic_context(ctx2)
                        overlap = sem1.intersection(sem2)
                        diff1 = sem1 - sem2
                        diff2 = sem2 - sem1
                        
                        critical_differences = False
                        conditions = {'summer', 'winter', 'morning', 'evening', '1', '2', 'length', 'width', 'salinity', 'ph'}
                        if (diff1.intersection(conditions)) or (diff2.intersection(conditions)):
                            critical_differences = True
                            
                        if len(overlap) >= 2 and not critical_differences:
                            return f"Conflicting evidence found: [{src1}] states {val1} {unit}, but [{src2}] states {val2} {unit}."
    return None

def detect_intent(question: str) -> str:
    q = question.lower()
    if "why" in q or "reason" in q or "cause" in q:
        return "WHY"
    if "how" in q and not "how many" in q and not "how much" in q and not "how long" in q:
        return "HOW"
    if "how many" in q or "how much" in q or "what is the" in q and re.search(r'\b(level|amount|value|concentration|temperature)\b', q):
        return "NUMBER"
    if "when" in q or "time" in q or "how long" in q:
        return "WHEN"
    if "where" in q or "location" in q:
        return "WHERE"
    return "WHAT"

def claim_satisfies_intent(claim_text: str, intent: str, claim_has_numbers: bool) -> bool:
    c = claim_text.lower()
    if intent == "WHY":
        return any(word in c for word in ['because', 'due to', 'since', 'causes', 'prevents', 'to', 'therefore', 'results in'])
    if intent == "HOW":
        return any(word in c for word in ['by', 'using', 'through', 'step', 'method', 'process', 'procedure', 'requires'])
    if intent == "NUMBER":
        return claim_has_numbers
    if intent == "WHEN":
        return any(word in c for word in ['during', 'after', 'before', 'morning', 'evening', 'time', 'date', 'daily', 'weekly', 'monthly', 'days', 'hours', 'minutes'])
    if intent == "WHERE":
        return any(word in c for word in ['in', 'at', 'on', 'location', 'pond', 'facility', 'tank'])
    return True

def compose_deterministic_answer(question: str, evidence_chunks: List[Any]) -> Dict[str, Any]:
    all_claims = []
    for i, (chunk, score) in enumerate(evidence_chunks, 1):
        all_claims.extend(extract_claims_from_chunk(chunk.content, chunk.id, i))
        
    question_words = set(re.findall(r'\w+', question.lower())) - {'what', 'is', 'the', 'how', 'why', 'are', 'in', 'of', 'for', 'to', 'a', 'and', 'should', 'be', 'when', 'does', 'much', 'many'}
    intent = detect_intent(question)
    
    selected_claims = []
    for claim in all_claims:
        claim_words = set(re.findall(r'\w+', claim.claim_text.lower()))
        overlap = question_words.intersection(claim_words)
        
        # Must be somewhat topically relevant
        if len(overlap) > 0 or len(question_words) == 0:
            # Must satisfy semantic intent
            if claim_satisfies_intent(claim.claim_text, intent, len(claim.numeric_entities) > 0):
                selected_claims.append(claim)
            
    if not selected_claims:
        # If no claim satisfies the exact intent + overlap, the deterministic system should ABSTAIN!
        # Do not just spit out adjacent topical facts.
        return {
            "answer": "I don't have sufficient evidence in the knowledge base to answer that.",
            "citations": [],
            "conflict": False
        }
        
    conflict = detect_conflicts(selected_claims)
    if conflict:
        return {
            "answer": conflict,
            "citations": [],
            "conflict": True
        }
        
    answer_parts = []
    used_sources = set()
    for claim in selected_claims:
        answer_parts.append(f"{claim.claim_text} [{claim.source_id}]")
        used_sources.add(claim.source_id)
        
    final_answer = " ".join(answer_parts)
    
    return {
        "answer": final_answer,
        "citations": list(used_sources),
        "conflict": False
    }

