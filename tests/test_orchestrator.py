"""Test Orchestrator directly."""

import json
from retrosynthesis_claw.orchestrator import RetrosynthesisOrchestrator

print("Testing Orchestrator directly for target molecule: BrC1=C2CCCOC2=NC=C1")
print("=" * 70)

try:
    orchestrator = RetrosynthesisOrchestrator.create_default()
    print("Created orchestrator successfully")
    
    print("Running retrosynthesis...")
    plan = orchestrator.run("BrC1=C2CCCOC2=NC=C1", top_k=1)
    
    print("\nSuccess!")
    print("Orchestrator result:")
    result = plan.to_dict()
    print(json.dumps(result, indent=2, ensure_ascii=False)[:1500])
    
    if "routes" in result and len(result["routes"]) > 0:
        route = result["routes"][0]
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
        
        print("✅ Orchestrator test completed successfully!")
    else:
        print("❌ No routes found in result")
        
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
