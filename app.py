from flask import Flask, request, jsonify
import os
import PyPDF2
import pytesseract
from PIL import Image
import re
from dateutil.parser import parse


def clean_amount(amount_str):
    if not amount_str:
        return None
    try:
        cleaned_str = re.sub(r'[₹,]', '', str(amount_str)).strip()
        return float(cleaned_str)
    except (ValueError, TypeError):
        return None

def parse_date(date_str):
    if not date_str:
        return None
    try:
        return parse(date_str, fuzzy=True).date().isoformat()
    except (ValueError, TypeError):
        return None

def find_first_match(text, patterns):
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None

def get_invoice_sections(text):
    sections = {
        "header": text,
        "line_items": "",
        "summary": ""
    }

    line_item_start_marker = r'(?i)^\s*(?:si no|description|particulars|itemname|hsn/sac)'
    summary_start_marker = r'(?i)^\s*(?:total|subtotal|amount chargeable|balance due)'

    line_item_match = re.search(line_item_start_marker, text, re.MULTILINE)
    summary_match = re.search(summary_start_marker, text, re.MULTILINE)

    if line_item_match:
        sections["header"] = text[:line_item_match.start()]
        if summary_match:
            sections["line_items"] = text[line_item_match.start():summary_match.start()]
            sections["summary"] = text[summary_match.start():]
        else:
            sections["line_items"] = text[line_item_match.start():]
            sections["summary"] = text[line_item_match.start():] 
    elif summary_match:
        sections["header"] = text[:summary_match.start()]
        sections["summary"] = text[summary_match.start():]
    
    return sections

def extract_line_items(line_items_text):
    items = []
    item_pattern = r"(?m)^(?!\s*total)(?!\s*cgst)(?!\s*sgst)(.+?)\s+([\d,]+\.\d{2})\s*$"
    
    potential_lines = line_items_text.split('\n')
    for line in potential_lines:
        if re.search(r'(?i)total|cgst|sgst|subtotal|tax', line):
            continue
            
        match = re.search(r'([\d,]+\.\d{2})', line)
        if match:
            amount = clean_amount(match.group(1))
            description = line[:match.start()].strip()
            if len(description) > 3:
                 items.append({"description": description, "amount": amount})

    return items

def validate_results(data):
    validation = {"is_valid": True, "warnings": []}

    essential_fields = ['invoice_number', 'invoice_date', 'total_amount', 'vendor_name']
    for field in essential_fields:
        if not data.get(field):
            validation["is_valid"] = False
            validation["warnings"].append(f"Missing essential field: {field}")

    if data.get("line_items") and data.get("total_amount"):
        line_items_total = sum(item.get('amount', 0) for item in data['line_items'] if item.get('amount'))
        
        if abs(line_items_total - data["total_amount"]) > 0.05 * data["total_amount"]: 
            validation["is_valid"] = False
            validation["warnings"].append(f"Line items total ({line_items_total}) does not approximate the invoice total ({data['total_amount']}).")

    return validation

def process_invoice(text):
    #regex patterns -> use to find matches.
    invoice_number_patterns = [r'Invoice No\.\s*[:\s]*([\w/-]+)', r'Invoice No\s*[:\s]*([\w/-]+)', r'Invoice Code\s*[:\s]*([\w/-]+)', r'Tax Invoice#\s*([\w/-]+)']
    date_patterns = [r'Dated\s*[:\s]*(\d{1,2}[-/\s][A-Za-z]{3,}[-/\s]\d{2,4})', r'Invoice Date\s*[:\s]*([\w\d\s-]+)', r'Dt[:\s]*(\d{2}/\d{2}/\d{4})']
    total_amount_patterns = [r'BALANCE DUE\s*₹?\s*([0-9,]+\.\d{2})', r'Total\s*₹?\s*([0-9,]+\.\d{2})', r'Total Amount after Tax\s*₹?\s*([0-9,]+\.\d{2})']
    vendor_name_patterns = [r'^(.*?)\n', r'for\s+(.*?)\n']
    customer_name_patterns = [r'Party\s*[:\s]*(.*?)\n', r'Bill to Party\nName\s*[:\s]*(.*?)\n', r'Billing Address\n(.*?)\n', r'Customer Address[:\s]*(.*?)\n']
    gstin_pattern = r'\b(\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]{1})\b'

    #Split to sections -> check for vendor name, gstin, name, invoice number and date, total amount, total number of items
    sections = get_invoice_sections(text)

    vendor_name = find_first_match(sections["header"], vendor_name_patterns)
    if vendor_name and 'invoice' in vendor_name.lower():
        vendor_name = find_first_match(sections["header"], [r'^[^\n]*\n(.*?)\n'])

    customer_name = find_first_match(sections["header"], customer_name_patterns)
    invoice_number = find_first_match(sections["header"], invoice_number_patterns)
    invoice_date = parse_date(find_first_match(sections["header"], date_patterns))
    total_amount = clean_amount(find_first_match(sections["summary"], total_amount_patterns))

    all_gstins = re.findall(gstin_pattern, text, re.IGNORECASE)
    vendor_gstin = all_gstins[0] if all_gstins else None
    customer_gstin = all_gstins[1] if len(all_gstins) > 1 else None
    
    line_items = extract_line_items(sections["line_items"])

    extracted_data = {
        "vendor_name": vendor_name,
        "vendor_gstin": vendor_gstin,
        "customer_name": customer_name,
        "customer_gstin": customer_gstin,
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "total_amount": total_amount,
        "line_items": line_items
    }
    
    validation_results = validate_results(extracted_data)
    extracted_data["validation"] = validation_results
    
    return extracted_data

app = Flask(__name__)

UPLOAD_DIR = 'uploads'
app.config['UPLOAD_DIR'] = UPLOAD_DIR

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

@app.route('/upload', methods = ['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error: No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error: no file selected"}), 400
    if file:
        filepath = os.path.join(app.config['UPLOAD_DIR'], file.filename)
        file.save(filepath)

        text = ""
        if file.filename.lower().endswith('.pdf'):
            try:
                with open(filepath, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        text += page.extract_text()
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        elif file.filename.lower().in_(['.png', '.jpg', '.jpeg']):
            try:
                text = pytesseract.image_to_string(Image.open(filepath))
            except Exception as e:
                return jsonify({"error": "OCR processing failed", "details": str(e)}), 500
        
        else:
            return jsonify({"error": "Unsupported file type"}), 400
        
        parsed_data = process_invoice(text) #need to implement parsing
        return jsonify(parsed_data)


if __name__ == '__main__':
    app.run(debug=True)