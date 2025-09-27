from typing import Dict, Any
from transformers.pipelines import pipeline
from .config import QA_MODEL, GSTIN_REGEX
from .utils import parse_date_str, clean_amount, is_company_like_line, normalize_invoice_number

_qa_pipeline = None

def _get_qa_pipeline():
    global _qa_pipeline
    if _qa_pipeline is not None:
        return _qa_pipeline
    try:
        _qa_pipeline = pipeline("question-answering", model=QA_MODEL, tokenizer=QA_MODEL)
    except Exception:
        _qa_pipeline = None
    return _qa_pipeline

def process_with_text_qa(text: str) -> Dict[str, Any]:
    qa = _get_qa_pipeline()
    if not qa or not text.strip():
        return {}
    questions = {
        "vendor_name": "What is the registered legal name of the vendor company?",
        "invoice_number": "Provide only the invoice number (exact code).",
        "invoice_date": "What is the invoice date (day month year)?",
        "total_amount": "What is the grand total amount (numbers only)?",
        "vendor_gstin": "Provide only the 15-character vendor GSTIN code.",
        "customer_gstin": "Provide only the 15-character customer GSTIN code."
    }
    answers: Dict[str, Any] = {}
    for field, q in questions.items():
        try:
            ctx = text[:12000]
            result = qa(question=q, context=ctx)
            # Handle transformers pipeline result properly
            if isinstance(result, dict) and "answer" in result:
                ans = result["answer"]
            else:
                continue
            if ans and ans.lower() not in {"", "n/a", "none", "no"}:
                answers[field] = ans.strip()
        except Exception:
            pass
    if 'invoice_date' in answers:
        d = parse_date_str(answers['invoice_date'])
        if d:
            answers['invoice_date'] = d
        else:
            answers.pop('invoice_date', None)
    if 'invoice_number' in answers:
        inv = normalize_invoice_number(answers['invoice_number'])
        if inv:
            answers['invoice_number'] = inv
        else:
            answers.pop('invoice_number', None)
    if 'total_amount' in answers:
        amt = clean_amount(answers['total_amount'])
        if amt is not None and amt >= 50:
            answers['total_amount'] = amt
        else:
            answers.pop('total_amount', None)
    for k in ['vendor_gstin', 'customer_gstin']:
        v = answers.get(k)
        if v:
            v_clean = v.strip().upper().replace(' ', '')
            if GSTIN_REGEX.match(v_clean):
                answers[k] = v_clean
            else:
                answers.pop(k, None)
    vn = answers.get('vendor_name')
    if vn:
        vn_clean = vn.strip()
        bad_vendor_tokens = {'inr','thousand','hundred','only','gstin','invoice','amount'}
        lower_v = vn_clean.lower()
        if (lower_v.startswith('inr ') or any(t in lower_v for t in bad_vendor_tokens)
            or len(vn_clean) < 3 or sum(c.isalpha() for c in vn_clean) < 3
            or not is_company_like_line(vn_clean)):
            answers.pop('vendor_name', None)
        else:
            vn_clean = vn_clean.replace('  ', ' ').strip(' ,:;')
            answers['vendor_name'] = vn_clean[:120]
    if answers:
        answers['processing_tier'] = 'Text_QA'
    return answers
