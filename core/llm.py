import json
import os
from typing import Dict, Any
import requests
from .config import LLM_MODEL
from .utils import parse_date_str, clean_amount, normalize_invoice_number

def process_with_llm(text: str) -> Dict[str, Any]:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key or not text.strip():
        return {}
    model = LLM_MODEL or "mixtral-8x7b-32768"
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        system_prompt = (
            "You extract structured invoice fields. Return STRICT minified JSON with keys: "
            "vendor_name, invoice_number, invoice_date (ISO yyyy-mm-dd), total_amount (number), "
            "vendor_gstin, customer_gstin. Missing values use null. No extra text.")
        user_prompt = f"Invoice Text:\n{text[:15000]}"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        resp = requests.post(url, json=payload, headers=headers, timeout=60)
        if resp.status_code != 200:
            return {}
        data = resp.json()
        content = (data.get('choices') or [{}])[0].get('message', {}).get('content', '')
        if not content:
            return {}
        i, j = content.find('{'), content.rfind('}')
        if i == -1 or j == -1:
            return {}
        parsed = json.loads(content[i:j+1])
        if parsed.get('invoice_date'):
            parsed['invoice_date'] = parse_date_str(parsed['invoice_date']) or parsed['invoice_date']
        if parsed.get('total_amount') is not None:
            parsed['total_amount'] = clean_amount(parsed['total_amount'])
        if parsed.get('invoice_number'):
            parsed['invoice_number'] = normalize_invoice_number(parsed.get('invoice_number'))
        parsed['processing_tier'] = 'LLM'
        return parsed
    except Exception:
        return {}
