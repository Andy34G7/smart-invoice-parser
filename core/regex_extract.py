import re
from typing import Dict, Any, List, Optional
from .utils import clean_amount, parse_date_str, is_company_like_line, normalize_invoice_number
from .gstin import extract_gstin_roles_and_vendor

def find_first_match(text, patterns):
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1).strip()
    return None

def get_invoice_sections(text):
    sections = {"header": text, "summary": text}
    summary_match = re.search(r'(?i)^\s*(?:total|subtotal|amount chargeable|balance due)', text, re.MULTILINE)
    if summary_match:
        sections["header"] = text[:summary_match.start()]
        sections["summary"] = text[summary_match.start():]
    return sections

def process_invoice_regex(text):
    invoice_number_patterns = [
        r'Invoice\s*No\.?\s*[:#-]?\s*([A-Z0-9/-]{3,})',
        r'Invoice\s*#\s*([A-Z0-9/-]{3,})',
        r'Invoice\s*Number\s*[:#-]?\s*([A-Z0-9/-]{3,})',
        r'Invoice Code\s*[:#-]?\s*([A-Z0-9/-]{3,})',
        r'Tax Invoice#\s*([A-Z0-9/-]{3,})'
    ]
    date_patterns = [
        r'Dated\s*[:\s]*(\d{1,2}[-/][A-Za-z]{3,}[-/]\d{2,4})',
        r'Invoice Date\s*[:\s]*(\d{1,2}[-/][A-Za-z]{3,}[-/]\d{2,4})',
        r'Dt[:\s]*(\d{2}/\d{2}/\d{4})',
        r'(\d{1,2}[-/][A-Za-z]{3,}[-/]\d{2,4})'
    ]
    total_amount_patterns = [
        r'BALANCE DUE\s*₹?\s*([0-9,]+(?:\.\d{2})?)',
        r'Total Amount after Tax\s*₹?\s*([0-9,]+(?:\.\d{2})?)',
        r'Total\s*₹?\s*([0-9,]+(?:\.\d{2})?)'
    ]
    sections = get_invoice_sections(text)
    gstin_roles = extract_gstin_roles_and_vendor(text, sections['header'])
    header_lines = [ln.strip() for ln in sections["header"].splitlines() if ln.strip()]
    vendor_candidates = []
    for ln in header_lines:
        low = ln.lower()
        if 'invoice' in low or 'gstin' in low or low.startswith('dated'):
            break
        if re.match(r'^\d+\)?$', ln):
            continue
        if len(ln) < 3:
            continue
        if is_company_like_line(ln):
            vendor_candidates.append(ln)
    vendor_name = None
    if vendor_candidates:
        vendor_candidates = [c for c in vendor_candidates if not re.fullmatch(r'[\d/.-]+', c)] or vendor_candidates
        vendor_name = max(vendor_candidates, key=len)[:120]
    if not vendor_name:
        vendor_name = header_lines[0].strip()[:120] if header_lines else None
    vn_hint = gstin_roles.get('vendor_name_hint')
    if vn_hint and is_company_like_line(vn_hint):
        if not vendor_name or (len(vn_hint) > len(vendor_name) and vn_hint.lower() not in vendor_name.lower()):
            vendor_name = vn_hint
    def is_company_like(s: str) -> bool:
        return is_company_like_line(s)
    if not vendor_name or ('invoice' in (vendor_name or '').lower()):
        m_prep = re.search(r'(?mi)^\s*Prepared\s*By\s*[:\-]\s*(.+)$', text)
        if m_prep:
            candidate = m_prep.group(1).strip()
            if is_company_like(candidate):
                vendor_name = candidate[:120]
        if not vendor_name:
            m_for = re.search(r'(?mi)^\s*For\s+(.+?)\s*$', text)
            if m_for:
                cand = m_for.group(1).strip()
                if is_company_like(cand):
                    vendor_name = cand[:120]
        if not vendor_name:
            store_pat = re.compile(r'(?mi)^.*\b(store\s*(?:contact|manager))\b.*$')
            lines = [ln for ln in text.splitlines()]
            for i, ln in enumerate(lines):
                if store_pat.search(ln):
                    for j in range(max(0, i-6), i):
                        cand = lines[j].strip()
                        if is_company_like(cand):
                            vendor_name = cand[:120]
                            break
                if vendor_name:
                    break
        if not vendor_name or ('invoice' in vendor_name.lower()):
            header_lines_scan = [ln.strip() for ln in sections['header'].splitlines()[:30] if ln.strip()]
            company_lines = [ln for ln in header_lines_scan if is_company_like(ln)]
            if company_lines:
                vendor_name = max(company_lines, key=len)[:120]
    if vendor_name and not is_company_like_line(vendor_name):
        vn_hint = gstin_roles.get('vendor_name_hint')
        if vn_hint and is_company_like_line(vn_hint):
            vendor_name = vn_hint
    raw_date = find_first_match(text, date_patterns)
    if not raw_date:
        token_match = re.search(r'\b\d{1,2}-[A-Za-z]{3}-\d{2,4}\b', sections["header"]) or re.search(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b', sections["header"]) 
        raw_date = token_match.group(0) if token_match else None
    def extract_grand_total(full_text: str) -> Optional[float]:
        candidates: List[float] = []
        lines = [ln.strip() for ln in full_text.splitlines() if ln.strip()]
        amount_re = re.compile(r'₹?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)')
        for ln in lines:
            low = ln.lower()
            if not any(t in low for t in ['total', 'amount chargeable', 'grand total', 'amount (inr)']):
                continue
            for m in re.finditer(r'₹?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)\s+total\b', low, flags=re.IGNORECASE):
                v = clean_amount(m.group(1))
                if v is not None:
                    candidates.append(v)
            m2 = re.search(r'(grand\s+total|total\s*amount|total|amount\s*\(inr\))[:\s]*₹?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)\s*$', low, flags=re.IGNORECASE)
            if m2:
                v = clean_amount(m2.group(2))
                if v is not None:
                    candidates.append(v)
            if 'total' in low:
                for m in amount_re.finditer(ln):
                    v = clean_amount(m.group(1))
                    if v is not None:
                        candidates.append(v)
        if not candidates:
            return None
        gt = max(candidates)
        if gt < 10 and len(candidates) > 1:
            gt = max((c for c in candidates if c >= 10), default=gt)
        return gt
    advanced_total = extract_grand_total(text)
    basic_total = clean_amount(find_first_match(sections["summary"], total_amount_patterns))
    total_amount = advanced_total if advanced_total is not None else basic_total
    if total_amount is None:
        all_tokens = re.findall(r'\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?', text)
        vals = []
        for tok in all_tokens:
            try:
                vals.append(float(tok.replace(',', '')))
            except Exception:
                pass
        if vals:
            guess = max(vals)
            if guess >= 100:
                total_amount = guess
    inv_raw = find_first_match(text, invoice_number_patterns)
    inv_norm = normalize_invoice_number(inv_raw)
    data = {
        "vendor_name": vendor_name if is_company_like_line(vendor_name or '') else None,
        "invoice_number": inv_norm,
        "invoice_date": parse_date_str(raw_date),
        "total_amount": total_amount,
        "processing_tier": "Regex",
        "vendor_gstin": gstin_roles.get('vendor_gstin'),
        "customer_gstin": gstin_roles.get('customer_gstin')
    }
    return data
