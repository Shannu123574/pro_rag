import re

def fix_scope():
    with open('app/evidence_extractor.py', 'r') as f:
        content = f.read()
    
    # Remove the bad inline import to fix UnboundLocalError
    content = content.replace("        import re\n", "")
    
    with open('app/evidence_extractor.py', 'w') as f:
        f.write(content)

fix_scope()
