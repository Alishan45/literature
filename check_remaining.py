import csv

def normalize(e):
    return str(e).strip().lower()

sent = set()
with open('EMAIL_LOG.csv', 'r', encoding='utf-8', newline='') as f:
    r = csv.DictReader(f)
    for row in r:
        if str(row.get('Email_Status', '')).upper() == 'SENT' and row.get('Professor_Email'):
            sent.add(normalize(row['Professor_Email']))

profs = []
with open('literature.csv', 'r', encoding='utf-8-sig', newline='') as f:
    r = csv.DictReader(f)
    for row in r:
        profs.append(row)

remaining = [p for p in profs if normalize(p['email']) not in sent]
print(f"Total: {len(profs)} | Sent: {len(sent)} | Remaining: {len(remaining)}")
for p in remaining[:10]:
    print(f"  Row {profs.index(p)+2}: {p['professor_name']} | {p['email']}")
