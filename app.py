from flask import Flask, request, jsonify
import os
import PyPDF2
import pytesseract
from PIL import Image

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
        
        parsed_data = "" #need to implement parsing
        return jsonify(parsed_data)


if __name__ == '__main__':
    app.run(debug=True)