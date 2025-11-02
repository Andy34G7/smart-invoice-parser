# Smart Invoice Parser

A comprehensive web-based invoice processing system that intelligently extracts key information from PDF invoices and images using multiple AI processing tiers.

## Processing Tiers

The system uses a progressive processing approach with multiple AI tiers:

1. **RegexOnly** - Regex-based pattern matching
2. **Regex+DocTR** - Enhanced OCR with Facebook's DocTR model
3. **Text_QA** - Question-answering using transformer models
4. **LLM** - Large Language Model processing for complex cases


## Installation

### Prerequisites
- Python 3.8+
- Virtual environment (recommended)
- Required system packages for OCR processing

### Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/Comono-India-Internal/hemanth-smart_invoice_parser.git
   cd hemanth-smart_invoice_parser
   ```

2. Create and activate virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the application:
   ```bash
   python app.py
   ```

5. Open your browser and navigate to `http://127.0.0.1:5000`

## Configuration

### Environment Variables
Create a `.env` file in the root directory:

```env
# AI Model Configuration
INVOICE_QA_MODEL=distilbert-base-cased-distilled-squad
INVOICE_LLM_MODEL=your-llm-model-name

# Feature Toggles
ENABLE_TEXT_QA=false  # Set to true to enable Text_QA processing tier
```

### Processing Tier Configuration
- **Text_QA**: Disabled by default due to compatibility considerations
- **LLM**: Requires proper model configuration
- **DocTR**: Enabled by default for enhanced OCR

## Usage

### Basic Workflow
1. **Upload**: Drag and drop or select invoice files
2. **Process**: System automatically processes with RegexOnly tier
3. **Review**: Check extracted data in the editable table
4. **Retry**: Use "Retry Parsing" for better accuracy with advanced tiers
5. **Verify**: Click "Verified" to save confirmed data to database

### Processing Tier Progression
- Start with **RegexOnly** for fast processing
- Retry with **Regex+DocTR** for better OCR accuracy
- Advanced users can enable **Text_QA** and **LLM** tiers

## Project Structure

``` text
├── app.py                 # Main Flask application
├── database.py           # Database operations and schema
├── requirements.txt      # Python dependencies
├── core/                 # Core processing modules
│   ├── config.py        # Configuration settings
│   ├── pipeline.py      # Processing tier orchestration
│   ├── ocr.py          # DocTR OCR processing
│   ├── qa.py           # Question-answering processing
│   ├── llm.py          # LLM processing
│   ├── regex_extract.py # Regex-based extraction
│   └── utils.py        # Utility functions
├── static/              # Frontend assets
│   ├── css/            # Stylesheets
│   └── js/             # JavaScript files
├── templates/           # HTML templates
├── uploads/            # Uploaded files storage
└── invoices/           # Sample invoice files
```

## API Endpoints

- `GET /` - Main application interface
- `POST /upload` - File upload and initial processing
- `POST /verify/<filename>` - Verify and save extracted data
- `POST /reparse/<filename>` - Retry processing with next tier


## Technical Details

### Models Used

- **DocTR**: Facebook's Document Text Recognition for OCR
- **Transformers**: Hugging Face transformers for question-answering

### Database Schema

- SQLite database with invoice records
- Verification status tracking
- Processing tier metadata
- File path associations

### Frontend

- **PDF.js**: Client-side PDF rendering

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
