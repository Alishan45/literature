import requests, os
from dotenv import load_dotenv
load_dotenv()
key = os.getenv('GEMINI_API_KEY', '').strip('"\'')
url = f'https://generativelanguage.googleapis.com/v1beta/models?pageSize=200&key={key}'
r = requests.get(url, timeout=30)
data = r.json()
models = [
    m['name'].replace('models/', '')
    for m in data.get('models', [])
    if 'generateContent' in m.get('supportedGenerationMethods', [])
]
print('Available generateContent models:')
for m in sorted(models):
    print(' ', m)
