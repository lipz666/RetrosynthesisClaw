try:
    from rdkit import Chem
    print('RDKit available:', True)
except ImportError:
    print('RDKit available:', False)
