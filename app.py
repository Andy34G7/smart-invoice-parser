from flask import Flask, request, jsonify
import os
import PyPDF2
from PIL import Image
import pytesseract
from invoice_processor import run_full_pipeline
from database import setup_database, get_result_by_filename

app = Flask(__name__)

UPLOAD_DIR = 'uploads'
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

setup_database()

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    if file:
        filepath = os.path.join(UPLOAD_DIR, file.filename)
        file.save(filepath)

        text_content = ""
        try:
            if file.filename.lower().endswith('.pdf'):
                with open(filepath, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        text_content += page.extract_text()
            elif file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                text_content = pytesseract.image_to_string(Image.open(filepath))
            else:
                 return jsonify({"error": "Unsupported file type"}), 400
        except Exception as e:
            return jsonify({"error": f"Failed to read file content: {e}"}), 500
        
        run_full_pipeline(filepath, text_content)

        return jsonify({
            "message": "File received and is being processed.",
            "filename": file.filename,
            "results_url": f"/results/{file.filename}"
        }), 202

@app.route('/results/<filename>', methods=['GET'])
def get_results(filename):
    """New endpoint to retrieve processing results from the database."""
    result = get_result_by_filename(filename)
    if result:
        return jsonify(result), 200
    else:
        return jsonify({"error": "Results not found or still processing."}), 404

if __name__ == '__main__':
    app.run(debug=True)