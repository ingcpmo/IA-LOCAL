# E1 — PAQUETE DE REVISIÓN HUMANA · RELACIONES NUEVAS DE H-10

**Fecha:** 2026-08-31 · **Autoridad:** Capa 9 = Cesar · **Tipo:** preparación READ-ONLY para revisión humana.
**Fuente (no modificada):** `factory/regulatory/pilot_run/h10_extraction_v2_20260830/H10_NEW_RELATIONS_SAMPLE_FOR_HUMAN.json`
**SAMPLE_SHA256 =** `f56d4babe7e8466368c9a6dbefe26e3716186f96e2658c68cf2f0469f5244f20`

```
SAMPLE_TOTAL   = 77
TESTED_BY_ROWS = 17
REFERS_TO_ROWS = 60
E1             = PENDING_HUMAN
```

**Flags estructurales** (son observaciones automáticas, NO veredictos):
`TOC_OR_INDEX_CONTEXT` · `REFERENCE_LIST_CONTEXT` · `CROSS_DOCUMENT_ENTITY_ANCHOR` · `NESTED_ENTITY_NAME` · `POSSIBLE_ALIAS` · `SAME_CLAIM_MULTIPLE_ENTITY_EDGES` · `EXACT_LITERAL_MATCH`

**Veredicto humano permitido** (Capa 9 / QA lo asigna; la máquina NO): `CORRECT` · `WRONG_NODE` · `SPURIOUS` · `AMBIGUOUS`

---

## A · `tested_by` — 17 filas (todas las aristas de la corrida)

### [TES-01]
```
INDEX                = TESTED_BY-01
RELATION             = tested_by
SOURCE_DOCUMENT      = RW-0006
PAGE                 = 192
EXACT_SOURCE_ANCHOR  = Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date) UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms. 1. Th
SOURCE_NODE          = clm-ffce50cb975b2635
SOURCE_LABEL         = 3.2.3 The Equipment shall have critical alarms and warnings as listed in
DESTINATION_NODE     = tst-c51272c4621d673e
DESTINATION_LABEL    = UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms. 1. T  (test)
REQUIREMENT_OR_REF   = 3.2.3
PROVENANCE_HASH      = 8b054b046f6700d3112c0d6dfe1948e1174dac27c8e44a9f8309cd9aeb51a2aa
STRUCTURAL_FLAGS     = CROSS_DOCUMENT_ENTITY_ANCHOR, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [TES-02]
```
INDEX                = TESTED_BY-02
RELATION             = tested_by
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 192
EXACT_SOURCE_ANCHOR  = Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date) UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms. 1. Th
SOURCE_NODE          = clm-9b30567369b392a1
SOURCE_LABEL         = UR4.1.1 [MCCPDC 3.2.3] - The physical servers shall be two (2) redundant Rockwell VersaVirtual™
DESTINATION_NODE     = tst-c51272c4621d673e
DESTINATION_LABEL    = UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms. 1. T  (test)
REQUIREMENT_OR_REF   = 3.2.3
PROVENANCE_HASH      = 8b054b046f6700d3112c0d6dfe1948e1174dac27c8e44a9f8309cd9aeb51a2aa
STRUCTURAL_FLAGS     = CROSS_DOCUMENT_ENTITY_ANCHOR, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [TES-03]
```
INDEX                = TESTED_BY-03
RELATION             = tested_by
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 192
EXACT_SOURCE_ANCHOR  = Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date) UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms. 1. Th
SOURCE_NODE          = clm-a27011aa844768f7
SOURCE_LABEL         = UR4.1.1 [MCCPDC 3.2.3] - The physical servers shall be…
DESTINATION_NODE     = tst-c51272c4621d673e
DESTINATION_LABEL    = UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms. 1. T  (test)
REQUIREMENT_OR_REF   = 3.2.3
PROVENANCE_HASH      = 8b054b046f6700d3112c0d6dfe1948e1174dac27c8e44a9f8309cd9aeb51a2aa
STRUCTURAL_FLAGS     = CROSS_DOCUMENT_ENTITY_ANCHOR, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [TES-04]
```
INDEX                = TESTED_BY-04
RELATION             = tested_by
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 157
EXACT_SOURCE_ANCHOR  = Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date) F05.05: Input State and Simulation Review Screen  | F05.05: Input State and Simulation Review Screen |  |  |  |  |  1. | Prerequisi
SOURCE_NODE          = clm-c16b3a168d374cef
SOURCE_LABEL         = screen, accessible by Admin and Maintenance personnel.-F05.05, 24
DESTINATION_NODE     = tst-b192abb965189ab2
DESTINATION_LABEL    = F05.05: Input State and Simulation Review Screen  (test)
REQUIREMENT_OR_REF   = F05.05
PROVENANCE_HASH      = cd0bf8a2144e2997662f6afbf8ad18789647d8ae306aed3bff1fe201aa484ade
STRUCTURAL_FLAGS     = CROSS_DOCUMENT_ENTITY_ANCHOR, SAME_CLAIM_MULTIPLE_ENTITY_EDGES, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [TES-05]
```
INDEX                = TESTED_BY-05
RELATION             = tested_by
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 192
EXACT_SOURCE_ANCHOR  = Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date) UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms. 1. Th
SOURCE_NODE          = clm-160f8415ea17e786
SOURCE_LABEL         = UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms.
DESTINATION_NODE     = tst-c51272c4621d673e
DESTINATION_LABEL    = UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms. 1. T  (test)
REQUIREMENT_OR_REF   = UR3.2.3
PROVENANCE_HASH      = 8b054b046f6700d3112c0d6dfe1948e1174dac27c8e44a9f8309cd9aeb51a2aa
STRUCTURAL_FLAGS     = CROSS_DOCUMENT_ENTITY_ANCHOR, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [TES-06]
```
INDEX                = TESTED_BY-06
RELATION             = tested_by
SOURCE_DOCUMENT      = RW-0006
PAGE                 = 192
EXACT_SOURCE_ANCHOR  = Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date) UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms. 1. Th
SOURCE_NODE          = clm-ba26e44e69dabe0f
SOURCE_LABEL         = The list of critical alarms in the table is not intended to be a are identified.
DESTINATION_NODE     = tst-c51272c4621d673e
DESTINATION_LABEL    = UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms. 1. T  (test)
REQUIREMENT_OR_REF   = 3.2.3
PROVENANCE_HASH      = 8b054b046f6700d3112c0d6dfe1948e1174dac27c8e44a9f8309cd9aeb51a2aa
STRUCTURAL_FLAGS     = CROSS_DOCUMENT_ENTITY_ANCHOR
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [TES-07]
```
INDEX                = TESTED_BY-07
RELATION             = tested_by
SOURCE_DOCUMENT      = RW-0006
PAGE                 = 192
EXACT_SOURCE_ANCHOR  = Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date) UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms. 1. Th
SOURCE_NODE          = clm-1c7584b555c57656
SOURCE_LABEL         = included in the Functional Specification document.
DESTINATION_NODE     = tst-c51272c4621d673e
DESTINATION_LABEL    = UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms. 1. T  (test)
REQUIREMENT_OR_REF   = 3.2.3
PROVENANCE_HASH      = 8b054b046f6700d3112c0d6dfe1948e1174dac27c8e44a9f8309cd9aeb51a2aa
STRUCTURAL_FLAGS     = CROSS_DOCUMENT_ENTITY_ANCHOR
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [TES-08]
```
INDEX                = TESTED_BY-08
RELATION             = tested_by
SOURCE_DOCUMENT      = RW-0006
PAGE                 = 192
EXACT_SOURCE_ANCHOR  = Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date) UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms. 1. Th
SOURCE_NODE          = clm-ae6b1677b2211968
SOURCE_LABEL         = 4.1.1 [MCCPDC 3.2.3] - The physical servers shall be two (2) redundant
DESTINATION_NODE     = tst-c51272c4621d673e
DESTINATION_LABEL    = UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms. 1. T  (test)
REQUIREMENT_OR_REF   = 3.2.3
PROVENANCE_HASH      = 8b054b046f6700d3112c0d6dfe1948e1174dac27c8e44a9f8309cd9aeb51a2aa
STRUCTURAL_FLAGS     = CROSS_DOCUMENT_ENTITY_ANCHOR, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [TES-09]
```
INDEX                = TESTED_BY-09
RELATION             = tested_by
SOURCE_DOCUMENT      = RW-0006
PAGE                 = 192
EXACT_SOURCE_ANCHOR  = Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date) UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms. 1. Th
SOURCE_NODE          = clm-41c127a212f199c8
SOURCE_LABEL         = comprehensive list of all alarms for the system.
DESTINATION_NODE     = tst-c51272c4621d673e
DESTINATION_LABEL    = UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms. 1. T  (test)
REQUIREMENT_OR_REF   = 3.2.3
PROVENANCE_HASH      = 8b054b046f6700d3112c0d6dfe1948e1174dac27c8e44a9f8309cd9aeb51a2aa
STRUCTURAL_FLAGS     = CROSS_DOCUMENT_ENTITY_ANCHOR
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [TES-10]
```
INDEX                = TESTED_BY-10
RELATION             = tested_by
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 192
EXACT_SOURCE_ANCHOR  = Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date) UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms. 1. Th
SOURCE_NODE          = clm-8d03847d17feacd3
SOURCE_LABEL         = UR4.1.1 [MCCPDC 3.2.3] - The physical servers shall be two (2) redundant Rockwell VersaVirtual™ Appliances suitable for
DESTINATION_NODE     = tst-c51272c4621d673e
DESTINATION_LABEL    = UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms. 1. T  (test)
REQUIREMENT_OR_REF   = 3.2.3
PROVENANCE_HASH      = 8b054b046f6700d3112c0d6dfe1948e1174dac27c8e44a9f8309cd9aeb51a2aa
STRUCTURAL_FLAGS     = CROSS_DOCUMENT_ENTITY_ANCHOR, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [TES-11]
```
INDEX                = TESTED_BY-11
RELATION             = tested_by
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 158
EXACT_SOURCE_ANCHOR  = Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date) F05.05: Input State and Simulation Review Screen  | F05.05: Input State and Simulation Review Screen |  |  |  |  |  2. | Login as a
SOURCE_NODE          = clm-8137fdc377337cb4
SOURCE_LABEL         = specification (See 3.1.9, F05.05:
DESTINATION_NODE     = tst-0b2093f8f99bd8d5
DESTINATION_LABEL    = F05.05: Input State and Simulation Review Screen  (test)
REQUIREMENT_OR_REF   = F05.05
PROVENANCE_HASH      = b81489fbaa3fe5665a989354c4b8214bf591cb19b4997d5c556e77ad8a971f14
STRUCTURAL_FLAGS     = CROSS_DOCUMENT_ENTITY_ANCHOR, SAME_CLAIM_MULTIPLE_ENTITY_EDGES, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [TES-12]
```
INDEX                = TESTED_BY-12
RELATION             = tested_by
SOURCE_DOCUMENT      = RW-0006
PAGE                 = 192
EXACT_SOURCE_ANCHOR  = Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date) UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms. 1. Th
SOURCE_NODE          = clm-dd1fb6f61698250c
SOURCE_LABEL         = List of Critical-to-Quality Alarms.
DESTINATION_NODE     = tst-c51272c4621d673e
DESTINATION_LABEL    = UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms. 1. T  (test)
REQUIREMENT_OR_REF   = 3.2.3
PROVENANCE_HASH      = 8b054b046f6700d3112c0d6dfe1948e1174dac27c8e44a9f8309cd9aeb51a2aa
STRUCTURAL_FLAGS     = CROSS_DOCUMENT_ENTITY_ANCHOR
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [TES-13]
```
INDEX                = TESTED_BY-13
RELATION             = tested_by
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 192
EXACT_SOURCE_ANCHOR  = Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date) UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms. 1. Th
SOURCE_NODE          = clm-c2451957602c04bb
SOURCE_LABEL         = UR4.1.1 [MCCPDC 3.2.3] - The physical servers shall be ...
DESTINATION_NODE     = tst-c51272c4621d673e
DESTINATION_LABEL    = UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms. 1. T  (test)
REQUIREMENT_OR_REF   = 3.2.3
PROVENANCE_HASH      = 8b054b046f6700d3112c0d6dfe1948e1174dac27c8e44a9f8309cd9aeb51a2aa
STRUCTURAL_FLAGS     = CROSS_DOCUMENT_ENTITY_ANCHOR, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [TES-14]
```
INDEX                = TESTED_BY-14
RELATION             = tested_by
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 192
EXACT_SOURCE_ANCHOR  = Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date) UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms. 1. Th
SOURCE_NODE          = clm-ccb85cc5b3a7ee9a
SOURCE_LABEL         = UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical
DESTINATION_NODE     = tst-c51272c4621d673e
DESTINATION_LABEL    = UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms. 1. T  (test)
REQUIREMENT_OR_REF   = UR3.2.3
PROVENANCE_HASH      = 8b054b046f6700d3112c0d6dfe1948e1174dac27c8e44a9f8309cd9aeb51a2aa
STRUCTURAL_FLAGS     = CROSS_DOCUMENT_ENTITY_ANCHOR, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [TES-15]
```
INDEX                = TESTED_BY-15
RELATION             = tested_by
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 157
EXACT_SOURCE_ANCHOR  = Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date) F05.05: Input State and Simulation Review Screen  | F05.05: Input State and Simulation Review Screen |  |  |  |  |  1. | Prerequisi
SOURCE_NODE          = clm-8137fdc377337cb4
SOURCE_LABEL         = specification (See 3.1.9, F05.05:
DESTINATION_NODE     = tst-b192abb965189ab2
DESTINATION_LABEL    = F05.05: Input State and Simulation Review Screen  (test)
REQUIREMENT_OR_REF   = F05.05
PROVENANCE_HASH      = cd0bf8a2144e2997662f6afbf8ad18789647d8ae306aed3bff1fe201aa484ade
STRUCTURAL_FLAGS     = CROSS_DOCUMENT_ENTITY_ANCHOR, SAME_CLAIM_MULTIPLE_ENTITY_EDGES, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [TES-16]
```
INDEX                = TESTED_BY-16
RELATION             = tested_by
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 158
EXACT_SOURCE_ANCHOR  = Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date) F05.05: Input State and Simulation Review Screen  | F05.05: Input State and Simulation Review Screen |  |  |  |  |  2. | Login as a
SOURCE_NODE          = clm-c16b3a168d374cef
SOURCE_LABEL         = screen, accessible by Admin and Maintenance personnel.-F05.05, 24
DESTINATION_NODE     = tst-0b2093f8f99bd8d5
DESTINATION_LABEL    = F05.05: Input State and Simulation Review Screen  (test)
REQUIREMENT_OR_REF   = F05.05
PROVENANCE_HASH      = b81489fbaa3fe5665a989354c4b8214bf591cb19b4997d5c556e77ad8a971f14
STRUCTURAL_FLAGS     = CROSS_DOCUMENT_ENTITY_ANCHOR, SAME_CLAIM_MULTIPLE_ENTITY_EDGES, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [TES-17]
```
INDEX                = TESTED_BY-17
RELATION             = tested_by
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 192
EXACT_SOURCE_ANCHOR  = Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date) UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms. 1. Th
SOURCE_NODE          = clm-8f33dd65ec88cc74
SOURCE_LABEL         = UR4.1.1 requirement includes in its text, the customer reference number MCCPDC 3.2.3, followed by
DESTINATION_NODE     = tst-c51272c4621d673e
DESTINATION_LABEL    = UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms. 1. T  (test)
REQUIREMENT_OR_REF   = 3.2.3
PROVENANCE_HASH      = 8b054b046f6700d3112c0d6dfe1948e1174dac27c8e44a9f8309cd9aeb51a2aa
STRUCTURAL_FLAGS     = CROSS_DOCUMENT_ENTITY_ANCHOR, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

---

## B · `refers_to` — 60 filas (muestra determinista de 350 aristas en el grafo)

### [REF-01]
```
INDEX                = REFERS_TO-01
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = FactoryTalk Linx Enterprise 6.21.00 Server
SOURCE_NODE          = clm-e52a5d61f74010dd
SOURCE_LABEL         = Per Section 2.1.1 Software, Rockwell Automation’s FactoryTalk Historian SE Administration Console
DESTINATION_NODE     = cmp-abbe8a20dd017f4c
DESTINATION_LABEL    = FactoryTalk  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 113f38c655eaad528a008d67e56ea8a2cf0ae1658fe7398d9cdf1e802f88c4a9
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-02]
```
INDEX                = REFERS_TO-02
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = FactoryTalk View Studio Site Edition Enterprise
SOURCE_NODE          = clm-c90b9e26077cd43f
SOURCE_LABEL         = security is used to authenticate users and restrict operating system level actions, FactoryTalk View SE
DESTINATION_NODE     = cmp-7d1365129f9f1cb3
DESTINATION_LABEL    = FactoryTalk View  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 949b967bfe0056ffdf5fa394767c72eb0107a2be8168e54992619858545211f6
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-03]
```
INDEX                = REFERS_TO-03
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 13
EXACT_SOURCE_ANCHOR  = Allen-Bradley 1756-L83E ControlLogix 5580 Controller with 10 MB User Memory, USB
SOURCE_NODE          = clm-c6c7b53a862efb46
SOURCE_LABEL         = Allen-Bradley 1756-L83E ControlLogix 5580 Controller with 10 MB User Memory, USB
DESTINATION_NODE     = cmp-f18c46d69089f207
DESTINATION_LABEL    = ControlLogix  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 23c09c46317f50e2665bf4fadc0edab46b805b7b256d9e807f773f62cb5f5293
STRUCTURAL_FLAGS     = POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-04]
```
INDEX                = REFERS_TO-04
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = FactoryTalk Linx Enterprise 6.21.00 Server
SOURCE_NODE          = clm-9d2c55f4ce60d3ce
SOURCE_LABEL         = The Rockwell Software FactoryTalk View SE platform provides the ability to archive continuous
DESTINATION_NODE     = cmp-abbe8a20dd017f4c
DESTINATION_LABEL    = FactoryTalk  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 113f38c655eaad528a008d67e56ea8a2cf0ae1658fe7398d9cdf1e802f88c4a9
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-05]
```
INDEX                = REFERS_TO-05
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 13
EXACT_SOURCE_ANCHOR  = Allen-Bradley 1756-L83E ControlLogix 5580 Controller with 10 MB User Memory, USB
SOURCE_NODE          = clm-42ddee56b1b69748
SOURCE_LABEL         = Allen-Bradley 1756-PA75 ControlLogix, 85-265 VAC Power Supply (13 Amp @ 5V)
DESTINATION_NODE     = cmp-f18c46d69089f207
DESTINATION_LABEL    = ControlLogix  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 23c09c46317f50e2665bf4fadc0edab46b805b7b256d9e807f773f62cb5f5293
STRUCTURAL_FLAGS     = POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-06]
```
INDEX                = REFERS_TO-06
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = FactoryTalk View Studio Site Edition Enterprise
SOURCE_NODE          = clm-94ab79f06ffd636a
SOURCE_LABEL         = The FactoryTalk View SE HMI satisfies the requirements for a method to display the values
DESTINATION_NODE     = cmp-7d1365129f9f1cb3
DESTINATION_LABEL    = FactoryTalk View  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 949b967bfe0056ffdf5fa394767c72eb0107a2be8168e54992619858545211f6
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-07]
```
INDEX                = REFERS_TO-07
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0012
PAGE                 = 4
EXACT_SOURCE_ANCHOR  = PCS – Process Control System (This project’s panel is named PCS-CP01, Process Control System
SOURCE_NODE          = clm-6c64f7b984516de5
SOURCE_LABEL         = MCCPDC PCS-CP01 Alarm Listing which provides among other details, the alarm text and the
DESTINATION_NODE     = cmp-390541921a1520dd
DESTINATION_LABEL    = CP01  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 98ef121b1460fb68db8fe854cafe136ef74aae72a41f161015427570e657cfea
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-08]
```
INDEX                = REFERS_TO-08
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 13
EXACT_SOURCE_ANCHOR  = The delivered system has the Rockwell Software FactoryTalk View SE software loaded onto it, which
SOURCE_NODE          = clm-0ff727712e6d97bc
SOURCE_LABEL         = module which integrates with FactoryTalk View SE.
DESTINATION_NODE     = cmp-bede758f7194a8bc
DESTINATION_LABEL    = FactoryTalk View SE  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 0d268ad3aaafe4b87bff2366bc2f22ff123c06eb7d78d6002502097424341120
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, SAME_CLAIM_MULTIPLE_ENTITY_EDGES, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-09]
```
INDEX                = REFERS_TO-09
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = FactoryTalk Historian DataLink Excel Reporting
SOURCE_NODE          = clm-6b11cf8561ff02ae
SOURCE_LABEL         = is bundled with the FactoryTalk Historian Site Edition product.
DESTINATION_NODE     = cmp-3e541a27d4244457
DESTINATION_LABEL    = FactoryTalk Historian  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 583f544a6fcb2f38f93552457fa42dff594060a3a0644f3520d53355dd06c28e
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-10]
```
INDEX                = REFERS_TO-10
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = FactoryTalk View Studio Site Edition Enterprise
SOURCE_NODE          = clm-b7a54b9180da99b5
SOURCE_LABEL         = saver can be used on the FactoryTalk View SE Client terminals.
DESTINATION_NODE     = cmp-7d1365129f9f1cb3
DESTINATION_LABEL    = FactoryTalk View  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 949b967bfe0056ffdf5fa394767c72eb0107a2be8168e54992619858545211f6
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-11]
```
INDEX                = REFERS_TO-11
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0011
PAGE                 = 4
EXACT_SOURCE_ANCHOR  = XAH-00001-06 DO PCS Status Indicator on PCS-CP-01 PCS
SOURCE_NODE          = clm-9d4de1fffaa03b8e
SOURCE_LABEL         = XAH-00001-06 DO PCS Status Indicator on PCS-CP-01 PCS
DESTINATION_NODE     = cmp-4f00d69b95ea7f43
DESTINATION_LABEL    = PCS-CP-01  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 70a121abda109632aa07c4297f61d3f2eb3580494f6c195dc8665cd275915d8c
STRUCTURAL_FLAGS     = POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-12]
```
INDEX                = REFERS_TO-12
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = FactoryTalk View Studio Site Edition Enterprise
SOURCE_NODE          = clm-4dbcf7a1d683b9e5
SOURCE_LABEL         = FactoryTalk View SE system with Historian.
DESTINATION_NODE     = cmp-7d1365129f9f1cb3
DESTINATION_LABEL    = FactoryTalk View  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 949b967bfe0056ffdf5fa394767c72eb0107a2be8168e54992619858545211f6
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, SAME_CLAIM_MULTIPLE_ENTITY_EDGES, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-13]
```
INDEX                = REFERS_TO-13
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = Engineering Workstation PC located in Room 054 Grid:
SOURCE_NODE          = clm-7ca3cf7ea8f83c3b
SOURCE_LABEL         = Engineering Workstation PC located in Room 054 Grid:
DESTINATION_NODE     = cmp-abb9c1125e4888ab
DESTINATION_LABEL    = engineering workstation  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 2162cdf9b715c33fe9ad134d6ba7bba11dd554d2d330d30d40ed87cdcd0cbb66
STRUCTURAL_FLAGS     = EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-14]
```
INDEX                = REFERS_TO-14
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = Engineering Workstation PC located in Room 054 Grid:
SOURCE_NODE          = clm-94fb7966d31052c8
SOURCE_LABEL         = This Engineering Workstation will be connected to the ethernet network allowing it to be connected to
DESTINATION_NODE     = cmp-abb9c1125e4888ab
DESTINATION_LABEL    = engineering workstation  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 2162cdf9b715c33fe9ad134d6ba7bba11dd554d2d330d30d40ed87cdcd0cbb66
STRUCTURAL_FLAGS     = CROSS_DOCUMENT_ENTITY_ANCHOR, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-15]
```
INDEX                = REFERS_TO-15
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0014
PAGE                 = 4
EXACT_SOURCE_ANCHOR  = PCS – Process Control System (This project’s panel is named PCS-CP01, Process Control System
SOURCE_NODE          = clm-fbd6a3bc8bdf0400
SOURCE_LABEL         = PCS system document named MCCPDC PCS-CP01 Alarm Hard Soft IO Listing.xlsx.
DESTINATION_NODE     = cmp-6e2c2c04d8c5f884
DESTINATION_LABEL    = CP01  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 98ef121b1460fb68db8fe854cafe136ef74aae72a41f161015427570e657cfea
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-16]
```
INDEX                = REFERS_TO-16
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 13
EXACT_SOURCE_ANCHOR  = A ThinManager® software solution provides the thin client architecture for the SCADA/HMI as
SOURCE_NODE          = clm-a05dd4e8265c08cf
SOURCE_LABEL         = UR3.5.2 [MCCPDC 1.4.2.4] - The SI shall implement thin client architecture for the SCADA/HMI to allow
DESTINATION_NODE     = cmp-b4a5b5dee5fac40d
DESTINATION_LABEL    = thin client  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 9e65be5b22dce9efad241759e4b37307f1defb49bf5d1cbc3ec109f40de215f6
STRUCTURAL_FLAGS     = EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-17]
```
INDEX                = REFERS_TO-17
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0014
PAGE                 = 4
EXACT_SOURCE_ANCHOR  = PCS – Process Control System (This project’s panel is named PCS-CP01, Process Control System
SOURCE_NODE          = clm-87687d525d1a41f7
SOURCE_LABEL         = with the PCS-CP01 controller reading a changing value (free-running timer) on the
DESTINATION_NODE     = cmp-6e2c2c04d8c5f884
DESTINATION_LABEL    = CP01  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 98ef121b1460fb68db8fe854cafe136ef74aae72a41f161015427570e657cfea
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-18]
```
INDEX                = REFERS_TO-18
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = FactoryTalk View Studio Site Edition Enterprise
SOURCE_NODE          = clm-795b923879298e87
SOURCE_LABEL         = failure to occur and not interrupt the functions of the system (FactoryTalk View SE, Historian,
DESTINATION_NODE     = cmp-7d1365129f9f1cb3
DESTINATION_LABEL    = FactoryTalk View  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 949b967bfe0056ffdf5fa394767c72eb0107a2be8168e54992619858545211f6
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-19]
```
INDEX                = REFERS_TO-19
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = FactoryTalk Linx Enterprise 6.21.00 Server
SOURCE_NODE          = clm-4dbcf7a1d683b9e5
SOURCE_LABEL         = FactoryTalk View SE system with Historian.
DESTINATION_NODE     = cmp-abbe8a20dd017f4c
DESTINATION_LABEL    = FactoryTalk  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 113f38c655eaad528a008d67e56ea8a2cf0ae1658fe7398d9cdf1e802f88c4a9
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, SAME_CLAIM_MULTIPLE_ENTITY_EDGES, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-20]
```
INDEX                = REFERS_TO-20
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0006
PAGE                 = 4
EXACT_SOURCE_ANCHOR  = interfaces with the FactoryTalk View Site Edition (SE) server system for
SOURCE_NODE          = clm-29adc5d71465fb10
SOURCE_LABEL         = o Microsoft Surface Pro wireless tablets interface with the FactoryTalk View SE
DESTINATION_NODE     = cmp-b21102ec6fb6e323
DESTINATION_LABEL    = FactoryTalk View  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 96832c1e9ae04a858a014f46959a5d68ac88b2dcd6588c324662cf203e4a2563
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-21]
```
INDEX                = REFERS_TO-21
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0006
PAGE                 = 6
EXACT_SOURCE_ANCHOR  = MicroLogix or CompactLogix.
SOURCE_NODE          = clm-6cc6c1327f972048
SOURCE_LABEL         = platform is Allen-Bradley CompactLogix with 1769 Remote I/O.
DESTINATION_NODE     = cmp-86a8b1f8d028ebcf
DESTINATION_LABEL    = CompactLogix  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 47dba39745c735c405ec49597aaf1a2d5c86f3ac45bed527add4ef4ee917e58c
STRUCTURAL_FLAGS     = POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-22]
```
INDEX                = REFERS_TO-22
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = FactoryTalk Linx Enterprise 6.21.00 Server
SOURCE_NODE          = clm-0ff727712e6d97bc
SOURCE_LABEL         = module which integrates with FactoryTalk View SE.
DESTINATION_NODE     = cmp-abbe8a20dd017f4c
DESTINATION_LABEL    = FactoryTalk  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 113f38c655eaad528a008d67e56ea8a2cf0ae1658fe7398d9cdf1e802f88c4a9
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, SAME_CLAIM_MULTIPLE_ENTITY_EDGES, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-23]
```
INDEX                = REFERS_TO-23
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = FactoryTalk Linx Enterprise 6.21.00 Server
SOURCE_NODE          = clm-06dce53dda055401
SOURCE_LABEL         = This FactoryTalk Historian SE license permits up to 250 points to be logged based on a configurable
DESTINATION_NODE     = cmp-abbe8a20dd017f4c
DESTINATION_LABEL    = FactoryTalk  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 113f38c655eaad528a008d67e56ea8a2cf0ae1658fe7398d9cdf1e802f88c4a9
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-24]
```
INDEX                = REFERS_TO-24
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = FactoryTalk Linx Enterprise 6.21.00 Server
SOURCE_NODE          = clm-98c40a5fd232b86e
SOURCE_LABEL         = With the FactoryTalk View SE electronic signature feature, each entry into the FactoryTalk View
DESTINATION_NODE     = cmp-abbe8a20dd017f4c
DESTINATION_LABEL    = FactoryTalk  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 113f38c655eaad528a008d67e56ea8a2cf0ae1658fe7398d9cdf1e802f88c4a9
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-25]
```
INDEX                = REFERS_TO-25
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0012
PAGE                 = 5
EXACT_SOURCE_ANCHOR  = from the FactoryTalk Linx driver itself.
SOURCE_NODE          = clm-1285135088383e25
SOURCE_LABEL         = Where vendor controller status information is required for HMI display and alarming, the FactoryTalk
DESTINATION_NODE     = cmp-542f80a4aae1bb9c
DESTINATION_LABEL    = FactoryTalk  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 1ce8e2840ffdf220962f84ad4ea5e6161580b8b578ea0d5db5dc2bfc959fd12f
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-26]
```
INDEX                = REFERS_TO-26
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = Engineering Workstation PC located in Room 054 Grid:
SOURCE_NODE          = clm-8c4c52cd29ca24e0
SOURCE_LABEL         = accessible to the Engineering Workstation via the ThinManager® technology.
DESTINATION_NODE     = cmp-abb9c1125e4888ab
DESTINATION_LABEL    = engineering workstation  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 2162cdf9b715c33fe9ad134d6ba7bba11dd554d2d330d30d40ed87cdcd0cbb66
STRUCTURAL_FLAGS     = CROSS_DOCUMENT_ENTITY_ANCHOR, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-27]
```
INDEX                = REFERS_TO-27
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 13
EXACT_SOURCE_ANCHOR  = Allen-Bradley 1756-L83E ControlLogix 5580 Controller with 10 MB User Memory, USB
SOURCE_NODE          = clm-b1a5bb323491a5f6
SOURCE_LABEL         = A control system based on Rockwell’s Allen-Bradley ControlLogix Programmable Automation
DESTINATION_NODE     = cmp-f18c46d69089f207
DESTINATION_LABEL    = ControlLogix  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 23c09c46317f50e2665bf4fadc0edab46b805b7b256d9e807f773f62cb5f5293
STRUCTURAL_FLAGS     = POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-28]
```
INDEX                = REFERS_TO-28
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = Engineering Workstation PC located in Room 054 Grid:
SOURCE_NODE          = clm-b717d363a09be36b
SOURCE_LABEL         = The Engineering Workstation consists of:
DESTINATION_NODE     = cmp-abb9c1125e4888ab
DESTINATION_LABEL    = engineering workstation  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 2162cdf9b715c33fe9ad134d6ba7bba11dd554d2d330d30d40ed87cdcd0cbb66
STRUCTURAL_FLAGS     = CROSS_DOCUMENT_ENTITY_ANCHOR, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-29]
```
INDEX                = REFERS_TO-29
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = FactoryTalk Linx Enterprise 6.21.00 Server
SOURCE_NODE          = clm-283c941be1cc0205
SOURCE_LABEL         = Before you can add users and user groups to the accounts list in the FactoryTalk View SE Runtime
DESTINATION_NODE     = cmp-abbe8a20dd017f4c
DESTINATION_LABEL    = FactoryTalk  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 113f38c655eaad528a008d67e56ea8a2cf0ae1658fe7398d9cdf1e802f88c4a9
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, SAME_CLAIM_MULTIPLE_ENTITY_EDGES, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-30]
```
INDEX                = REFERS_TO-30
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = FactoryTalk View Studio Site Edition Enterprise
SOURCE_NODE          = clm-61e4e0fed1bc40fc
SOURCE_LABEL         = FactoryTalk View Site Edition 10-Client Bundle
DESTINATION_NODE     = cmp-7d1365129f9f1cb3
DESTINATION_LABEL    = FactoryTalk View  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 949b967bfe0056ffdf5fa394767c72eb0107a2be8168e54992619858545211f6
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-31]
```
INDEX                = REFERS_TO-31
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = FactoryTalk Linx Enterprise 6.21.00 Server
SOURCE_NODE          = clm-b5241db42f588d71
SOURCE_LABEL         = FactoryTalk Historian software.
DESTINATION_NODE     = cmp-abbe8a20dd017f4c
DESTINATION_LABEL    = FactoryTalk  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 113f38c655eaad528a008d67e56ea8a2cf0ae1658fe7398d9cdf1e802f88c4a9
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-32]
```
INDEX                = REFERS_TO-32
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0006
PAGE                 = 6
EXACT_SOURCE_ANCHOR  = MicroLogix or CompactLogix.
SOURCE_NODE          = clm-0c8d2c4ffc97a6cc
SOURCE_LABEL         = MicroLogix or CompactLogix.
DESTINATION_NODE     = cmp-86a8b1f8d028ebcf
DESTINATION_LABEL    = CompactLogix  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 47dba39745c735c405ec49597aaf1a2d5c86f3ac45bed527add4ef4ee917e58c
STRUCTURAL_FLAGS     = POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-33]
```
INDEX                = REFERS_TO-33
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0014
PAGE                 = 4
EXACT_SOURCE_ANCHOR  = PCS – Process Control System (This project’s panel is named PCS-CP01, Process Control System
SOURCE_NODE          = clm-6eb73a39503aa50c
SOURCE_LABEL         = MCCPDC PCS-CP01 Alarm Hard Soft IO Listing.xlsx
DESTINATION_NODE     = cmp-46697d1bb453b5b5
DESTINATION_LABEL    = PCS-CP01  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 98ef121b1460fb68db8fe854cafe136ef74aae72a41f161015427570e657cfea
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-34]
```
INDEX                = REFERS_TO-34
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 49
EXACT_SOURCE_ANCHOR  = CompactLogix (5380 series).
SOURCE_NODE          = clm-8ddb76ea31248021
SOURCE_LABEL         = CompactLogix (5380 series).
DESTINATION_NODE     = cmp-d7b4d5336092b2a2
DESTINATION_LABEL    = CompactLogix  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = a2c25d145432df816c00585a3797b74c9207787debb234d2af74829dd112f562
STRUCTURAL_FLAGS     = POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-35]
```
INDEX                = REFERS_TO-35
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0011
PAGE                 = 3
EXACT_SOURCE_ANCHOR  = PCS – Process Control System (This project’s panel is named PCS-CP01, Process Control System
SOURCE_NODE          = clm-976f7286cc6e5477
SOURCE_LABEL         = which is hardwired to the PCS-CP01 system.
DESTINATION_NODE     = cmp-1a1fb25a2268a32c
DESTINATION_LABEL    = CP01  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 98ef121b1460fb68db8fe854cafe136ef74aae72a41f161015427570e657cfea
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-36]
```
INDEX                = REFERS_TO-36
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = FactoryTalk View Studio Site Edition Enterprise
SOURCE_NODE          = clm-a1e848f0e25dd024
SOURCE_LABEL         = FactoryTalk View SE makes efficient use of the security features built into the underlying Microsoft
DESTINATION_NODE     = cmp-7d1365129f9f1cb3
DESTINATION_LABEL    = FactoryTalk View  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 949b967bfe0056ffdf5fa394767c72eb0107a2be8168e54992619858545211f6
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-37]
```
INDEX                = REFERS_TO-37
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = FactoryTalk Linx Enterprise 6.21.00 Server
SOURCE_NODE          = clm-faa012ff31ef920f
SOURCE_LABEL         = The Rockwell Automation FactoryTalk Linx Enterprise software is an OPC server and provides the
DESTINATION_NODE     = cmp-5e261c0b14cea343
DESTINATION_LABEL    = FactoryTalk Linx  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 113f38c655eaad528a008d67e56ea8a2cf0ae1658fe7398d9cdf1e802f88c4a9
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-38]
```
INDEX                = REFERS_TO-38
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = FactoryTalk View Studio Site Edition Enterprise
SOURCE_NODE          = clm-c77530d053a05c36
SOURCE_LABEL         = If the user logs out of FactoryTalk View SE and again requires access, the user must reenter the login ID
DESTINATION_NODE     = cmp-7d1365129f9f1cb3
DESTINATION_LABEL    = FactoryTalk View  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 949b967bfe0056ffdf5fa394767c72eb0107a2be8168e54992619858545211f6
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-39]
```
INDEX                = REFERS_TO-39
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 13
EXACT_SOURCE_ANCHOR  = The delivered system has the Rockwell Software FactoryTalk View SE software loaded onto it, which
SOURCE_NODE          = clm-283c941be1cc0205
SOURCE_LABEL         = Before you can add users and user groups to the accounts list in the FactoryTalk View SE Runtime
DESTINATION_NODE     = cmp-bede758f7194a8bc
DESTINATION_LABEL    = FactoryTalk View SE  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 0d268ad3aaafe4b87bff2366bc2f22ff123c06eb7d78d6002502097424341120
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, SAME_CLAIM_MULTIPLE_ENTITY_EDGES, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-40]
```
INDEX                = REFERS_TO-40
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = FactoryTalk View Studio Site Edition Enterprise
SOURCE_NODE          = clm-58109fb8353c52ee
SOURCE_LABEL         = FactoryTalk View SE system.
DESTINATION_NODE     = cmp-7d1365129f9f1cb3
DESTINATION_LABEL    = FactoryTalk View  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 949b967bfe0056ffdf5fa394767c72eb0107a2be8168e54992619858545211f6
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-41]
```
INDEX                = REFERS_TO-41
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 49
EXACT_SOURCE_ANCHOR  = CompactLogix (5380 series).
SOURCE_NODE          = clm-6b764277d8713282
SOURCE_LABEL         = platform is Allen-Bradley CompactLogix with 1769 Remote I/O.
DESTINATION_NODE     = cmp-d7b4d5336092b2a2
DESTINATION_LABEL    = CompactLogix  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = a2c25d145432df816c00585a3797b74c9207787debb234d2af74829dd112f562
STRUCTURAL_FLAGS     = POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-42]
```
INDEX                = REFERS_TO-42
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0014
PAGE                 = 5
EXACT_SOURCE_ANCHOR  = is handled in the PLC and not in the FactoryTalk Alarm and Events
SOURCE_NODE          = clm-7398082f60d752fb
SOURCE_LABEL         = is handled in the PLC and not in the FactoryTalk Alarm and Events
DESTINATION_NODE     = cmp-28db170d5a86219e
DESTINATION_LABEL    = FactoryTalk  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 2b7f21e6a9a6142acae152f03fa5d3b21f609333b3059e79bd5cda80de16b59d
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-43]
```
INDEX                = REFERS_TO-43
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = FactoryTalk Linx Enterprise 6.21.00 Server
SOURCE_NODE          = clm-3d9f2e80ca8140a7
SOURCE_LABEL         = The Windows-linked All Users group is automatically added to the FactoryTalk Runtime Security
DESTINATION_NODE     = cmp-abbe8a20dd017f4c
DESTINATION_LABEL    = FactoryTalk  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 113f38c655eaad528a008d67e56ea8a2cf0ae1658fe7398d9cdf1e802f88c4a9
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-44]
```
INDEX                = REFERS_TO-44
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0011
PAGE                 = 4
EXACT_SOURCE_ANCHOR  = in the FactoryTalk Historian Site Edition (SE) software product.
SOURCE_NODE          = clm-8346ed7dcf6068b5
SOURCE_LABEL         = points shall be configured to be logged in the FactoryTalk Historian software product.
DESTINATION_NODE     = cmp-12d7e381df0cd835
DESTINATION_LABEL    = FactoryTalk  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 233dcd3ed90cec275cf352676bae2f7c8e4ff4c55afe12a4df30314f788c5e07
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-45]
```
INDEX                = REFERS_TO-45
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = FactoryTalk Linx Enterprise 6.21.00 Server
SOURCE_NODE          = clm-660c37ee08693714
SOURCE_LABEL         = FactoryTalk View SE uses a
DESTINATION_NODE     = cmp-abbe8a20dd017f4c
DESTINATION_LABEL    = FactoryTalk  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 113f38c655eaad528a008d67e56ea8a2cf0ae1658fe7398d9cdf1e802f88c4a9
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, SAME_CLAIM_MULTIPLE_ENTITY_EDGES, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-46]
```
INDEX                = REFERS_TO-46
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 13
EXACT_SOURCE_ANCHOR  = The delivered system has the Rockwell Software FactoryTalk View SE software loaded onto it, which
SOURCE_NODE          = clm-660c37ee08693714
SOURCE_LABEL         = FactoryTalk View SE uses a
DESTINATION_NODE     = cmp-bede758f7194a8bc
DESTINATION_LABEL    = FactoryTalk View SE  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 0d268ad3aaafe4b87bff2366bc2f22ff123c06eb7d78d6002502097424341120
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, SAME_CLAIM_MULTIPLE_ENTITY_EDGES, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-47]
```
INDEX                = REFERS_TO-47
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0014
PAGE                 = 4
EXACT_SOURCE_ANCHOR  = PCS – Process Control System (This project’s panel is named PCS-CP01, Process Control System
SOURCE_NODE          = clm-5912f207afad4c27
SOURCE_LABEL         = PCS – Process Control System (This project’s panel is named PCS-CP01, Process Control System
DESTINATION_NODE     = cmp-46697d1bb453b5b5
DESTINATION_LABEL    = PCS-CP01  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 98ef121b1460fb68db8fe854cafe136ef74aae72a41f161015427570e657cfea
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-48]
```
INDEX                = REFERS_TO-48
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 1
EXACT_SOURCE_ANCHOR  = PLC Interfaces (PCS-CP01 and other Vendor Systems) .....................................
SOURCE_NODE          = clm-0d8cea5bc167a213
SOURCE_LABEL         = The PLC application revision is populated into a tag in the PCS-CP01 PLC.
DESTINATION_NODE     = cmp-05b6d7591767f621
DESTINATION_LABEL    = CP01  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 4b01e10bb51e7dda41e85bef86618085eba1f03a782bf3d1d63ac21c84255c4d
STRUCTURAL_FLAGS     = TOC_OR_INDEX_CONTEXT, NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-49]
```
INDEX                = REFERS_TO-49
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0014
PAGE                 = 4
EXACT_SOURCE_ANCHOR  = PCS – Process Control System (This project’s panel is named PCS-CP01, Process Control System
SOURCE_NODE          = clm-1c7617c4ff8a8c27
SOURCE_LABEL         = WFI_Comms_OK DI PCS-CP01 successfully Water for Injection
DESTINATION_NODE     = cmp-6e2c2c04d8c5f884
DESTINATION_LABEL    = CP01  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 98ef121b1460fb68db8fe854cafe136ef74aae72a41f161015427570e657cfea
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-50]
```
INDEX                = REFERS_TO-50
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = FactoryTalk Linx Enterprise 6.21.00 Server
SOURCE_NODE          = clm-5833a893ed98d1c0
SOURCE_LABEL         = FactoryTalk View SE security is based on a system of letter codes (A-P) which are assigned to the
DESTINATION_NODE     = cmp-abbe8a20dd017f4c
DESTINATION_LABEL    = FactoryTalk  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 113f38c655eaad528a008d67e56ea8a2cf0ae1658fe7398d9cdf1e802f88c4a9
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-51]
```
INDEX                = REFERS_TO-51
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = FactoryTalk View Studio Site Edition Enterprise
SOURCE_NODE          = clm-0ff727712e6d97bc
SOURCE_LABEL         = module which integrates with FactoryTalk View SE.
DESTINATION_NODE     = cmp-7d1365129f9f1cb3
DESTINATION_LABEL    = FactoryTalk View  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 949b967bfe0056ffdf5fa394767c72eb0107a2be8168e54992619858545211f6
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, SAME_CLAIM_MULTIPLE_ENTITY_EDGES, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-52]
```
INDEX                = REFERS_TO-52
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = FactoryTalk View Studio Site Edition Enterprise
SOURCE_NODE          = clm-752158d06df54dca
SOURCE_LABEL         = FactoryTalk View SE system, the user is required to enter his/ her login and password to access
DESTINATION_NODE     = cmp-7d1365129f9f1cb3
DESTINATION_LABEL    = FactoryTalk View  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 949b967bfe0056ffdf5fa394767c72eb0107a2be8168e54992619858545211f6
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-53]
```
INDEX                = REFERS_TO-53
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 13
EXACT_SOURCE_ANCHOR  = Administrator and Maintenance login security levels.
SOURCE_NODE          = clm-e0774e5d64c9685e
SOURCE_LABEL         = Administrator  Ability to change input values via simulation feature A, B, C, D, E
DESTINATION_NODE     = act-bc6a65907ef2903f
DESTINATION_LABEL    = Administrator  (actor)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 036322553783cf6a8b22caba88dea1605c429c8ab768c08aba4f2e8f375c0790
STRUCTURAL_FLAGS     = EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-54]
```
INDEX                = REFERS_TO-54
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = FactoryTalk View Studio Site Edition Enterprise
SOURCE_NODE          = clm-5de08577f569808d
SOURCE_LABEL         = FactoryTalk View SE Security
DESTINATION_NODE     = cmp-7d1365129f9f1cb3
DESTINATION_LABEL    = FactoryTalk View  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 949b967bfe0056ffdf5fa394767c72eb0107a2be8168e54992619858545211f6
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-55]
```
INDEX                = REFERS_TO-55
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 49
EXACT_SOURCE_ANCHOR  = CompactLogix (5380 series).
SOURCE_NODE          = clm-9f60bff6222a21cc
SOURCE_LABEL         = OEM vendor on-skid control system platform is Allen-Bradley CompactLogix (5380 series).-F16.00, 49
DESTINATION_NODE     = cmp-d7b4d5336092b2a2
DESTINATION_LABEL    = CompactLogix  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = a2c25d145432df816c00585a3797b74c9207787debb234d2af74829dd112f562
STRUCTURAL_FLAGS     = POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-56]
```
INDEX                = REFERS_TO-56
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = FactoryTalk Linx Enterprise 6.21.00 Server
SOURCE_NODE          = clm-a5e08d738996fe76
SOURCE_LABEL         = FactoryTalk Activation Manager 4.05.01 Server
DESTINATION_NODE     = cmp-abbe8a20dd017f4c
DESTINATION_LABEL    = FactoryTalk  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 113f38c655eaad528a008d67e56ea8a2cf0ae1658fe7398d9cdf1e802f88c4a9
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-57]
```
INDEX                = REFERS_TO-57
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0006
PAGE                 = 4
EXACT_SOURCE_ANCHOR  = interfaces with the FactoryTalk View Site Edition (SE) server system for
SOURCE_NODE          = clm-e5f755410c81dfcc
SOURCE_LABEL         = hardwired signals terminated on its IO cards and a larger supervisory FactoryTalk View SE system with
DESTINATION_NODE     = cmp-4aafaa7b5bad21fe
DESTINATION_LABEL    = FactoryTalk  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 96832c1e9ae04a858a014f46959a5d68ac88b2dcd6588c324662cf203e4a2563
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-58]
```
INDEX                = REFERS_TO-58
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 9
EXACT_SOURCE_ANCHOR  = FactoryTalk View Studio Site Edition Enterprise
SOURCE_NODE          = clm-aadf96dd3436de4f
SOURCE_LABEL         = the FactoryTalk View SE server.
DESTINATION_NODE     = cmp-7d1365129f9f1cb3
DESTINATION_LABEL    = FactoryTalk View  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 949b967bfe0056ffdf5fa394767c72eb0107a2be8168e54992619858545211f6
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-59]
```
INDEX                = REFERS_TO-59
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0014
PAGE                 = 4
EXACT_SOURCE_ANCHOR  = PCS – Process Control System (This project’s panel is named PCS-CP01, Process Control System
SOURCE_NODE          = clm-a691a115a829f271
SOURCE_LABEL         = Wash_Ster_Comms_OK DI PCS-CP01 successfully Washer/Sterilizer OEM
DESTINATION_NODE     = cmp-6e2c2c04d8c5f884
DESTINATION_LABEL    = CP01  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 98ef121b1460fb68db8fe854cafe136ef74aae72a41f161015427570e657cfea
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

### [REF-60]
```
INDEX                = REFERS_TO-60
RELATION             = refers_to
SOURCE_DOCUMENT      = RW-0005
PAGE                 = 13
EXACT_SOURCE_ANCHOR  = The delivered system has the Rockwell Software FactoryTalk View SE software loaded onto it, which
SOURCE_NODE          = clm-3918902aecb5bc12
SOURCE_LABEL         = FactoryTalk View SE system and the PLCs (PCS-CP01 and the other vendor systems).
DESTINATION_NODE     = cmp-bede758f7194a8bc
DESTINATION_LABEL    = FactoryTalk View SE  (system_component)
REQUIREMENT_OR_REF   = literal_name
PROVENANCE_HASH      = 0d268ad3aaafe4b87bff2366bc2f22ff123c06eb7d78d6002502097424341120
STRUCTURAL_FLAGS     = NESTED_ENTITY_NAME, POSSIBLE_ALIAS, EXACT_LITERAL_MATCH
HUMAN_VERDICT        = 
HUMAN_NOTE           = 
```

---

## Resumen de flags estructurales (informativo)

```
EXACT_LITERAL_MATCH                 = 73
POSSIBLE_ALIAS                      = 54
NESTED_ENTITY_NAME                  = 45
CROSS_DOCUMENT_ENTITY_ANCHOR        = 20
SAME_CLAIM_MULTIPLE_ENTITY_EDGES    = 13
TOC_OR_INDEX_CONTEXT                = 1
```

## Instrucciones para Capa 9 / QA

1. Para cada fila, fijar `HUMAN_VERDICT` ∈ {CORRECT, WRONG_NODE, SPURIOUS, AMBIGUOUS} y `HUMAN_NOTE`.
2. Los `STRUCTURAL_FLAGS` son pistas automáticas, no prejuzgan el veredicto.
3. Juzgar cada `refers_to` por `SOURCE_LABEL` (el claim), no por la ancla del nodo entidad (que apunta a la primera mención del componente en el proyecto — flag `CROSS_DOCUMENT_ENTITY_ANCHOR`).
4. Juzgar cada `tested_by` por si el claim fuente (URS/FS) que cita `3.2.3` / `F05.05` se refiere realmente al mismo requisito/función que prueba ese caso SAT de RW-0003.
5. Al terminar: registrar el resultado por el mecanismo de gobernanza autenticado (NO editar este Markdown como firma). El fichero fuente `H10_NEW_RELATIONS_SAMPLE_FOR_HUMAN.json` conserva su `sample_sha256` como ancla del conjunto revisado.

```
E1_STATUS = PENDING_HUMAN
```