from typing import Dict, Any, Optional
from .ocr import process_with_doctr
from .regex_extract import process_invoice_regex
from .qa import process_with_text_qa
from .llm import process_with_llm
from .utils import has_any_field, is_company_like_line
from database import save_to_db

def get_next_tier(current_tier: Optional[str]) -> Optional[str]:
    """Determine the next processing tier based on the current tier"""
    from .config import ENABLE_TEXT_QA
    
    if ENABLE_TEXT_QA:
        tier_hierarchy = {
            None: 'RegexOnly',
            'RegexOnly': 'Regex+DocTR', 
            'Regex': 'Regex+DocTR',
            'Regex+DocTR': 'Text_QA',
            'Text_QA': 'LLM',
            'LLM': None 
        }
    else:
        
        tier_hierarchy = {
            None: 'RegexOnly',
            'RegexOnly': 'Regex+DocTR', 
            'Regex': 'Regex+DocTR',
            'Regex+DocTR': 'LLM',  
            'LLM': None  
        }
    
    return tier_hierarchy.get(current_tier)

def get_alternative_tier(current_tier: Optional[str]) -> Optional[str]:
    """Get an alternative tier if the standard next tier fails"""
    if not current_tier:
        return None
    alternatives = {
        'Regex+DocTR': 'LLM',  
        'Text_QA': None  
    }
    return alternatives.get(current_tier)

def run_specific_tier(image_path: str, text_content: str, target_tier: str) -> Optional[Dict[str, Any]]:
    """Run a specific processing tier"""
    original_text = text_content or ''
    
    if target_tier == 'RegexOnly':
        result = process_invoice_regex(original_text)
        if result:
            result['processing_tier'] = 'RegexOnly'
            return result
    
    elif target_tier == 'Regex+DocTR':
        # Get DocTR OCR data
        doctr_data: Dict[str, Any] = {}
        doctr_text = ''
        try:
            doctr_data = process_with_doctr(image_path) or {}
            doctr_text = doctr_data.get('raw_text', '') or ''
        except Exception:
            pass
        
        # Combine texts
        if doctr_text:
            combined_lines = []
            seen = set()
            for ln in (original_text.splitlines() + doctr_text.splitlines()):
                k = ln.strip()
                if k and k not in seen:
                    seen.add(k)
                    combined_lines.append(ln)
            combined_text = '\n'.join(combined_lines)
        else:
            combined_text = original_text
        
        heuristic = process_invoice_regex(combined_text)
        from .merge import merge_tier1_tier2
        result = merge_tier1_tier2(heuristic, doctr_data)
        if result:
            result['processing_tier'] = 'Regex+DocTR'
            return result
    
    elif target_tier == 'Text_QA':
        doctr_data: Dict[str, Any] = {}
        doctr_text = ''
        try:
            doctr_data = process_with_doctr(image_path) or {}
            doctr_text = doctr_data.get('raw_text', '') or ''
        except Exception:
            pass
        
        if doctr_text:
            combined_lines = []
            seen = set()
            for ln in (original_text.splitlines() + doctr_text.splitlines()):
                k = ln.strip()
                if k and k not in seen:
                    seen.add(k)
                    combined_lines.append(ln)
            combined_text = '\n'.join(combined_lines)
        else:
            combined_text = original_text
        
        qa_source_parts = [combined_text]
        try:
            result = process_with_text_qa('\n'.join(qa_source_parts))
            if result and has_any_field(result):
                result['processing_tier'] = 'Text_QA'
                return result
            else:
                print("Text_QA didn't extract useful data, will fall back to LLM on next retry")
                return None
        except Exception as e:
            print(f"Text_QA processing failed: {e}")
            return None
    
    elif target_tier == 'LLM':
        doctr_data: Dict[str, Any] = {}
        doctr_text = ''
        try:
            doctr_data = process_with_doctr(image_path) or {}
            doctr_text = doctr_data.get('raw_text', '') or ''
        except Exception:
            pass
        
        if doctr_text:
            combined_lines = []
            seen = set()
            for ln in (original_text.splitlines() + doctr_text.splitlines()):
                k = ln.strip()
                if k and k not in seen:
                    seen.add(k)
                    combined_lines.append(ln)
            combined_text = '\n'.join(combined_lines)
        else:
            combined_text = original_text
        
        result = process_with_llm(combined_text)
        if result:
            result['processing_tier'] = 'LLM'
            return result
    
    return None

def is_output_valid(data):
    if not isinstance(data, dict):
        return False
    vendor = (data.get("vendor_name") or "").strip()
    total = data.get("total_amount")
    if not vendor or total is None:
        return False
    bad_tokens = [
        "invoice no", "invoice", "gstin", "dated", "tax invoice", "party :", "party:",
        "bill to", "ship to", "address", "order no", "prepared by", "amount"
    ]
    low = vendor.lower()
    if any(t in low for t in bad_tokens):
        return False
    address_tokens = ["road", "rd", "street", "st ", "st.", "lane", "ln", "complex", "tower",
                      "floor", "opp", "near", "shop", "block", "sector", "phase", "plot", "no.", "no "]
    if any(tok in low for tok in address_tokens):
        digits = sum(c.isdigit() for c in vendor)
        if digits >= 2 or vendor.count(',') >= 1:
            return False
    letters = sum(c.isalpha() for c in vendor)
    if letters < max(3, len(vendor) * 0.4):
        return False
    return True

def run_full_pipeline(image_path, text_content):
    pre_regex = process_invoice_regex(text_content or '') if text_content else {}
    vendor_ok = is_company_like_line((pre_regex.get('vendor_name') or '')) if isinstance(pre_regex, dict) else False
    if is_output_valid(pre_regex) and vendor_ok:
        pre_regex['file_path'] = image_path
        pre_regex.setdefault('status', 'SUCCESS')
        pre_regex['processing_tier'] = 'RegexOnly'
        save_to_db(pre_regex)
        return
    original_text = text_content or ''
    doctr_data: Dict[str, Any] = {}
    doctr_text = ''
    try:
        doctr_data = process_with_doctr(image_path) or {}
        doctr_text = doctr_data.get('raw_text', '') or ''
    except Exception:
        pass
    if doctr_text:
        combined_lines = []
        seen = set()
        for ln in (original_text.splitlines() + doctr_text.splitlines()):
            k = ln.strip()
            if k and k not in seen:
                seen.add(k)
                combined_lines.append(ln)
        combined_text = '\n'.join(combined_lines)
    else:
        combined_text = original_text
    heuristic = process_invoice_regex(combined_text)
    from .merge import merge_tier1_tier2
    merged = merge_tier1_tier2(heuristic, doctr_data)
    merged['file_path'] = image_path
    merged.setdefault('status', 'SUCCESS' if is_output_valid(merged) else 'PARTIAL')
    save_to_db(merged)
    if is_output_valid(merged):
        return
    def field_count(d: Dict[str, Any]):
        keys = ['vendor_name', 'invoice_number', 'invoice_date', 'total_amount', 'vendor_gstin', 'customer_gstin']
        return sum(1 for k in keys if d.get(k) not in (None, ''))
    baseline_count = field_count(merged)
    qa_source_parts = [combined_text]
    for k in ['vendor_name', 'invoice_number']:
        v = merged.get(k)
        if isinstance(v, str):
            qa_source_parts.append(v)
    qa_data = process_with_text_qa('\n'.join(qa_source_parts))
    if has_any_field(qa_data):
        qa_merged = dict(merged)
        improved = False
        for key in ['vendor_name','invoice_date','vendor_gstin','customer_gstin']:
            val = qa_data.get(key)
            if val and val != qa_merged.get(key):
                qa_merged[key] = val
                improved = True
        if qa_data.get('invoice_number'):
            new_n = qa_data['invoice_number']
            old_n = qa_merged.get('invoice_number')
            from .utils import alnum_mix
            if new_n and new_n != old_n:
                if (not old_n) or (alnum_mix(new_n) and not alnum_mix(old_n)) or (len(new_n) > len(old_n)):
                    qa_merged['invoice_number'] = new_n
                    improved = True
        if qa_data.get('total_amount') is not None:
            existing_total = qa_merged.get('total_amount')
            new_total = qa_data.get('total_amount')
            if existing_total is None or (isinstance(new_total,(int,float)) and isinstance(existing_total,(int,float)) and new_total > existing_total*1.05):
                qa_merged['total_amount'] = new_total
                improved = True
        qa_merged['processing_tier'] = qa_data.get('processing_tier','Text_QA')
        qa_merged['file_path'] = image_path
        qa_merged.setdefault('status', 'SUCCESS' if is_output_valid(qa_merged) else 'PARTIAL')
        qa_count = field_count(qa_merged)
        if improved and (qa_count > baseline_count or (not is_output_valid(merged) and is_output_valid(qa_merged))):
            save_to_db(qa_merged)
            if is_output_valid(qa_merged):
                return
            merged = qa_merged
            baseline_count = qa_count
    llm_out = process_with_llm(combined_text)
    if has_any_field(llm_out):
        llm_count = field_count(llm_out)
        if llm_count > baseline_count or (not is_output_valid(merged) and is_output_valid(llm_out)):
            llm_out['file_path'] = image_path
            llm_out.setdefault('status', 'SUCCESS' if is_output_valid(llm_out) else 'PARTIAL')
            save_to_db(llm_out)
            if is_output_valid(llm_out):
                return
            merged = llm_out
            baseline_count = llm_count
    if not is_output_valid(merged):
        pass
    if not has_any_field(merged):
        save_to_db({ 'file_path': image_path, 'status': 'FAILED', 'processing_tier': 'ALL_TIERS' })
