# TAREA HEADLESS — c8_alcoa_validator (GENERACIÓN de código)

Eres el agente headless de Capa 8. La misión está aprobada por un humano.
Tu trabajo es CREAR código nuevo dentro de este workspace.

## Crear app/alcoa_validator.py (solo stdlib)
Funciones:
  ATTRIBUTES = ["attributable","legible","contemporaneous","original",
                "accurate","complete","consistent","enduring","available"]

  validate_alcoa_record(record: dict) -> dict
    Revisa qué atributos ALCOA+ están presentes y con valor verdadero en record.
    Retorna {"compliant": bool, "present": [...], "missing": [...],
             "score": int (0-9)}.  compliant es True solo si los 9 están presentes.

  compute_record_hash(record: dict) -> str
    Devuelve "sha256:" + hexdigest del JSON ordenado del record.

  audit_stamp(actor: str, action: str, record: dict) -> dict
    Retorna {"actor": actor, "action": action,
             "timestamp_utc": ISO-8601 en UTC,
             "record_hash": compute_record_hash(record)}

## Crear tests/test_alcoa_validator.py (pytest, solo stdlib)
Exactamente 6 tests:
  1. record con los 9 atributos en True -> compliant True, score 9, missing []
  2. record al que le falta "accurate" -> compliant False, "accurate" en missing
  3. record vacío -> compliant False, score 0
  4. compute_record_hash empieza con "sha256:" y es estable para el mismo input
  5. audit_stamp tiene actor, action, timestamp_utc y record_hash
  6. audit_stamp["timestamp_utc"] termina en "+00:00" o "Z" (UTC)

## Reglas
- Solo lectura y escritura dentro de este workspace.
- Solo la biblioteca estandar de Python (sin instalar paquetes, sin red).
- Comandos permitidos: ls, grep, find, cat, python3 sobre archivos del workspace,
  y pytest sobre tests/.
- No modifiques nada fuera del workspace.

## Entregable
app/alcoa_validator.py y tests/test_alcoa_validator.py funcionando con pytest.
