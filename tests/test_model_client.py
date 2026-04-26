from retrosynthesis_claw.config import load_default_config
from retrosynthesis_claw.model_client import build_model_client

config = load_default_config()
client = build_model_client(config.model)
result = client.generate_retrosynthesis('CCO')

print('Model test successful!')
print(f'Model: {config.model.model_name}')
print(f'Proposal: {result.get("proposal")}')
print(f'Precursors: {result.get("precursors")}')
print(f'Reaction type: {result.get("reaction_type")}')
print(f'Notes: {result.get("notes")}')
