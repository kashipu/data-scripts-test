#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test fix para archivo Julio BM"""

import sys
import pandas as pd
import json
import re
from pathlib import Path

# Fix encoding Windows
if sys.platform == 'win32':
    import codecs
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'ignore')

def fix_json_format(json_text):
    """Fix JSON con comillas simples y sin comas"""
    if not isinstance(json_text, str) or pd.isna(json_text):
        return json_text

    try:
        json.loads(json_text)
        return json_text
    except:
        pass

    fixed = json_text
    fixed = fixed.replace('\\', '')
    fixed = re.sub(r"'(\w+)':", r'"\1":', fixed)
    fixed = re.sub(r":\s*'([^']*?)'", r': "\1"', fixed)
    fixed = re.sub(r'"\s+"', '", "', fixed)  # Entre strings
    fixed = re.sub(r'(\d)\s+"', r'\1, "', fixed)  # Después de números
    fixed = re.sub(r'}\s+{', '}, {', fixed)  # Entre objetos

    try:
        json.loads(fixed)
        return fixed
    except Exception as e:
        print(f"JSON irrecuperable: {str(e)[:50]}")
        return '[]'

# Leer archivo
archivo = "datos_raw/1 Base Julio_BM_2025_extracted_256529.xlsx"
print(f"Leyendo: {archivo}")

df = pd.read_excel(archivo, nrows=10)
print(f"Registros leidos: {len(df)}")

# Probar fix en los primeros 10
exitos = 0
fallos = 0

for idx, answers in enumerate(df['answers']):
    fixed = fix_json_format(answers)

    try:
        parsed = json.loads(fixed)
        exitos += 1
        print(f"  Fila {idx+1}: OK - {len(parsed)} items")
    except:
        fallos += 1
        print(f"  Fila {idx+1}: FALLO")

print(f"\nRESULTADO: {exitos} exitos, {fallos} fallos")
print(f"Tasa de exito: {(exitos/(exitos+fallos)*100):.1f}%")
