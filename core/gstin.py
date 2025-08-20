import re
from typing import Dict, Any, List
from .config import GSTIN_REGEX
from .utils import is_company_like_line

def _linewise(text: str):
    lines = text.splitlines()
    return list(enumerate(lines))

def _has_any(s: str, keywords: List[str]) -> bool:
    low = s.lower()
    return any(k in low for k in keywords)

def extract_gstin_roles_and_vendor(text: str, header_text: str) -> Dict[str, Any]:
    lines = _linewise(text)
    header_lines = set(i for i, _ in _linewise(header_text))
    results = []
    pat = re.compile(r'\b(\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9])\b', re.IGNORECASE)
    for idx, line in lines:
        for m in pat.finditer(line):
            val = m.group(1).strip().upper()
            role = None
            neighborhood = ' '.join([lines[i][1] for i in range(max(0, idx-2), min(len(lines), idx+3))])
            if _has_any(neighborhood, ['customer', 'buyer', 'bill to', 'billed to', 'consignee', 'ship to']):
                role = 'customer'
            if _has_any(neighborhood, ['supplier', 'vendor', 'seller', 'from']):
                role = 'vendor'
            results.append({'value': val, 'line_idx': idx, 'role_hint': role, 'in_header': idx in header_lines})
    seen = set()
    dedup = []
    for r in results:
        if r['value'] in seen:
            continue
        seen.add(r['value'])
        dedup.append(r)
    results = dedup
    vendor_gstin = None
    customer_gstin = None
    if not results:
        return {'vendor_gstin': None, 'customer_gstin': None, 'vendor_name_hint': None}
    for r in results:
        if r['role_hint'] == 'vendor' and GSTIN_REGEX.match(r['value']):
            vendor_gstin = r
            break
    for r in results:
        if r['role_hint'] == 'customer' and GSTIN_REGEX.match(r['value']):
            customer_gstin = r
            break
    if vendor_gstin is None and results:
        header_candidates = [r for r in results if r['in_header']]
        vendor_gstin = (header_candidates[0] if header_candidates else results[0])
    if customer_gstin is None and results:
        for r in results:
            if vendor_gstin and r['value'] != vendor_gstin['value']:
                customer_gstin = r
                break
    vendor_name_hint = None
    def good_vendor_line(s: str) -> bool:
        s = s.strip()
        if not s or len(s) < 3:
            return False
        low = s.lower()
        if _has_any(low, ['invoice', 'gstin', 'date', 'tax invoice', 'bill to', 'buyer', 'consignee', 'ship to', 'address', 'store']):
            return False
        if re.fullmatch(r'[\d/ .-]+', s):
            return False
        if sum(c.isalpha() for c in s) < 3:
            return False
        return is_company_like_line(s)
    if vendor_gstin is not None:
        vi = vendor_gstin['line_idx']
        window_up = range(max(0, vi-10), vi)
        window_down = range(vi+1, min(len(lines), vi+4))
        suffixes = ['private limited','pvt ltd','pvt. ltd.','ltd','llp','inc','company','limited']
        best = None
        for j in reversed(list(window_up)):
            candidate = lines[j][1].strip()
            if good_vendor_line(candidate) and any(sf in candidate.lower() for sf in suffixes):
                best = candidate
                break
        if not best:
            for j in window_down:
                candidate = lines[j][1].strip()
                if good_vendor_line(candidate) and any(sf in candidate.lower() for sf in suffixes):
                    best = candidate
                    break
        if not best:
            for j in reversed(list(window_up)):
                candidate = lines[j][1].strip()
                if good_vendor_line(candidate):
                    best = candidate
                    break
        if not best:
            for j in window_down:
                candidate = lines[j][1].strip()
                if good_vendor_line(candidate):
                    best = candidate
                    break
        if best:
            vendor_name_hint = best[:120]
    return {
        'vendor_gstin': vendor_gstin['value'] if vendor_gstin else None,
        'customer_gstin': customer_gstin['value'] if customer_gstin else None,
        'vendor_name_hint': vendor_name_hint
    }
