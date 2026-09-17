import urllib.request
import json
req = urllib.request.Request('http://localhost:8000/query', data=json.dumps({"question":"Why should shrimp ponds be checked around dawn?"}).encode('utf-8'), headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req) as response:
    print(response.read().decode('utf-8'))
