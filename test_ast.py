#!/usr/bin/env python3
import ast
import json

answer = "[{'questionTitle': 'Test' 'answerValue': 10}]"
print("ORIGINAL:", answer)

try:
    parsed = ast.literal_eval(answer)
    result = json.dumps(parsed, ensure_ascii=False)
    print("PARSED AST:", result)
except Exception as e:
    print("ERROR:", e)
