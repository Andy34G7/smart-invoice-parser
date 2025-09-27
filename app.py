from flask import Flask, request, jsonify, render_template, send_file
import os
import PyPDF2
from PIL import Image
import pytesseract
from core.pipeline import run_full_pipeline
from database import setup_database, get_result_by_filename, upsert_verified_data

app = Flask(__name__)

UPLOAD_DIR = 'uploads'
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

setup_database()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    if file:
        filepath = os.path.join(UPLOAD_DIR, file.filename)
        print(f"Saving file to: {filepath}")
        file.save(filepath)
        print(f"File saved successfully: {os.path.exists(filepath)}")

        text_content = ""
        try:
            if file.filename.lower().endswith('.pdf'):
                with open(filepath, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        page_text = None
                        try:
                            page_text = page.extract_text()
                        except Exception:
                            page_text = None
                        if page_text:
                            text_content += page_text
            elif file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                text_content = pytesseract.image_to_string(Image.open(filepath))
            else:
                 return jsonify({"error": "Unsupported file type"}), 400
        except Exception as e:
            return jsonify({"error": f"Failed to read file content: {e}"}), 500
        
        run_full_pipeline(filepath, text_content)

        # Try to fetch parsed data immediately
        parsed = get_result_by_filename(file.filename)
        if parsed and parsed.get('status') != 'FAILED':
            return jsonify(parsed), 200

        # Fallback – provide polling URL
        return jsonify({
            "message": "File received; processing deferred",
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

@app.route('/verify/<filename>', methods=['POST'])
def verify_data(filename):
    """Endpoint to handle verified data updates"""
    try:
        verified_data = request.json
        if not verified_data:
            return jsonify({"error": "No data provided"}), 400
        
        upsert_verified_data(filename, verified_data)
        return jsonify({"message": "Data verified and updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to update data: {str(e)}"}), 500

@app.route('/reparse/<filename>', methods=['POST'])
def reparse_file(filename):
    """Endpoint to reparse an existing file using the next processing tier
    
    Processing tiers in order:
    1. RegexOnly - Fast regex-based extraction
    2. Regex+DocTR - Regex + OCR processing  
    3. Text_QA - Question-answering model
    4. LLM - Large language model processing
    """
    try:
        filepath = os.path.join(UPLOAD_DIR, filename)
        
        if not os.path.exists(filepath):
            return jsonify({"error": "File not found"}), 404
        
        # Read file content again
        text_content = ""
        try:
            if filename.lower().endswith('.pdf'):
                with open(filepath, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        page_text = None
                        try:
                            page_text = page.extract_text()
                        except Exception:
                            page_text = None
                        if page_text:
                            text_content += page_text
            elif filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                text_content = pytesseract.image_to_string(Image.open(filepath))
            else:
                return jsonify({"error": "Unsupported file type"}), 400
        except Exception as e:
            return jsonify({"error": f"Failed to read file content: {e}"}), 500
        
        # Get current processing tier from database
        current_result = get_result_by_filename(filename)
        current_tier = current_result.get('processing_tier') if current_result else None
        
        # Determine next tier
        from core.pipeline import get_next_tier, get_alternative_tier, run_specific_tier
        next_tier = get_next_tier(current_tier)
        
        if not next_tier:
            return jsonify({
                "error": f"Already processed with highest tier ({current_tier}). No higher tier available."
            }), 400
        
        # Run specific tier processing
        result = run_specific_tier(filepath, text_content, next_tier)
        
        # If Text_QA fails, try the alternative tier (LLM)
        if not result and next_tier == 'Text_QA':
            print(f"{next_tier} failed, trying alternative tier...")
            alternative_tier = get_alternative_tier(current_tier)
            if alternative_tier:
                print(f"Falling back to {alternative_tier} tier")
                result = run_specific_tier(filepath, text_content, alternative_tier)
        
        if result:
            # Add metadata and save to database
            result['file_path'] = filepath
            result.setdefault('status', 'SUCCESS' if result.get('vendor_name') and result.get('total_amount') else 'PARTIAL')
            from database import save_to_db
            save_to_db(result)
            
            # Return the new result
            updated_result = get_result_by_filename(filename)
            return jsonify(updated_result), 200
        else:
            attempted_tier = next_tier
            if next_tier == 'Text_QA':
                alternative_tier = get_alternative_tier(current_tier)
                if alternative_tier:
                    attempted_tier = f"{next_tier} and {alternative_tier}"
            
            return jsonify({
                "error": f"Processing with {attempted_tier} tier(s) failed to extract data"
            }), 500
        
    except Exception as e:
        return jsonify({"error": f"Failed to reparse file: {str(e)}"}), 500

@app.route('/pdf/<filename>')
def serve_pdf(filename):
    """Serve PDF files for preview"""
    try:
        file_path = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(file_path) and filename.lower().endswith('.pdf'):
            return send_file(file_path, mimetype='application/pdf')
        else:
            return jsonify({"error": "File not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/uploads/<filename>')
def serve_uploaded_file(filename):
    """Serve uploaded files for preview"""
    try:
        file_path = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(file_path):
            return send_file(file_path)
        else:
            return jsonify({"error": "File not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)