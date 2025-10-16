#!/usr/bin/env python3
import ast
import json
import re
import sys

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'ignore')

import pandas as pd

# Leer caso real problemático
df = pd.read_excel('datos_raw/1 Base Julio_BM_2025_extracted_256529.xlsx', nrows=350)
answer = df['answers'].iloc[343]

print(f"ORIGINAL ({len(answer)} chars):")
print(answer[:200], "...")

# Aplicar fix completo con ast
fixed = answer.replace('\\', '')
fixed = re.sub(r"(\d)\s+'", r"\1, '", fixed)
fixed = re.sub(r"'\s+'(\w)", r"', '\1", fixed)  # Solo si sigue letra
fixed = re.sub(r"}\s+{", r"}, {", fixed)

print(f"\nFIXED ({len(fixed)} chars):")
print(fixed)  # Completo para ver el error

try:
    parsed = ast.literal_eval(fixed)
    result = json.dumps(parsed, ensure_ascii=False)
    print("\nRESULTADO: OK!")
    print(f"Items: {len(parsed)}")
    print(f"JSON válido ({len(result)} chars)")
except Exception as e:
    print(f"\nERROR: {e}")
