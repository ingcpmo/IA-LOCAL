"""Prototipo AISLADO del modelo hibrido determinista + Ollama (Mesa de Diseno, FASE 2).

NO forma parte del producto. NO se importa desde app/ ni desde factory/regulatory/.
- No escribe en el audit trail real (usa su propio poc_log.jsonl).
- Lee el store canonico en SOLO LECTURA.
- No modifica findings, reglas ni provenance.
- Suite de pruebas propia (test_poc.py); no toca la suite del proyecto.
"""
