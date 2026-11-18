from __future__ import annotations
import json
from pathlib import Path
from circularity.integration import build_evidence_adapter, adapter_summary
from circularity.scoring import evaluate_snapshot, CATEGORIES, CONFIG

ROOT=Path(__file__).resolve().parent
AUDIT=ROOT/'test_data'/'ev_motor_disassembly_audit (1).json'
audit=json.loads(AUDIT.read_text(encoding='utf-8'))
adapter=build_evidence_adapter(
    audit['components'],audit['component_features'],audit['relationships'],
    audit['disassembly_sequence'],audit['robotic_assessment']
)
summary=adapter_summary(adapter)
assert len(CATEGORIES)==11
assert sum(len(c['qs']) for c in CATEGORIES)==80
assert sum(len(v) for v in CONFIG['critical'].values())==111
assert summary['classes']=={'C':43,'B':24,'A':13}
assert adapter.loc[adapter.input_key=='rotor_access','suggested_value'].iloc[0]=='>5'

# Evidence/content preservation checks extracted from the protected HTML evaluator.
SUPPORT=json.loads((ROOT/'circularity'/'data'/'support_data.json').read_text(encoding='utf-8'))
FIGURES=json.loads((ROOT/'circularity'/'data'/'figure_catalog.json').read_text(encoding='utf-8'))
assert len(SUPPORT['evGuidelines'])==69
assert len(SUPPORT['disassemblyGuidelines'])==29
assert len(SUPPORT['circularityGuidelines'])==59
assert len(SUPPORT['evidenceRegister'])==101
assert len(SUPPORT['crosswalk'])==40
assert len(SUPPORT['references'])==41
assert len(SUPPORT['assessmentCriteria'])==19
assert len(SUPPORT['criticalRules'])==115
assert len(FIGURES)==35
assert all((ROOT/'circularity'/'assets'/'figures'/f['file']).exists() for f in FIGURES)

result=evaluate_snapshot(audit['circularity_evaluation'])
assert abs(result['overall']-71.121)<1e-9
print('PASS')
print('11 categories, 80 inputs, 111 critical conditions')
print('A/B/C:',summary['classes'])
for k in ['req_ops','rob_tot','grasp_tot','sequence','cool_inspect']:
    row=adapter.loc[adapter.input_key==k].iloc[0]
    print(k, '=>', row.suggested_value, '|', row.status)
print('ELLI rotor_access suggestion:',adapter.loc[adapter.input_key=='rotor_access','suggested_value'].iloc[0])
print('Approved corrected demonstration score:',result['overall'])
print('Evidence preserved: 101 register, 40 crosswalk, 41 references, 115 critical-rule rows, 35 figures')
print('Guidelines preserved: 69 EV, 29 general DfD, 59 circularity')
