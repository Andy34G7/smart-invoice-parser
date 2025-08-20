import os
import PyPDF2
from PIL import Image
import pytesseract
from core.pipeline import run_full_pipeline
from database import setup_database, get_result_by_filename

INVOICE_DIR = 'invoices'
UPLOAD_DIR = 'uploads'


def ensure_dirs():
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)


def extract_text_for_file(src_path: str) -> str:
    text_content = ''
    try:
        lower = src_path.lower()
        if lower.endswith('.pdf'):
            with open(src_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text_content += page.extract_text() or ''
        elif lower.endswith(('.png', '.jpg', '.jpeg')):
            text_content = pytesseract.image_to_string(Image.open(src_path))
    except Exception as e:
        print(f"Failed to extract text from {src_path}: {e}")
    return text_content


def process_all():
    setup_database()
    ensure_dirs()
    for fname in os.listdir(INVOICE_DIR):
        src_path = os.path.join(INVOICE_DIR, fname)
        if not os.path.isfile(src_path):
            continue
        if not fname.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg')):
            continue
        dest_path = os.path.join(UPLOAD_DIR, fname)
        if not os.path.exists(dest_path):
            # copy file into uploads for consistency
            try:
                with open(src_path, 'rb') as src, open(dest_path, 'wb') as dst:
                    dst.write(src.read())
            except Exception as e:
                print(f"Could not copy {fname} to uploads: {e}")
        print(f"Processing {fname}...")
        text = extract_text_for_file(dest_path)
        run_full_pipeline(dest_path, text)
        result = get_result_by_filename(fname)
        print('Result:', result)


if __name__ == '__main__':
    process_all()
