"""Test direct retrosynthesis for the target molecule."""

import json
import urllib.request

url = "http://localhost:8000/model-test"

print("Testing direct retrosynthesis for target molecule: BrC1=C2CCCOC2=NC=C1")
print("=" * 70)

try:
    req = urllib.request.Request(url, method="GET")
    print("Testing model endpoint...")
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
        print(f"Status: {resp.status}")
        result = json.loads(raw)
        print("\nModel test successful!")
        print(json.dumps(result, indent=2, ensure_ascii=False)[:1000])
        
    # Now test with the actual molecule
    print("\n" + "=" * 70)
    print("Testing with target molecule...")
    
    # Create a custom request to test the target molecule
    import urllib.parse
    import urllib.request
    
    # Use the model client directly
    from retrosynthesis_claw.config import load_default_config
    from retrosynthesis_claw.model_client import build_model_client
    
    cfg = load_default_config()
    client = build_model_client(cfg.model)
    
    print("Calling model client...")
    result = client.generate_retrosynthesis(
        "BrC1=C2CCCOC2=NC=C1",
        context="test_target_molecule"
    )
    
    print("\nSuccess!")
    print("Retrosynthesis result:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    print("\n" + "=" * 70)
    print("Model response analysis:")
    print(f"Proposal: {result.get('proposal', 'N/A')}")
    print(f"Reaction type: {result.get('reaction_type', 'N/A')}")
    print(f"Precursors: {result.get('precursors', 'N/A')}")
    print(f"Confidence: {result.get('confidence', 'N/A')}")
    
    if 'raw_response' in result:
        print("\nRaw model response received")
    
    print("\n✅ Direct retrosynthesis test completed successfully!")
    
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
