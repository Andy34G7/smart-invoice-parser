import os
from typing import Dict, Any, List
_doctr_predictor = None

def _get_doctr_predictor():
    global _doctr_predictor
    if _doctr_predictor is not None:
        return _doctr_predictor
    try:
        from doctr.models import ocr_predictor
        _doctr_predictor = ocr_predictor(pretrained=True)
    except Exception:
        _doctr_predictor = None
    return _doctr_predictor

def process_with_doctr(image_path: str) -> Dict[str, Any]:
    predictor = _get_doctr_predictor()
    if predictor is None:
        return {}
    ext = os.path.splitext(image_path)[1].lower()
    if ext not in {'.png', '.jpg', '.jpeg'}:
        return {}
    try:
        from doctr.io import DocumentFile
        doc = DocumentFile.from_images(image_path)
        result = predictor(doc)
        exported = result.export()
        lines: List[str] = []
        for page in exported.get('pages', []):
            for block in page.get('blocks', []):
                for line in block.get('lines', []):
                    line_text = ' '.join([w.get('value', '') for w in line.get('words', [])]).strip()
                    if line_text:
                        lines.append(line_text)
        full_text = '\n'.join(lines)
        data: Dict[str, Any] = {'raw_text': full_text, 'processing_tier': 'DocTR'}
        first_line = next((ln for ln in full_text.splitlines() if ln.strip()), None)
        if first_line:
            data['vendor_name'] = first_line.strip()[:120]
        return data
    except Exception:
        return {}
