import os
import fitz  # This is the PyMuPDF library

DOCS_DIR = "legal_documents"
KNOWLEDGE_TEXT = ""

def load_pdf_knowledge():
    """Reads all PDFs in the folder using heavy-duty PyMuPDF."""
    import logging
    global KNOWLEDGE_TEXT
    if not os.path.exists(DOCS_DIR):
        logging.warning(f"{DOCS_DIR} folder not found.")
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
                logging.debug(f"Successfully read PDF file: {filename}")
            except Exception as e:
                logging.error(f"Could not read {filename}: {e}")
    
    KNOWLEDGE_TEXT = extracted_text
    logging.debug(f"Total characters loaded: {len(KNOWLEDGE_TEXT)}")
    return KNOWLEDGE_TEXT

# Dummy variables to prevent the UI from crashing
DLP_RULES = {}
def get_all_guidelines(): return []
def get_all_legal_references(): return []