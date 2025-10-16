#!/usr/bin/env python3
import pandas as pd
import re
import json
import sys

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'ignore')

# Leer fila problemática
df = pd.read_excel('datos_raw/1 Base Julio_BM_2025_extracted_256529.xlsx', nrows=350)
answer = df['answers'].iloc[343]  # Fila 345 = index 343

print(f"JSON COMPLETO ({len(answer)} chars):")
print(answer)
print("\n" + "="*70)

# Aplicar fix SIMPLE v5
fixed = answer.replace('\\', '')
fixed = fixed.replace("'", '"')  # Simple: todas las comillas
fixed = re.sub(r'(\d)\s+"', r'\1, "', fixed)
fixed = re.sub(r'"\s+"(\w+)":', '", "\1":', fixed)
fixed = re.sub(r'}\s+{', '}, {', fixed)

print(f"\nJSON FIXED ({len(fixed)} chars):")
print(fixed)
print("\n" + "="*70)

# Ver alrededor del char 338
print(f"\nAlrededor del char 338:")
print(f"Posición 330-350: '{fixed[330:350]}'")
print(f"Posición 335-345: '{fixed[335:345]}'")

# Intentar parsear
try:
    result = json.loads(fixed)
    print("\nPARSEO: OK!")
    print(f"Items: {len(result)}")
except Exception as e:
    print(f"\nPARSEO: ERROR")
    print(f"Error: {e}")
