import urllib.request
import json
req = urllib.request.Request(
    'http://127.0.0.1:8001/orcamento/upsert-linhas',
    data=json.dumps({
        "linhas":[{
            "id": "abc",
            "id_planilha": "p1",
            "descricao": "Tijolo",
            "unidade": "un",
            "quantidade": 100,
            "preco_unitario": 1.5,
            "macro_item_context": "Paredes"
        }]
    }).encode(),
    headers={
        'Content-Type': 'application/json',
        'x-api-secret': 'sk-foiasodfnlnasdker-949865165fasejgooasdnlfga',
        'x-tenant-id': 'tenant_test'
    }
)
try:
    resp = urllib.request.urlopen(req)
    print("SUCCESS", resp.read())
except Exception as e:
    print("ERROR", e)
    if hasattr(e, 'read'):
        print(e.read().decode())
