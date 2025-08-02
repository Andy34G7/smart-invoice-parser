import re
from PIL import Image
from dateutil.parser import parse
from transformers import (DonutProcessor, VisionEncoderDecoderModel)
from database import save_to_db

def clean_amount(s):
    return float(re.sub(r'[₹,]', '', str(s)).strip()) if s else None

def parse_date_str(s):
    return parse(s, fuzzy=True).date().isoformat() if s else None

def find_first_match(text, patterns):
    for p in patterns:
        match = re.search(p, text, re.IGNORECASE | re.MULTILINE)
        if match: return match.group(1).strip()
    return None

def get_invoice_sections(text):
    sections = {"header": text, "summary": text}
    summary_match = re.search(r'(?i)^\s*(?:total|subtotal|amount chargeable|balance due)', text, re.MULTILINE)
    if summary_match:
        sections["header"] = text[:summary_match.start()]
        sections["summary"] = text[summary_match.start():]
    return sections

def process_invoice_regex(text):
    print("--- Using Regex parse ---")
    invoice_number_patterns = [r'Invoice No\.\s*[:\s]*([\w/-]+)', r'Invoice No\s*[:\s]*([\w/-]+)', r'Invoice Code\s*[:\s]*([\w/-]+)', r'Tax Invoice#\s*([\w/-]+)']
    date_patterns = [r'Dated\s*[:\s]*(\d{1,2}[-/\s][A-Za-z]{3,}[-/\s]\d{2,4})', r'Invoice Date\s*[:\s]*([\w\d\s-]+)', r'Dt[:\s]*(\d{2}/\d{2}/\d{4})']
    total_amount_patterns = [r'BALANCE DUE\s*₹?\s*([0-9,]+\.\d{2})', r'Total Amount after Tax\s*₹?\s*([0-9,]+\.\d{2})', r'Total\s*₹?\s*([0-9,]+\.\d{2})']
    vendor_name_patterns = [r'^(.*?)\n']
    gstin_pattern = r'\b(\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]{1})\b'
    
    sections = get_invoice_sections(text)
    vendor_name = find_first_match(sections["header"], vendor_name_patterns)
    
    extracted_data = {
        "vendor_name": vendor_name,
        "invoice_number": find_first_match(text, invoice_number_patterns),
        "invoice_date": parse_date_str(find_first_match(text, date_patterns)),
        "total_amount": clean_amount(find_first_match(sections["summary"], total_amount_patterns)),
        "processing_tier": "Regex"
    }

    all_gstins = re.findall(gstin_pattern, text, re.IGNORECASE)
    extracted_data["vendor_gstin"] = all_gstins[0] if all_gstins else None
    extracted_data["customer_gstin"] = all_gstins[1] if len(all_gstins) > 1 else None
    return extracted_data

def process_with_donut(image_path):
    print("--- Using Donut model---")
    model_name = "naver-clova-ix/donut-base-finetuned-cord-v2"
    processor = DonutProcessor.from_pretrained(model_name)
    model = VisionEncoderDecoderModel.from_pretrained(model_name)
    image = Image.open(image_path).convert("RGB")
    pixel_values = processor(image, return_tensors="pt").pixel_values
    task_prompt = "<s_cord-v2>"
    decoder_input_ids = processor.tokenizer(task_prompt, add_special_tokens=False, return_tensors="pt").input_ids
    outputs = model.generate(pixel_values, decoder_input_ids=decoder_input_ids, max_length=model.decoder.config.max_position_embeddings, early_stopping=True, pad_token_id=processor.tokenizer.pad_token_id, eos_token_id=processor.tokenizer.eos_token_id, use_cache=True, num_beams=1, return_dict_in_generate=True)
    sequence = processor.batch_decode(outputs.sequences)[0]
    sequence = sequence.replace(processor.tokenizer.eos_token, "").replace(processor.tokenizer.pad_token, "")
    parsed_json = processor.token2json(sequence)
    total_price_str = parsed_json.get("total", {}).get("total_price")
    return { "vendor_name": parsed_json.get("menu", [{}])[0].get("nm"), "total_amount": float(total_price_str) if total_price_str else None, "invoice_date": parsed_json.get("meta", {}).get("issue_date"), "processing_tier": "Donut" }


def is_output_valid(data):
    return data and data.get("total_amount") is not None and data.get("vendor_name") is not None

def run_full_pipeline(image_path, text_content):
    print(f"\n Started trying to parse: {image_path}")
    
    # Tier 1: Regex
    final_data = process_invoice_regex(text_content)
    if is_output_valid(final_data):
        final_data["file_path"] = image_path
        save_to_db(final_data)
        return
        
    # Tier 2: Donut
    try:
        final_data = process_with_donut(image_path)
        if is_output_valid(final_data):
            final_data["file_path"] = image_path
            save_to_db(final_data)
            return
    except Exception as e:
        print(f"Processing with Donut failed.")
        
    print("All processing methods failed.")
    save_to_db({ "file_path": image_path, "status": "FAILED", "processing_tier": "ALL_TIERS" })