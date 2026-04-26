"""Test retrosynthesis for target molecule."""

import json
import urllib.request

url = "http://localhost:8000/route"

target_smiles = "BrC1=C2CCCOC2=NC=C1"

payload = {
    "target": target_smiles,
    "top_k": 1,
    "debug": True
}

data = json.dumps(payload).encode("utf-8")
headers = {"Content-Type": "application/json"}

print(f"Testing retrosynthesis for target molecule: {target_smiles}")
print("=" * 70)

try:
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    print("Sending request to FastAPI...")
    with urllib.request.urlopen(req, timeout=180) as resp:
        raw = resp.read().decode("utf-8")
        print(f"Status: {resp.status}")
        result = json.loads(raw)
        print("\nSuccess!")
        print("Retrosynthesis result:")
        print(json.dumps(result, indent=2, ensure_ascii=False)[:2000])
        
        # Extract key information
        if "result" in result:
            result_data = result["result"]
            if "routes" in result_data and len(result_data["routes"]) > 0:
                route = result_data["routes"][0]
                print("\n" + "=" * 70)
                print("Route analysis:")
                print(f"Route ID: {route.get('route_id', 'N/A')}")
                print(f"Total score: {route.get('total_score', 'N/A')}")
                print(f"Feasibility score: {route.get('feasibility_score', 'N/A')}")
                
                if "steps" in route and len(route["steps"]) > 0:
                    print("\nRetrosynthesis steps:")
                    for i, step in enumerate(route["steps"]):
                        print(f"Step {i+1}:")
                        print(f"  Target: {step.get('target_smiles', 'N/A')}")
                        print(f"  Reaction: {step.get('reaction_type', 'N/A')}")
                        print(f"  Precursors: {step.get('precursors', 'N/A')}")
                        print(f"  Confidence: {step.get('confidence', 'N/A')}")
                        print(f"  Rationale: {step.get('rationale', 'N/A')}")
                        print()
                
                print("✅ Retrosynthesis completed successfully!")
            else:
                print("❌ No routes found in result")
        else:
            print("❌ No result field in response")
            
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
