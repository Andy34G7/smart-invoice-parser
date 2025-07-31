from flask import Flask, request, jsonify
import os

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

        # wip

        return jsonify({"message": "file uploaded successfully", "filename": file.filename})


if __name__ == '__main__':
    app.run(debug=True)