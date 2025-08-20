import re
from typing import Dict, Any, Optional
from .utils import is_company_like_line

def merge_tier1_tier2(t1: Dict[str, Any], t2: Dict[str, Any]) -> Dict[str, Any]:
    if not t1:
        return {**t2}
    if not t2:
        return {**t1}
    merged: Dict[str, Any] = {}
    def alnum_mix(s: Optional[str]):
        if not isinstance(s, str):
            return False
        return bool(re.search(r'[A-Za-z]', s) and re.search(r'\d', s))
    v1, v2 = t1.get('vendor_name'), t2.get('vendor_name')
    if v1 and v2:
        c1 = is_company_like_line(v1)
        c2 = is_company_like_line(v2)
        if c1 and not c2:
            merged['vendor_name'] = v1
        elif c2 and not c1:
            merged['vendor_name'] = v2
        else:
            merged['vendor_name'] = v2 if len(str(v2)) >= len(str(v1)) else v1
    else:
        merged['vendor_name'] = v1 or v2
    n1, n2 = t1.get('invoice_number'), t2.get('invoice_number')
    if n2 and not n1:
        merged['invoice_number'] = n2
    elif n1 and not n2:
        merged['invoice_number'] = n1
    elif n1 and n2:
        if alnum_mix(n2) and not alnum_mix(n1):
            merged['invoice_number'] = n2
        elif alnum_mix(n1) and not alnum_mix(n2):
            merged['invoice_number'] = n1
        else:
            merged['invoice_number'] = n2 if len(str(n2)) >= len(str(n1)) else n1
    else:
        merged['invoice_number'] = None
    d1, d2 = t1.get('invoice_date'), t2.get('invoice_date')
    merged['invoice_date'] = d2 or d1
    a1, a2 = t1.get('total_amount'), t2.get('total_amount')
    if a1 is None and a2 is not None:
        merged['total_amount'] = a2
    elif a2 is None and a1 is not None:
        merged['total_amount'] = a1
    elif a1 is not None and a2 is not None:
        try:
            diff = abs(a1 - a2)
            base = max(a1, a2, 1)
            if diff / base <= 0.01:
                merged['total_amount'] = a2
            else:
                raw1 = str(t1.get('raw_total_amount', a1))
                raw2 = str(t2.get('raw_total_amount', a2))
                score1 = len(re.findall(r'\d', raw1)) / max(len(raw1), 1)
                score2 = len(re.findall(r'\d', raw2)) / max(len(raw2), 1)
                merged['total_amount'] = a2 if score2 >= score1 else a1
        except Exception:
            merged['total_amount'] = a2
    else:
        merged['total_amount'] = None
    for key in ['vendor_gstin', 'customer_gstin']:
        v_1, v_2 = t1.get(key), t2.get(key)
        merged[key] = v_2 or v_1
    merged['processing_tier'] = 'Regex+DocTR'
    return merged
