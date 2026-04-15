import os
import fitz  # This is the PyMuPDF library

DOCS_DIR = "legal_documents"
KNOWLEDGE_TEXT = ""

def load_pdf_knowledge():
    """Reads all PDFs in the folder using heavy-duty PyMuPDF."""
    global KNOWLEDGE_TEXT
    if not os.path.exists(DOCS_DIR):
        print(f"WARNING: {DOCS_DIR} folder not found.")
        return "No legal documents found."
    
    extracted_text = ""
    for filename in os.listdir(DOCS_DIR):
        if filename.lower().endswith(".pdf"):
            filepath = os.path.join(DOCS_DIR, filename)
            try:
                # Use PyMuPDF to crack open the file
                doc = fitz.open(filepath)
                for page in doc:
                    extracted_text += page.get_text() + "\n"
                print(f"DEBUG: Successfully read PDF file: {filename}")
            except Exception as e:
                print(f"ERROR: Could not read {filename}: {e}")
    
    KNOWLEDGE_TEXT = extracted_text
    print(f"DEBUG: Total characters loaded: {len(KNOWLEDGE_TEXT)}")
    return KNOWLEDGE_TEXT

# Dummy variables to prevent the UI from crashing
DLP_RULES = {}
def get_all_guidelines(): return []
def get_all_legal_references(): return []