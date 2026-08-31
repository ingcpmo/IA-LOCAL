# E1 — 2ª REVISIÓN HUMANA (post FIX-A) · PAQUETE DE 77 RELACIONES

**Fecha:** 2026-08-31 · **Muestra:** `H10_NEW_RELATIONS_SAMPLE_FOR_HUMAN.json` `sample_sha256 = c2ca5aaa36e9904b77cecf266cfa6645ab76949828074c857a360a5bf75ad3fd` · 17 `tested_by` + 60 `refers_to` (regenerada por `h10_regen_e1_sample.py` tras FIX-A).

**E1-1 (histórica, PRESERVADA):** muestra `f56d4bab…` · verdict_set `a533bf4a…` · `E1_ACCEPTANCE=FAIL` (CORRECT=26 / WRONG_NODE=30 / SPURIOUS=11 / AMBIGUOUS=10).

**Instrucción:** decide `NEW_HUMAN_VERDICT ∈ {CORRECT, WRONG_NODE, SPURIOUS, AMBIGUOUS}` por fila. **No reutilices el veredicto anterior aunque la relación sea la misma.** `PREVIOUS_VERDICT` no está disponible por fila (E1-1 se registró sólo en agregado). `SAME_RELATION_AS_PREVIOUS` indica si esa arista `(claim, entidad)` estaba en la muestra E1-1.

**Criterio de aceptación (literal, del plan):** *E1 valida que las relaciones nuevas no sean ruido.*

---

## Fila 1 · `tested_by` · RW-0006 p.6

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-ffce50cb975b2635`:

  > 3.2.3 The Equipment shall have critical alarms and warnings as listed in

- **destino** `test` `tst-c51272c4621d673e` = **UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Al** · tabla `SAT-P192-T1`

- **ancla de provenance del destino:** `Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date)
UR3.2.3 The Equipment shall hav`

- **provenance_hash** `8b054b046f6700d3112c0d6dfe1948e1174dac27c8e44a9f8309cd9aeb51a2aa` · **ref** `3.2.3`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 2 · `tested_by` · RW-0005 p.13

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-9b30567369b392a1`:

  > UR4.1.1 [MCCPDC 3.2.3] - The physical servers shall be two (2) redundant Rockwell VersaVirtual™

- **destino** `test` `tst-c51272c4621d673e` = **UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Al** · tabla `SAT-P192-T1`

- **ancla de provenance del destino:** `Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date)
UR3.2.3 The Equipment shall hav`

- **provenance_hash** `8b054b046f6700d3112c0d6dfe1948e1174dac27c8e44a9f8309cd9aeb51a2aa` · **ref** `3.2.3`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 3 · `tested_by` · RW-0005 p.7

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-a27011aa844768f7`:

  > UR4.1.1 [MCCPDC 3.2.3] - The physical servers shall be…

- **destino** `test` `tst-c51272c4621d673e` = **UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Al** · tabla `SAT-P192-T1`

- **ancla de provenance del destino:** `Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date)
UR3.2.3 The Equipment shall hav`

- **provenance_hash** `8b054b046f6700d3112c0d6dfe1948e1174dac27c8e44a9f8309cd9aeb51a2aa` · **ref** `3.2.3`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 4 · `tested_by` · RW-0005 p.54

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-c16b3a168d374cef`:

  > screen, accessible by Admin and Maintenance personnel.-F05.05, 24

- **destino** `test` `tst-b192abb965189ab2` = **F05.05: Input State and Simulation Review Screen** · tabla `SAT-P157-T1`

- **ancla de provenance del destino:** `Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date)
F05.05: Input State and Simulat`

- **provenance_hash** `cd0bf8a2144e2997662f6afbf8ad18789647d8ae306aed3bff1fe201aa484ade` · **ref** `F05.05`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 5 · `tested_by` · RW-0005 p.54

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-160f8415ea17e786`:

  > UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Alarms.

- **destino** `test` `tst-c51272c4621d673e` = **UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Al** · tabla `SAT-P192-T1`

- **ancla de provenance del destino:** `Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date)
UR3.2.3 The Equipment shall hav`

- **provenance_hash** `8b054b046f6700d3112c0d6dfe1948e1174dac27c8e44a9f8309cd9aeb51a2aa` · **ref** `3.2.3`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 6 · `tested_by` · RW-0006 p.6

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-ba26e44e69dabe0f`:

  > The list of critical alarms in the table is not intended to be a are identified.

- **destino** `test` `tst-c51272c4621d673e` = **UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Al** · tabla `SAT-P192-T1`

- **ancla de provenance del destino:** `Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date)
UR3.2.3 The Equipment shall hav`

- **provenance_hash** `8b054b046f6700d3112c0d6dfe1948e1174dac27c8e44a9f8309cd9aeb51a2aa` · **ref** `3.2.3`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 7 · `tested_by` · RW-0006 p.6

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-1c7584b555c57656`:

  > included in the Functional Specification document.

- **destino** `test` `tst-c51272c4621d673e` = **UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Al** · tabla `SAT-P192-T1`

- **ancla de provenance del destino:** `Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date)
UR3.2.3 The Equipment shall hav`

- **provenance_hash** `8b054b046f6700d3112c0d6dfe1948e1174dac27c8e44a9f8309cd9aeb51a2aa` · **ref** `3.2.3`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 8 · `tested_by` · RW-0006 p.11

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-ae6b1677b2211968`:

  > 4.1.1 [MCCPDC 3.2.3] - The physical servers shall be two (2) redundant

- **destino** `test` `tst-c51272c4621d673e` = **UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Al** · tabla `SAT-P192-T1`

- **ancla de provenance del destino:** `Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date)
UR3.2.3 The Equipment shall hav`

- **provenance_hash** `8b054b046f6700d3112c0d6dfe1948e1174dac27c8e44a9f8309cd9aeb51a2aa` · **ref** `3.2.3`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 9 · `tested_by` · RW-0006 p.6

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-41c127a212f199c8`:

  > comprehensive list of all alarms for the system.

- **destino** `test` `tst-c51272c4621d673e` = **UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Al** · tabla `SAT-P192-T1`

- **ancla de provenance del destino:** `Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date)
UR3.2.3 The Equipment shall hav`

- **provenance_hash** `8b054b046f6700d3112c0d6dfe1948e1174dac27c8e44a9f8309cd9aeb51a2aa` · **ref** `3.2.3`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 10 · `tested_by` · RW-0005 p.54

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-8d03847d17feacd3`:

  > UR4.1.1 [MCCPDC 3.2.3] - The physical servers shall be two (2) redundant Rockwell VersaVirtual™ Appliances suitable for

- **destino** `test` `tst-c51272c4621d673e` = **UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Al** · tabla `SAT-P192-T1`

- **ancla de provenance del destino:** `Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date)
UR3.2.3 The Equipment shall hav`

- **provenance_hash** `8b054b046f6700d3112c0d6dfe1948e1174dac27c8e44a9f8309cd9aeb51a2aa` · **ref** `3.2.3`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 11 · `tested_by` · RW-0005 p.13

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-8137fdc377337cb4`:

  > specification (See 3.1.9, F05.05:

- **destino** `test` `tst-0b2093f8f99bd8d5` = **F05.05: Input State and Simulation Review Screen** · tabla `SAT-P158-T1`

- **ancla de provenance del destino:** `Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date)
F05.05: Input State and Simulat`

- **provenance_hash** `b81489fbaa3fe5665a989354c4b8214bf591cb19b4997d5c556e77ad8a971f14` · **ref** `F05.05`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 12 · `tested_by` · RW-0006 p.6

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-dd1fb6f61698250c`:

  > List of Critical-to-Quality Alarms.

- **destino** `test` `tst-c51272c4621d673e` = **UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Al** · tabla `SAT-P192-T1`

- **ancla de provenance del destino:** `Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date)
UR3.2.3 The Equipment shall hav`

- **provenance_hash** `8b054b046f6700d3112c0d6dfe1948e1174dac27c8e44a9f8309cd9aeb51a2aa` · **ref** `3.2.3`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 13 · `tested_by` · RW-0005 p.7

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-c2451957602c04bb`:

  > UR4.1.1 [MCCPDC 3.2.3] - The physical servers shall be ...

- **destino** `test` `tst-c51272c4621d673e` = **UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Al** · tabla `SAT-P192-T1`

- **ancla de provenance del destino:** `Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date)
UR3.2.3 The Equipment shall hav`

- **provenance_hash** `8b054b046f6700d3112c0d6dfe1948e1174dac27c8e44a9f8309cd9aeb51a2aa` · **ref** `3.2.3`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 14 · `tested_by` · RW-0005 p.13

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-ccb85cc5b3a7ee9a`:

  > UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical

- **destino** `test` `tst-c51272c4621d673e` = **UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Al** · tabla `SAT-P192-T1`

- **ancla de provenance del destino:** `Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date)
UR3.2.3 The Equipment shall hav`

- **provenance_hash** `8b054b046f6700d3112c0d6dfe1948e1174dac27c8e44a9f8309cd9aeb51a2aa` · **ref** `3.2.3`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 15 · `tested_by` · RW-0005 p.13

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-8137fdc377337cb4`:

  > specification (See 3.1.9, F05.05:

- **destino** `test` `tst-b192abb965189ab2` = **F05.05: Input State and Simulation Review Screen** · tabla `SAT-P157-T1`

- **ancla de provenance del destino:** `Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date)
F05.05: Input State and Simulat`

- **provenance_hash** `cd0bf8a2144e2997662f6afbf8ad18789647d8ae306aed3bff1fe201aa484ade` · **ref** `F05.05`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 16 · `tested_by` · RW-0005 p.54

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-c16b3a168d374cef`:

  > screen, accessible by Admin and Maintenance personnel.-F05.05, 24

- **destino** `test` `tst-0b2093f8f99bd8d5` = **F05.05: Input State and Simulation Review Screen** · tabla `SAT-P158-T1`

- **ancla de provenance del destino:** `Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date)
F05.05: Input State and Simulat`

- **provenance_hash** `b81489fbaa3fe5665a989354c4b8214bf591cb19b4997d5c556e77ad8a971f14` · **ref** `F05.05`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 17 · `tested_by` · RW-0005 p.7

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-8f33dd65ec88cc74`:

  > UR4.1.1 requirement includes in its text, the customer reference number MCCPDC 3.2.3, followed by

- **destino** `test` `tst-c51272c4621d673e` = **UR3.2.3 The Equipment shall have critical alarms and warnings as listed in (URS) Table 1- List of Critical-to-Quality Al** · tabla `SAT-P192-T1`

- **ancla de provenance del destino:** `Item | Test Description | Expected Result | Actual Result | Deviat- ion ID | Result (Pass/ Fail) | Performed By (Initial & Date)
UR3.2.3 The Equipment shall hav`

- **provenance_hash** `8b054b046f6700d3112c0d6dfe1948e1174dac27c8e44a9f8309cd9aeb51a2aa` · **ref** `3.2.3`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 18 · `refers_to` · RW-0005 p.13

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-c6c7b53a862efb46`:

  > Allen-Bradley 1756-L83E ControlLogix 5580 Controller with 10 MB User Memory, USB

- **destino** `system_component` `cmp-f18c46d69089f207` = **ControlLogix**

- **ancla de provenance del destino:** `Allen-Bradley 1756-L83E ControlLogix 5580 Controller with 10 MB User Memory, USB`

- **provenance_hash** `23c09c46317f50e2665bf4fadc0edab46b805b7b256d9e807f773f62cb5f5293` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 19 · `refers_to` · RW-0005 p.13

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-42ddee56b1b69748`:

  > Allen-Bradley 1756-PA75 ControlLogix, 85-265 VAC Power Supply (13 Amp @ 5V)

- **destino** `system_component` `cmp-f18c46d69089f207` = **ControlLogix**

- **ancla de provenance del destino:** `Allen-Bradley 1756-L83E ControlLogix 5580 Controller with 10 MB User Memory, USB`

- **provenance_hash** `23c09c46317f50e2665bf4fadc0edab46b805b7b256d9e807f773f62cb5f5293` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 20 · `refers_to` · RW-0005 p.40

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-0ff727712e6d97bc`:

  > module which integrates with FactoryTalk View SE.

- **destino** `system_component` `cmp-bede758f7194a8bc` = **FactoryTalk View SE**

- **ancla de provenance del destino:** `The delivered system has the Rockwell Software FactoryTalk View SE software loaded onto it, which`

- **provenance_hash** `0d268ad3aaafe4b87bff2366bc2f22ff123c06eb7d78d6002502097424341120` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 21 · `refers_to` · RW-0005 p.51

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-6b11cf8561ff02ae`:

  > is bundled with the FactoryTalk Historian Site Edition product.

- **destino** `system_component` `cmp-3e541a27d4244457` = **FactoryTalk Historian**

- **ancla de provenance del destino:** `FactoryTalk Historian DataLink Excel Reporting`

- **provenance_hash** `583f544a6fcb2f38f93552457fa42dff594060a3a0644f3520d53355dd06c28e` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 22 · `refers_to` · RW-0011 p.4

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-9d4de1fffaa03b8e`:

  > XAH-00001-06 DO PCS Status Indicator on PCS-CP-01 PCS

- **destino** `system_component` `cmp-4f00d69b95ea7f43` = **PCS-CP-01**

- **ancla de provenance del destino:** `XAH-00001-06 DO PCS Status Indicator on PCS-CP-01 PCS`

- **provenance_hash** `70a121abda109632aa07c4297f61d3f2eb3580494f6c195dc8665cd275915d8c` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 23 · `refers_to` · RW-0005 p.9

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-7ca3cf7ea8f83c3b`:

  > Engineering Workstation PC located in Room 054 Grid:

- **destino** `system_component` `cmp-abb9c1125e4888ab` = **engineering workstation**

- **ancla de provenance del destino:** `Engineering Workstation PC located in Room 054 Grid:`

- **provenance_hash** `2162cdf9b715c33fe9ad134d6ba7bba11dd554d2d330d30d40ed87cdcd0cbb66` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 24 · `refers_to` · RW-0005 p.13

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-94fb7966d31052c8`:

  > This Engineering Workstation will be connected to the ethernet network allowing it to be connected to

- **destino** `system_component` `cmp-abb9c1125e4888ab` = **engineering workstation**

- **ancla de provenance del destino:** `Engineering Workstation PC located in Room 054 Grid:`

- **provenance_hash** `2162cdf9b715c33fe9ad134d6ba7bba11dd554d2d330d30d40ed87cdcd0cbb66` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 25 · `refers_to` · RW-0005 p.49

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-a05dd4e8265c08cf`:

  > UR3.5.2 [MCCPDC 1.4.2.4] - The SI shall implement thin client architecture for the SCADA/HMI to allow

- **destino** `system_component` `cmp-b4a5b5dee5fac40d` = **thin client**

- **ancla de provenance del destino:** `A ThinManager® software solution provides the thin client architecture for the SCADA/HMI as`

- **provenance_hash** `9e65be5b22dce9efad241759e4b37307f1defb49bf5d1cbc3ec109f40de215f6` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 26 · `refers_to` · RW-0006 p.6

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-6cc6c1327f972048`:

  > platform is Allen-Bradley CompactLogix with 1769 Remote I/O.

- **destino** `system_component` `cmp-86a8b1f8d028ebcf` = **CompactLogix**

- **ancla de provenance del destino:** `MicroLogix or CompactLogix.`

- **provenance_hash** `47dba39745c735c405ec49597aaf1a2d5c86f3ac45bed527add4ef4ee917e58c` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 27 · `refers_to` · RW-0012 p.5

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-1285135088383e25`:

  > Where vendor controller status information is required for HMI display and alarming, the FactoryTalk

- **destino** `system_component` `cmp-542f80a4aae1bb9c` = **FactoryTalk**

- **ancla de provenance del destino:** `from the FactoryTalk Linx driver itself.`

- **provenance_hash** `1ce8e2840ffdf220962f84ad4ea5e6161580b8b578ea0d5db5dc2bfc959fd12f` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 28 · `refers_to` · RW-0005 p.51

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-8c4c52cd29ca24e0`:

  > accessible to the Engineering Workstation via the ThinManager® technology.

- **destino** `system_component` `cmp-abb9c1125e4888ab` = **engineering workstation**

- **ancla de provenance del destino:** `Engineering Workstation PC located in Room 054 Grid:`

- **provenance_hash** `2162cdf9b715c33fe9ad134d6ba7bba11dd554d2d330d30d40ed87cdcd0cbb66` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 29 · `refers_to` · RW-0005 p.13

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-b1a5bb323491a5f6`:

  > A control system based on Rockwell’s Allen-Bradley ControlLogix Programmable Automation

- **destino** `system_component` `cmp-f18c46d69089f207` = **ControlLogix**

- **ancla de provenance del destino:** `Allen-Bradley 1756-L83E ControlLogix 5580 Controller with 10 MB User Memory, USB`

- **provenance_hash** `23c09c46317f50e2665bf4fadc0edab46b805b7b256d9e807f773f62cb5f5293` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 30 · `refers_to` · RW-0005 p.13

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-b717d363a09be36b`:

  > The Engineering Workstation consists of:

- **destino** `system_component` `cmp-abb9c1125e4888ab` = **engineering workstation**

- **ancla de provenance del destino:** `Engineering Workstation PC located in Room 054 Grid:`

- **provenance_hash** `2162cdf9b715c33fe9ad134d6ba7bba11dd554d2d330d30d40ed87cdcd0cbb66` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 31 · `refers_to` · RW-0005 p.9

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-61e4e0fed1bc40fc`:

  > FactoryTalk View Site Edition 10-Client Bundle

- **destino** `system_component` `cmp-7d1365129f9f1cb3` = **FactoryTalk View**

- **ancla de provenance del destino:** `FactoryTalk View Studio Site Edition Enterprise`

- **provenance_hash** `949b967bfe0056ffdf5fa394767c72eb0107a2be8168e54992619858545211f6` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 32 · `refers_to` · RW-0006 p.6

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-0c8d2c4ffc97a6cc`:

  > MicroLogix or CompactLogix.

- **destino** `system_component` `cmp-86a8b1f8d028ebcf` = **CompactLogix**

- **ancla de provenance del destino:** `MicroLogix or CompactLogix.`

- **provenance_hash** `47dba39745c735c405ec49597aaf1a2d5c86f3ac45bed527add4ef4ee917e58c` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 33 · `refers_to` · RW-0014 p.18

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-6eb73a39503aa50c`:

  > MCCPDC PCS-CP01 Alarm Hard Soft IO Listing.xlsx

- **destino** `system_component` `cmp-46697d1bb453b5b5` = **PCS-CP01**

- **ancla de provenance del destino:** `PCS – Process Control System (This project’s panel is named PCS-CP01, Process Control System`

- **provenance_hash** `98ef121b1460fb68db8fe854cafe136ef74aae72a41f161015427570e657cfea` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 34 · `refers_to` · RW-0005 p.49

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-8ddb76ea31248021`:

  > CompactLogix (5380 series).

- **destino** `system_component` `cmp-d7b4d5336092b2a2` = **CompactLogix**

- **ancla de provenance del destino:** `CompactLogix (5380 series).`

- **provenance_hash** `a2c25d145432df816c00585a3797b74c9207787debb234d2af74829dd112f562` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 35 · `refers_to` · RW-0005 p.49

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-faa012ff31ef920f`:

  > The Rockwell Automation FactoryTalk Linx Enterprise software is an OPC server and provides the

- **destino** `system_component` `cmp-5e261c0b14cea343` = **FactoryTalk Linx**

- **ancla de provenance del destino:** `FactoryTalk Linx Enterprise 6.21.00 Server`

- **provenance_hash** `113f38c655eaad528a008d67e56ea8a2cf0ae1658fe7398d9cdf1e802f88c4a9` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 36 · `refers_to` · RW-0005 p.40

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-283c941be1cc0205`:

  > Before you can add users and user groups to the accounts list in the FactoryTalk View SE Runtime

- **destino** `system_component` `cmp-bede758f7194a8bc` = **FactoryTalk View SE**

- **ancla de provenance del destino:** `The delivered system has the Rockwell Software FactoryTalk View SE software loaded onto it, which`

- **provenance_hash** `0d268ad3aaafe4b87bff2366bc2f22ff123c06eb7d78d6002502097424341120` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 37 · `refers_to` · RW-0005 p.49

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-6b764277d8713282`:

  > platform is Allen-Bradley CompactLogix with 1769 Remote I/O.

- **destino** `system_component` `cmp-d7b4d5336092b2a2` = **CompactLogix**

- **ancla de provenance del destino:** `CompactLogix (5380 series).`

- **provenance_hash** `a2c25d145432df816c00585a3797b74c9207787debb234d2af74829dd112f562` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 38 · `refers_to` · RW-0014 p.5

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-7398082f60d752fb`:

  > is handled in the PLC and not in the FactoryTalk Alarm and Events

- **destino** `system_component` `cmp-28db170d5a86219e` = **FactoryTalk**

- **ancla de provenance del destino:** `is handled in the PLC and not in the FactoryTalk Alarm and Events`

- **provenance_hash** `2b7f21e6a9a6142acae152f03fa5d3b21f609333b3059e79bd5cda80de16b59d` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 39 · `refers_to` · RW-0005 p.40

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-3d9f2e80ca8140a7`:

  > The Windows-linked All Users group is automatically added to the FactoryTalk Runtime Security

- **destino** `system_component` `cmp-abbe8a20dd017f4c` = **FactoryTalk**

- **ancla de provenance del destino:** `FactoryTalk Linx Enterprise 6.21.00 Server`

- **provenance_hash** `113f38c655eaad528a008d67e56ea8a2cf0ae1658fe7398d9cdf1e802f88c4a9` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 40 · `refers_to` · RW-0005 p.40

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-660c37ee08693714`:

  > FactoryTalk View SE uses a

- **destino** `system_component` `cmp-bede758f7194a8bc` = **FactoryTalk View SE**

- **ancla de provenance del destino:** `The delivered system has the Rockwell Software FactoryTalk View SE software loaded onto it, which`

- **provenance_hash** `0d268ad3aaafe4b87bff2366bc2f22ff123c06eb7d78d6002502097424341120` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 41 · `refers_to` · RW-0014 p.4

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-5912f207afad4c27`:

  > PCS – Process Control System (This project’s panel is named PCS-CP01, Process Control System

- **destino** `system_component` `cmp-46697d1bb453b5b5` = **PCS-CP01**

- **ancla de provenance del destino:** `PCS – Process Control System (This project’s panel is named PCS-CP01, Process Control System`

- **provenance_hash** `98ef121b1460fb68db8fe854cafe136ef74aae72a41f161015427570e657cfea` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 42 · `refers_to` · RW-0005 p.40

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-e0774e5d64c9685e`:

  > Administrator  Ability to change input values via simulation feature A, B, C, D, E

- **destino** `actor` `act-bc6a65907ef2903f` = **Administrator**

- **ancla de provenance del destino:** `Administrator and Maintenance login security levels.`

- **provenance_hash** `036322553783cf6a8b22caba88dea1605c429c8ab768c08aba4f2e8f375c0790` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 43 · `refers_to` · RW-0005 p.54

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-9f60bff6222a21cc`:

  > OEM vendor on-skid control system platform is Allen-Bradley CompactLogix (5380 series).-F16.00, 49

- **destino** `system_component` `cmp-d7b4d5336092b2a2` = **CompactLogix**

- **ancla de provenance del destino:** `CompactLogix (5380 series).`

- **provenance_hash** `a2c25d145432df816c00585a3797b74c9207787debb234d2af74829dd112f562` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 44 · `refers_to` · RW-0005 p.9

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-a5e08d738996fe76`:

  > FactoryTalk Activation Manager 4.05.01 Server

- **destino** `system_component` `cmp-abbe8a20dd017f4c` = **FactoryTalk**

- **ancla de provenance del destino:** `FactoryTalk Linx Enterprise 6.21.00 Server`

- **provenance_hash** `113f38c655eaad528a008d67e56ea8a2cf0ae1658fe7398d9cdf1e802f88c4a9` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 45 · `refers_to` · RW-0005 p.49

- **SAME_RELATION_AS_PREVIOUS** = YES   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-3918902aecb5bc12`:

  > FactoryTalk View SE system and the PLCs (PCS-CP01 and the other vendor systems).

- **destino** `system_component` `cmp-bede758f7194a8bc` = **FactoryTalk View SE**

- **ancla de provenance del destino:** `The delivered system has the Rockwell Software FactoryTalk View SE software loaded onto it, which`

- **provenance_hash** `0d268ad3aaafe4b87bff2366bc2f22ff123c06eb7d78d6002502097424341120` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 46 · `refers_to` · RW-0005 p.13

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-b6d7eb711c053a7f`:

  > application revision is populated into a tag in the PCS-CP01 PLC.

- **destino** `system_component` `cmp-228329ce2f500a19` = **PCS-CP01**

- **ancla de provenance del destino:** `PLC Interfaces (PCS-CP01 and other Vendor Systems) .....................................`

- **provenance_hash** `4b01e10bb51e7dda41e85bef86618085eba1f03a782bf3d1d63ac21c84255c4d` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 47 · `refers_to` · RW-0005 p.45

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-0530d41a2b17a50a`:

  > This FactoryTalk Historian SE is capable of logging data at different rates based on its configuration.

- **destino** `system_component` `cmp-3e541a27d4244457` = **FactoryTalk Historian**

- **ancla de provenance del destino:** `FactoryTalk Historian DataLink Excel Reporting`

- **provenance_hash** `583f544a6fcb2f38f93552457fa42dff594060a3a0644f3520d53355dd06c28e` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 48 · `refers_to` · RW-0012 p.5

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-cfd59d42c840f121`:

  > Wash_Ster_Comms_OK DI PCS-CP01 successfully communicating

- **destino** `system_component` `cmp-da216cca36b0d404` = **PCS-CP01**

- **ancla de provenance del destino:** `PCS – Process Control System (This project’s panel is named PCS-CP01, Process Control System`

- **provenance_hash** `98ef121b1460fb68db8fe854cafe136ef74aae72a41f161015427570e657cfea` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 49 · `refers_to` · RW-0005 p.13

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-9d2c55f4ce60d3ce`:

  > The Rockwell Software FactoryTalk View SE platform provides the ability to archive continuous

- **destino** `system_component` `cmp-bede758f7194a8bc` = **FactoryTalk View SE**

- **ancla de provenance del destino:** `The delivered system has the Rockwell Software FactoryTalk View SE software loaded onto it, which`

- **provenance_hash** `0d268ad3aaafe4b87bff2366bc2f22ff123c06eb7d78d6002502097424341120` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 50 · `refers_to` · RW-0005 p.13

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-90b19e0022efa847`:

  > revision shall be accessible via a main menu selection to users with Administrator or

- **destino** `actor` `act-bc6a65907ef2903f` = **Administrator**

- **ancla de provenance del destino:** `Administrator and Maintenance login security levels.`

- **provenance_hash** `036322553783cf6a8b22caba88dea1605c429c8ab768c08aba4f2e8f375c0790` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 51 · `refers_to` · RW-0005 p.13

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-ec29f43d640fa70f`:

  > Alarm List MCCPDC PCS-CP01 Alarms Hard Soft IO Listing

- **destino** `system_component` `cmp-228329ce2f500a19` = **PCS-CP01**

- **ancla de provenance del destino:** `PLC Interfaces (PCS-CP01 and other Vendor Systems) .....................................`

- **provenance_hash** `4b01e10bb51e7dda41e85bef86618085eba1f03a782bf3d1d63ac21c84255c4d` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 52 · `refers_to` · RW-0005 p.45

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-06dce53dda055401`:

  > This FactoryTalk Historian SE license permits up to 250 points to be logged based on a configurable

- **destino** `system_component` `cmp-3e541a27d4244457` = **FactoryTalk Historian**

- **ancla de provenance del destino:** `FactoryTalk Historian DataLink Excel Reporting`

- **provenance_hash** `583f544a6fcb2f38f93552457fa42dff594060a3a0644f3520d53355dd06c28e` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 53 · `refers_to` · RW-0011 p.4

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-30879ffdc43d5406`:

  > in the FactoryTalk Historian Site Edition (SE) software product.

- **destino** `system_component` `cmp-be0595e17992c873` = **FactoryTalk Historian**

- **ancla de provenance del destino:** `in the FactoryTalk Historian Site Edition (SE) software product.`

- **provenance_hash** `233dcd3ed90cec275cf352676bae2f7c8e4ff4c55afe12a4df30314f788c5e07` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 54 · `refers_to` · RW-0005 p.49

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-faa012ff31ef920f`:

  > The Rockwell Automation FactoryTalk Linx Enterprise software is an OPC server and provides the

- **destino** `system_component` `cmp-37363e0842740a23` = **OPC server**

- **ancla de provenance del destino:** `OPC server for Rockwell Controllers provides the means to read/write values from/to the controller.`

- **provenance_hash** `0828ac6bbc37fc8a079a8a67c1023c77004455880ea4254c25fad1525a50f337` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 55 · `refers_to` · RW-0005 p.13

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-94ab79f06ffd636a`:

  > The FactoryTalk View SE HMI satisfies the requirements for a method to display the values

- **destino** `system_component` `cmp-bede758f7194a8bc` = **FactoryTalk View SE**

- **ancla de provenance del destino:** `The delivered system has the Rockwell Software FactoryTalk View SE software loaded onto it, which`

- **provenance_hash** `0d268ad3aaafe4b87bff2366bc2f22ff123c06eb7d78d6002502097424341120` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 56 · `refers_to` · RW-0005 p.51

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-ebbd774b916fef1c`:

  > The FactoryTalk View SE HMI server and other software is running on the VersaVirtual™

- **destino** `system_component` `cmp-bede758f7194a8bc` = **FactoryTalk View SE**

- **ancla de provenance del destino:** `The delivered system has the Rockwell Software FactoryTalk View SE software loaded onto it, which`

- **provenance_hash** `0d268ad3aaafe4b87bff2366bc2f22ff123c06eb7d78d6002502097424341120` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 57 · `refers_to` · RW-0011 p.4

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-471a539ce64bf8cb`:

  > detailed in the MCCPDC PCS-CP01 Alarms Hard Soft IO Listing.xlsx document.

- **destino** `system_component` `cmp-36baf682d2d15e14` = **PCS-CP01**

- **ancla de provenance del destino:** `PCS – Process Control System (This project’s panel is named PCS-CP01, Process Control System`

- **provenance_hash** `98ef121b1460fb68db8fe854cafe136ef74aae72a41f161015427570e657cfea` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 58 · `refers_to` · RW-0005 p.40

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-b35a6c825e9428ae`:

  > combination of Microsoft Windows domain security and FactoryTalk View SE security.

- **destino** `system_component` `cmp-bede758f7194a8bc` = **FactoryTalk View SE**

- **ancla de provenance del destino:** `The delivered system has the Rockwell Software FactoryTalk View SE software loaded onto it, which`

- **provenance_hash** `0d268ad3aaafe4b87bff2366bc2f22ff123c06eb7d78d6002502097424341120` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 59 · `refers_to` · RW-0005 p.45

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-58109fb8353c52ee`:

  > FactoryTalk View SE system.

- **destino** `system_component` `cmp-bede758f7194a8bc` = **FactoryTalk View SE**

- **ancla de provenance del destino:** `The delivered system has the Rockwell Software FactoryTalk View SE software loaded onto it, which`

- **provenance_hash** `0d268ad3aaafe4b87bff2366bc2f22ff123c06eb7d78d6002502097424341120` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 60 · `refers_to` · RW-0012 p.5

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-6dba79005d84f66d`:

  > Since an Administrator or Maintenance person may put any input point in SIMULATE and change its

- **destino** `actor` `act-e2522a5ba572cd46` = **Administrator**

- **ancla de provenance del destino:** `Since an Administrator or Maintenance person may put any input point in SIMULATE and change its`

- **provenance_hash** `dcee8569866ddadf69078a0fa8e0548996bd483e07a17209369daacffbb6ba48` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 61 · `refers_to` · RW-0005 p.45

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-98c40a5fd232b86e`:

  > With the FactoryTalk View SE electronic signature feature, each entry into the FactoryTalk View

- **destino** `system_component` `cmp-bede758f7194a8bc` = **FactoryTalk View SE**

- **ancla de provenance del destino:** `The delivered system has the Rockwell Software FactoryTalk View SE software loaded onto it, which`

- **provenance_hash** `0d268ad3aaafe4b87bff2366bc2f22ff123c06eb7d78d6002502097424341120` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 62 · `refers_to` · RW-0005 p.40

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-82095eb77ed125ac`:

  > of the Microsoft Windows users to FactoryTalk View SE, as needed.

- **destino** `system_component` `cmp-bede758f7194a8bc` = **FactoryTalk View SE**

- **ancla de provenance del destino:** `The delivered system has the Rockwell Software FactoryTalk View SE software loaded onto it, which`

- **provenance_hash** `0d268ad3aaafe4b87bff2366bc2f22ff123c06eb7d78d6002502097424341120` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 63 · `refers_to` · RW-0005 p.13

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-d1f727833fc32276`:

  >  Alarm limit values can be changed via OIT by Administrator security

- **destino** `actor` `act-bc6a65907ef2903f` = **Administrator**

- **ancla de provenance del destino:** `Administrator and Maintenance login security levels.`

- **provenance_hash** `036322553783cf6a8b22caba88dea1605c429c8ab768c08aba4f2e8f375c0790` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 64 · `refers_to` · RW-0005 p.13

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-2af6124440ae76e4`:

  > control panel, an access layer Stratix Ethernet switch provides connectivity for the

- **destino** `system_component` `cmp-3ca114db69d568cf` = **Stratix**

- **ancla de provenance del destino:** `control panel, an access layer Stratix Ethernet switch provides connectivity for the`

- **provenance_hash** `1ca6da5207cc0c71bb260d958d66f84753fa0f3406fb5fa0a163a29a77729f96` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 65 · `refers_to` · RW-0014 p.5

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-a073b8fd2910fb97`:

  > logic is implemented to ensure that the communications links between the PCS-CP01 controller

- **destino** `system_component` `cmp-46697d1bb453b5b5` = **PCS-CP01**

- **ancla de provenance del destino:** `PCS – Process Control System (This project’s panel is named PCS-CP01, Process Control System`

- **provenance_hash** `98ef121b1460fb68db8fe854cafe136ef74aae72a41f161015427570e657cfea` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 66 · `refers_to` · RW-0005 p.51

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-b563e3028f543d8a`:

  > Engineering Workstation via the ThinManager® technology.

- **destino** `system_component` `cmp-abb9c1125e4888ab` = **engineering workstation**

- **ancla de provenance del destino:** `Engineering Workstation PC located in Room 054 Grid:`

- **provenance_hash** `2162cdf9b715c33fe9ad134d6ba7bba11dd554d2d330d30d40ed87cdcd0cbb66` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 67 · `refers_to` · RW-0006 p.11

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-157ea08288b3d62b`:

  > virtual active directory, network time

- **destino** `system_component` `cmp-e81c7b18207925b4` = **Active Directory**

- **ancla de provenance del destino:** `vendor systems and other IT Systems, such as Windows Active Directory, NTP`

- **provenance_hash** `192c5f73aee5927a72fae291371c2d9dec8ac49a0cac380e679b798d0ed6226d` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 68 · `refers_to` · RW-0005 p.40

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-b76dc5b9747eb0b6`:

  > The FactoryTalk View SE electronic signature feature can be

- **destino** `system_component` `cmp-bede758f7194a8bc` = **FactoryTalk View SE**

- **ancla de provenance del destino:** `The delivered system has the Rockwell Software FactoryTalk View SE software loaded onto it, which`

- **provenance_hash** `0d268ad3aaafe4b87bff2366bc2f22ff123c06eb7d78d6002502097424341120` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 69 · `refers_to` · RW-0006 p.6

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-278ac117634c6d32`:

  > control system platform is Allen-Bradley GuardLogix (1756-L72S).

- **destino** `system_component` `cmp-9117869b7c8bd88c` = **GuardLogix**

- **ancla de provenance del destino:** `control system platform is Allen-Bradley GuardLogix (1756-L72S).`

- **provenance_hash** `e7d592ccf34914ff8e74b09870ccc0c716cb5290759cabb5271f5c1aec0abf9d` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 70 · `refers_to` · RW-0005 p.9

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-63c3ff62e2724c6c`:

  > FactoryTalk Historian Site Edition – 250 points 7.01 Server

- **destino** `system_component` `cmp-3e541a27d4244457` = **FactoryTalk Historian**

- **ancla de provenance del destino:** `FactoryTalk Historian DataLink Excel Reporting`

- **provenance_hash** `583f544a6fcb2f38f93552457fa42dff594060a3a0644f3520d53355dd06c28e` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 71 · `refers_to` · RW-0011 p.4

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-ff39d638f54d7d2f`:

  > is handled in the PLC and not in the FactoryTalk Alarm and Events

- **destino** `system_component` `cmp-12d7e381df0cd835` = **FactoryTalk**

- **ancla de provenance del destino:** `in the FactoryTalk Historian Site Edition (SE) software product.`

- **provenance_hash** `233dcd3ed90cec275cf352676bae2f7c8e4ff4c55afe12a4df30314f788c5e07` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 72 · `refers_to` · RW-0005 p.49

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-ea7fe0aca07b2ff4`:

  > OPC server for Rockwell Controllers provides the means to read/write values from/to the controller.

- **destino** `system_component` `cmp-37363e0842740a23` = **OPC server**

- **ancla de provenance del destino:** `OPC server for Rockwell Controllers provides the means to read/write values from/to the controller.`

- **provenance_hash** `0828ac6bbc37fc8a079a8a67c1023c77004455880ea4254c25fad1525a50f337` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 73 · `refers_to` · RW-0005 p.40

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-df096ff0a5c82949`:

  > P), and all FactoryTalk Security actions.

- **destino** `system_component` `cmp-abbe8a20dd017f4c` = **FactoryTalk**

- **ancla de provenance del destino:** `FactoryTalk Linx Enterprise 6.21.00 Server`

- **provenance_hash** `113f38c655eaad528a008d67e56ea8a2cf0ae1658fe7398d9cdf1e802f88c4a9` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 74 · `refers_to` · RW-0012 p.14

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-f49dbaac39795c7b`:

  > MCCPDC PCS-CP01 Alarms Hard Soft IO Listing.xlsx

- **destino** `system_component` `cmp-da216cca36b0d404` = **PCS-CP01**

- **ancla de provenance del destino:** `PCS – Process Control System (This project’s panel is named PCS-CP01, Process Control System`

- **provenance_hash** `98ef121b1460fb68db8fe854cafe136ef74aae72a41f161015427570e657cfea` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 75 · `refers_to` · RW-0005 p.49

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-70359963bfa6e9b1`:

  > The Rockwell Automation FactoryTalk Linx Enterprise software provides the connection between the

- **destino** `system_component` `cmp-5e261c0b14cea343` = **FactoryTalk Linx**

- **ancla de provenance del destino:** `FactoryTalk Linx Enterprise 6.21.00 Server`

- **provenance_hash** `113f38c655eaad528a008d67e56ea8a2cf0ae1658fe7398d9cdf1e802f88c4a9` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 76 · `refers_to` · RW-0005 p.51

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-795b923879298e87`:

  > failure to occur and not interrupt the functions of the system (FactoryTalk View SE, Historian,

- **destino** `system_component` `cmp-bede758f7194a8bc` = **FactoryTalk View SE**

- **ancla de provenance del destino:** `The delivered system has the Rockwell Software FactoryTalk View SE software loaded onto it, which`

- **provenance_hash** `0d268ad3aaafe4b87bff2366bc2f22ff123c06eb7d78d6002502097424341120` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`


## Fila 77 · `refers_to` · RW-0005 p.40

- **SAME_RELATION_AS_PREVIOUS** = NO   ·   **PREVIOUS_VERDICT** = NOT_AVAILABLE_PER_ROW

- **claim (origen)** `clm-5833a893ed98d1c0`:

  > FactoryTalk View SE security is based on a system of letter codes (A-P) which are assigned to the

- **destino** `system_component` `cmp-bede758f7194a8bc` = **FactoryTalk View SE**

- **ancla de provenance del destino:** `The delivered system has the Rockwell Software FactoryTalk View SE software loaded onto it, which`

- **provenance_hash** `0d268ad3aaafe4b87bff2366bc2f22ff123c06eb7d78d6002502097424341120` · **ref** `literal_name`

- **NEW_HUMAN_VERDICT** = `________`

