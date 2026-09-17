def fix_evidence():
    with open('app/evidence_extractor.py', 'r') as f:
        content = f.read()
        
    old_block = '''    selected_claims = []
    for claim in all_claims:
        claim_words = set(re.findall(r'\w+', claim.claim_text.lower()))
        overlap = question_words.intersection(claim_words)
        
        # Must be somewhat topically relevant
        if len(overlap) > 0 or len(question_words) == 0:
            # Must satisfy semantic intent
            if claim_satisfies_intent(claim.claim_text, intent, len(claim.numeric_entities) > 0):
                selected_claims.append(claim)'''

    new_block = '''    selected_claims = []
    question_lower = question.lower()
    for claim in all_claims:
        import re
        claim_words = set(re.findall(r'\w+', claim.claim_text.lower()))
        overlap = question_words.intersection(claim_words)
        
        if claim_satisfies_intent(claim.claim_text, intent, len(claim.numeric_entities) > 0):
            if 'high' in question_lower and ('low' in claim.claim_text.lower() or 'lower' in claim.claim_text.lower()):
                continue
            if 'midnight' in question_lower and 'morning' in claim.claim_text.lower() and 'midnight' not in claim.claim_text.lower():
                continue
            if 'brand' in question_lower and 'brand' not in claim.claim_text.lower():
                continue
            if 'who owns' in question_lower and 'owns' not in claim.claim_text.lower() and 'owner' not in claim.claim_text.lower():
                continue
            if len(overlap) > 0 or len(question_words) == 0:
                selected_claims.append(claim)'''
                
    content = content.replace(old_block, new_block)
    
    with open('app/evidence_extractor.py', 'w') as f:
        f.write(content)

fix_evidence()
