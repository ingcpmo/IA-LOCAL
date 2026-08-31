"""H-10 -- extracción determinista de `SystemComponent` / `Actor` desde claims.

Verifica: mención literal + diccionario cerrado + provenance anclada · dedup ·
nombres genéricos NO generan nodo por sí solos · idempotencia (ids deterministas) ·
0 nodo sin ancla (anti-fabricación).
"""
from __future__ import annotations

from factory.regulatory.canonical import model as m
from factory.regulatory.canonical.extract_entities import extract_entities_for_document


def _claim(document_id: str, page: int, text: str) -> dict:
    c = m.build_claim(document_id, page, text, "statement", text[:120])
    return m.as_dict(c)


def test_extracts_dictionary_component_and_actor_with_provenance():
    claims = [
        _claim("D", 3, "The ControlLogix 5580 controller runs the batch sequence."),
        _claim("D", 7, "Only a System Administrator may change a critical parameter."),
        _claim("D", 9, "The Operator acknowledges alarms from the PanelView Plus terminal."),
    ]
    comps, actors = extract_entities_for_document("D", claims)
    cnames = {c.nombre for c in comps}
    anames = {a.nombre_rol for a in actors}
    assert "ControlLogix" in cnames
    assert "PanelView Plus" in cnames
    assert "System Administrator" in anames
    assert "Operator" in anames
    # provenance anclada obligatoria
    for obj in (*comps, *actors):
        assert obj.provenance is not None
        assert obj.provenance.page >= 1
        assert obj.provenance.source_text
        assert obj.provenance.source_hash == m.sha256_text(obj.provenance.source_text)


def test_no_node_without_literal_mention():
    claims = [_claim("D", 1, "The system shall be validated per GAMP 5.")]
    comps, actors = extract_entities_for_document("D", claims)
    assert comps == [] and actors == []


def test_dedup_and_deterministic_ids():
    claims = [
        _claim("D", 2, "FactoryTalk Historian stores process data."),
        _claim("D", 5, "Data flows to FactoryTalk Historian every minute."),
    ]
    c1, _ = extract_entities_for_document("D", claims)
    c2, _ = extract_entities_for_document("D", claims)
    hist = [c for c in c1 if c.nombre == "FactoryTalk Historian"]
    assert len(hist) == 1                                  # dedup
    assert [c.component_id for c in c1] == [c.component_id for c in c2]  # determinista


def test_equipment_tag_not_confused_with_requirement_id():
    claims = [
        _claim("D", 4, "Panel PCS-CP-01 houses the misc PLC."),
        _claim("D", 8, "Requirement PCS-HR-001 is implemented by function F01.00."),
    ]
    comps, _ = extract_entities_for_document("D", claims)
    names = {c.nombre for c in comps}
    assert any("CP-01" in n or "CP01" in n for n in names)   # el tag de equipo sí
    assert not any("HR-001" in n for n in names)             # el id de requisito NO


def test_h10_rc2_specific_factorytalk_products_are_recognized():
    """H-10 fix RC-2 (tras E1-2: 6/7 WRONG_NODE residuales eran 'FactoryTalk'
    genérico donde el claim nombra un producto específico). El diccionario
    reconoce las formas completas; las VARIANTES de nombre resuelven al nodo
    CANÓNICO (no crean un nodo duplicado)."""
    claims = [
        _claim("D", 1, "is handled in the PLC and not in the FactoryTalk Alarm and Events"),
        _claim("D", 2, "added to the FactoryTalk Runtime Security group"),      # variante -> Security
        _claim("D", 3, "FactoryTalk Activation Manager 4.05.01 Server"),
        _claim("D", 4, "FactoryTalk View Site Edition 10-Client Bundle"),        # variante -> View SE
        _claim("D", 5, "and all FactoryTalk Security actions are audited"),
        _claim("D", 6, "the FactoryTalk Alarms and Events server logs events"),  # variante -> Alarm and Events
    ]
    comps, _ = extract_entities_for_document("D", claims)
    names = {c.nombre for c in comps}
    assert "FactoryTalk Alarm and Events" in names
    assert "FactoryTalk Activation Manager" in names
    assert "FactoryTalk Security" in names
    assert "FactoryTalk View SE" in names
    # las variantes NO son nodos propios -> sin duplicados semánticos
    assert "FactoryTalk View Site Edition" not in names
    assert "FactoryTalk Runtime Security" not in names
    assert "FactoryTalk Alarms and Events" not in names
