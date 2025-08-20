import re
from typing import Optional, List
from dateutil.parser import parse

def clean_amount(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        try:
            return float(s)
        except Exception:
            return None
    tokens = re.findall(r'\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?', str(s))
    if not tokens:
        return None
    vals = []
    for t in tokens:
        try:
            vals.append(float(t.replace(',', '')))
        except Exception:
            pass
    return max(vals) if vals else None

def parse_date_str(s):
    if not s:
        return None
    s = str(s).strip()
    if re.fullmatch(r'20\d{2}-\d{2}', s):
        return None
    try:
        return parse(s, fuzzy=True).date().isoformat()
    except Exception:
        return None

def alnum_mix(s: Optional[str]) -> bool:
    if not isinstance(s, str):
        return False
    return bool(re.search(r'[A-Za-z]', s) and re.search(r'\d', s))

def is_company_like_line(s: str) -> bool:
    s = (s or '').strip()
    if not s or len(s) < 3:
        return False
    low = s.lower()
    bad = ['invoice', 'gstin', 'bill to', 'ship to', 'address', 'tax invoice', 'order no', 'invoice code', 'ref.', 'ref ', 'ref:',
           'contact', 'phone', 'mobile', 'email', 'www', 'website', 'store', 'helpline', 'care', 'customer',
           'road', 'rd', 'street', 'st ', 'st.', 'lane', 'ln', 'complex', 'tower', 'floor', 'opp', 'near', 'shop', 'block',
           'sector', 'phase', 'plot', 'no.', 'no ', 'colony', 'market', 'apartment', 'residency', 'residence', 'society',
           'village', 'taluka', 'tehsil', 'district', 'dist', 'po ', 'ps ', 'pin', 'pincode', 'zip', 'city', 'state']
    if any(b in low for b in bad):
        return False
    letters = sum(c.isalpha() for c in s)
    if letters < 3:
        return False
    suffixes = ['private limited', 'pvt', 'pvt.', 'pvt ltd', 'ltd', 'llp', 'inc', 'co', 'company', 'limited']
    if any(sf in low for sf in suffixes):
        return True
    compact = re.sub(r'\s+', '', s)
    upper_ratio = sum(1 for c in compact if c.isupper()) / max(1, len(compact))
    digit_ratio = sum(1 for c in s if c.isdigit()) / max(1, len(s))
    return upper_ratio > 0.4 and digit_ratio < 0.25

def normalize_invoice_number(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = str(s).strip()
    candidates = re.findall(r'[A-Za-z0-9][A-Za-z0-9_\-/]{2,24}', s)
    if not candidates:
        return None
    candidates = [c for c in candidates if re.search(r'\d', c)]
    if not candidates:
        return None
    candidates.sort(key=lambda x: (not alnum_mix(x), -len(x)))
    best = candidates[0].upper()
    if len(best) < 3 or len(best) > 24:
        return None
    return best

def has_any_field(d: dict) -> bool:
    if not isinstance(d, dict):
        return False
    keys = ["vendor_name", "total_amount", "invoice_number", "invoice_date"]
    return any(d.get(k) not in (None, "") for k in keys)
