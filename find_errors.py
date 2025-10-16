#!/usr/bin/env python3
"""Buscar casos problemáticos en JSON"""

import pandas as pd
import json
import re
import sys

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'ignore')

def fix_json_format(json_text):
    if not isinstance(json_text, str):
        return None

    fixed = json_text.replace('\\', '')
    fixed = re.sub(r"'(\w+)':", r'"\1":', fixed)
    fixed = re.sub(r":\s*'(.*?)'\s*([\s}])", r': "\1"\2', fixed)  # MEJORADO
    fixed = re.sub(r'"\s+"', '", "', fixed)
    fixed = re.sub(r'(\d)\s+"', r'\1, "', fixed)
    fixed = re.sub(r'}\s+{', '}, {', fixed)

    try:
        json.loads(fixed)
        return None  # OK
    except Exception as e:
        return (json_text[:200], fixed[:200], str(e))

# Cargar registros
print("Cargando 2000 registros...")
df = pd.read_excel('datos_raw/1 Base Julio_BM_2025_extracted_256529.xlsx', nrows=2000)

# Buscar errores
errores = []
for idx, answers in enumerate(df['answers']):
    error = fix_json_format(answers)
    if error:
        errores.append((idx+2, error))
        if len(errores) >= 5:
            break

print(f"\nErrores encontrados: {len(errores)}")

for fila, (original, fixed, msg) in errores:
    print(f"\n{'='*70}")
    print(f"FILA {fila}:")
    print(f"ORIGINAL: {original}")
    print(f"FIXED:    {fixed}")
    print(f"ERROR:    {msg[:80]}")
