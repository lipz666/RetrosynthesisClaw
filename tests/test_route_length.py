#!/usr/bin/env python3
"""
Test script to verify the retrosynthesis route length based on molecule complexity.
"""

from retrosynthesis_claw.orchestrator import RetrosynthesisOrchestrator

# Create orchestrator
orchestrator = RetrosynthesisOrchestrator.create_default()

# Test molecules of different complexity
print("Testing retrosynthesis route generation based on molecule complexity...")
print("=" * 70)

# Simple molecule (SMILES length < 10)
test_molecules = [
    ("CCO", "Ethanol (simple)"),
    ("CC(=O)O", "Acetic acid (medium)"),
    ("C1=CC=CC=C1C(=O)O", "Benzoic acid (medium)"),
    ("CC1=C(C(=O)O)C=CC=C1OC2=CC=C(C=C2)Cl", "Complex molecule (complex)"),
]

for smiles, description in test_molecules:
    print(f"\nTesting: {description}")
    print(f"SMILES: {smiles}")
    print(f"SMILES length: {len(smiles)}")
    
    try:
        # Run retrosynthesis
        route_plan = orchestrator.run(smiles, top_k=1)
        
        if route_plan.routes:
            route = route_plan.routes[0]
            print(f"Generated steps: {len(route.steps)}")
            print(f"Route score: {route.total_score}")
            
            # Print first few steps
            print("First 3 steps:")
            for i, step in enumerate(route.steps[:3]):
                print(f"  Step {step.step_index}: {step.target_smiles} → {step.precursors}")
        else:
            print("No routes generated")
            
    except Exception as e:
        print(f"Error: {e}")
    
    print("-" * 50)