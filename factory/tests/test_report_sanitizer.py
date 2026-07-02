"""
W5 — Tests unitarios dedicados de factory/core/report_sanitizer.py.

Cubren el comportamiento preexistente (regresión) y el patrón nuevo de
credenciales embebidas en connection strings. Función pura: sin FastAPI,
sin contenedor, sin red.
"""

from factory.core.report_sanitizer import sanitize_for_report

REDACTED = "***REDACTED***"


# ── Regresión: comportamiento preexistente ────────────────────────────────────

def test_masks_sensitive_key_names_regardless_of_value():
    data = {
        "api_key": "x",
        "API-KEY": "y",
        "password": "z",
        "client_secret": "s",
        "auth_token": "t",
        "credentials": {"inner": "v"},
        "normal_field": "keep",
    }
    out = sanitize_for_report(data)
    assert out["api_key"] == REDACTED
    assert out["API-KEY"] == REDACTED
    assert out["password"] == REDACTED
    assert out["client_secret"] == REDACTED
    assert out["auth_token"] == REDACTED
    assert out["credentials"] == REDACTED
    assert out["normal_field"] == "keep"


def test_masks_known_secret_values_in_strings():
    out = sanitize_for_report(
        {"log": "connected with key SECRETVALUE ok"},
        secret_values=["SECRETVALUE"],
    )
    assert out["log"] == f"connected with key {REDACTED} ok"


def test_masks_sk_ant_pattern():
    out = sanitize_for_report("prefix sk-ant-abc123_XYZ- suffix")
    assert out == f"prefix {REDACTED} suffix"


def test_does_not_mutate_input():
    data = {"password": "p", "nested": ["a", {"token": "t"}]}
    sanitize_for_report(data)
    assert data == {"password": "p", "nested": ["a", {"token": "t"}]}


def test_walks_lists_and_tuples():
    out = sanitize_for_report(["ok", ("sk-ant-xyz", "plain")])
    assert out[0] == "ok"
    assert out[1] == (REDACTED, "plain")
    assert isinstance(out[1], tuple)


def test_empty_and_none_secret_values_are_ignored():
    out = sanitize_for_report({"log": "nothing here"}, secret_values=["", None])
    assert out["log"] == "nothing here"


# ── W5: credenciales embebidas en connection strings ──────────────────────────

def test_masks_postgresql_connection_string_password():
    url = "postgresql://gmp_user:S3cr3tPass@postgres:5432/gmp_db"
    out = sanitize_for_report({"database_url_note": url})
    assert out["database_url_note"] == (
        f"postgresql://{REDACTED}@postgres:5432/gmp_db"
    )
    assert "S3cr3tPass" not in str(out)


def test_masks_redis_url_with_empty_user():
    url = "redis://:redispass@redis:6379/0"
    out = sanitize_for_report({"note": url})
    assert out["note"] == f"redis://{REDACTED}@redis:6379/0"
    assert "redispass" not in str(out)


def test_masks_conn_string_inside_larger_text():
    text = "conexión fallida a postgresql://u:pw@db:5432/x tras 3 intentos"
    out = sanitize_for_report(text)
    assert "pw" not in out.split("@")[0].split("://")[-1]
    assert out == (
        f"conexión fallida a postgresql://{REDACTED}@db:5432/x tras 3 intentos"
    )


def test_url_without_credentials_is_untouched():
    for url in [
        "http://localhost:9000/api/v1/layer9/missions",
        "http://host.docker.internal:11434",
        "https://www.fda.gov/inspections-compliance",
    ]:
        assert sanitize_for_report(url) == url


def test_plain_timestamps_and_ratios_are_untouched():
    data = {
        "ts": "2026-07-02T10:00:00+00:00",
        "ratio": "18:18 PASS",
        "elapsed": "0:01:23",
    }
    assert sanitize_for_report(data) == data


def test_email_like_strings_do_not_lose_local_part():
    # user@host sin esquema '://' no debe tocarse.
    assert sanitize_for_report("ing_cpmo@ivr-ia") == "ing_cpmo@ivr-ia"
