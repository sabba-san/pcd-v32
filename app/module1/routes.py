# from flask import Blueprint, request, jsonify

# # Safe Imports with Error Handling
# try:
#     from ..chatbot_core import process_query, analyze_legal_text, analyze_defect_image, analyze_pdf_document
#     from ..conversation_logger import save_history
#     from ..dlp_knowledge_base import get_all_guidelines, get_all_legal_references
#     from ..feedback_manager import save_feedback
# except Exception as e:
#     # Save the error string securely so it doesn't get deleted by Python
#     error_msg = str(e)
#     print(f"CRITICAL IMPORT ERROR: {error_msg}")
    
#     # Dummy functions that safely return the REAL error to your chat screen
#     process_query = lambda x: f"Backend Error: {error_msg}"
#     analyze_legal_text = lambda x: f"Backend Error: {error_msg}"
#     analyze_defect_image = lambda x: f"Backend Error: {error_msg}"
#     analyze_pdf_document = lambda x: f"Backend Error: {error_msg}"
    
#     save_history = lambda x: None
#     get_all_guidelines = lambda: []
#     get_all_legal_references = lambda: []

# module1 = Blueprint('module1', __name__, url_prefix='/api')

# @module1.route('/chat', methods=['POST'])
# def api_chat():
#     try:
#         data = request.json
#         message = data.get('message', '').strip()
        
#         if not message:
#             return jsonify({"error": "Empty message"}), 400
        
#         response_text = process_query(message)
        
#         try:
#             save_history({"user": message, "bot": response_text})
#         except Exception:
#             pass # Ignore history save errors
            
#         return jsonify({"response": response_text})
        
#     except Exception as e:  # <--- THIS IS THE FIX (added 'as e')
#         print(f"ROUTE ERROR: {e}")
#         return jsonify({"error": f"Server Error: {str(e)}"}), 500

# @module1.route('/analyze', methods=['POST'])
# def api_analyze():
#     try:
#         data = request.json
#         text = data.get('message', '').strip()
        
#         if not text:
#             return jsonify({"error": "Empty text"}), 400
            
#         response_text = analyze_legal_text(text)
#         return jsonify({"response": response_text})
        
#     except Exception as e: # <--- THIS IS THE FIX (added 'as e')
#         print(f"ANALYZE ERROR: {e}")
#         return jsonify({"error": f"Server Error: {str(e)}"}), 500

# @module1.route('/guidelines', methods=['GET'])
# def api_guidelines():
#     return jsonify({"guidelines": get_all_guidelines()})

# @module1.route('/legal-references', methods=['GET'])
# def api_legal_references():
#     return jsonify({"references": get_all_legal_references()})

# @module1.route('/analyze-image', methods=['POST'])
# def api_analyze_image():
#     try:
#         data = request.json
#         base64_image = data.get('image', '')
        
#         if not base64_image:
#             return jsonify({"error": "No image provided"}), 400
            
#         # Strip the HTML data prefix so Groq can read the pure image code
#         if "," in base64_image:
#             base64_image = base64_image.split(",")[1]
            
#         response_text = analyze_defect_image(base64_image)
#         return jsonify({"response": response_text})
        
#     except Exception as e:
#         print(f"VISION ERROR: {e}")
#         return jsonify({"error": f"Server Error: {str(e)}"}), 500

# @module1.route('/analyze-pdf', methods=['POST'])
# def api_analyze_pdf():
#     try:
#         if 'pdf' not in request.files:
#             return jsonify({"error": "No PDF file uploaded"}), 400
        
#         pdf_file = request.files['pdf']
        
#         if pdf_file.filename == '':
#             return jsonify({"error": "No selected file"}), 400
            
#         if not pdf_file.filename.lower().endswith('.pdf'):
#             return jsonify({"error": "Invalid file format. Please upload a PDF."}), 400

#         # Read the file as bytes
#         pdf_bytes = pdf_file.read()
        
#         # Send to core logic
#         response_text = analyze_pdf_document(pdf_bytes)
        
#         return jsonify({"response": response_text})
        
#     except Exception as e:
#         print(f"PDF ROUTE ERROR: {e}")
#         return jsonify({"error": f"Server Error: {str(e)}"}), 500
##############################################################################################
#test1
from flask import Blueprint, request, jsonify

# Safe Imports with Error Handling
try:
    from ..chatbot_component.chatbot_core import process_query, analyze_legal_text, analyze_defect_image, analyze_pdf_document
    from ..chatbot_component.conversation_logger import save_history
    from ..chatbot_component.dlp_knowledge_base import get_all_guidelines, get_all_legal_references
    from ..chatbot_component.feedback_manager import save_feedback
except Exception as e:
    # Save the error string securely so it doesn't get deleted by Python
    error_msg = str(e)
    print(f"CRITICAL IMPORT ERROR: {error_msg}")
    
    # Dummy functions that safely return the REAL error to your chat screen
    process_query = lambda x: f"Backend Error: {error_msg}"
    analyze_legal_text = lambda x: f"Backend Error: {error_msg}"
    analyze_defect_image = lambda x: f"Backend Error: {error_msg}"
    analyze_pdf_document = lambda x: f"Backend Error: {error_msg}"
    
    save_history = lambda x: None
    get_all_guidelines = lambda: []
    get_all_legal_references = lambda: []
    save_feedback = lambda *args, **kwargs: None 

module1 = Blueprint('module1', __name__, url_prefix='/api')

@module1.route('/chat', methods=['POST'])
def api_chat():
    try:
        data = request.json
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({"error": "Empty message"}), 400
        
        response_text = process_query(message)
        
        try:
            save_history({"user": message, "bot": response_text})
        except Exception:
            pass # Ignore history save errors
            
        return jsonify({"response": response_text})
        
    except Exception as e:
        print(f"ROUTE ERROR: {e}")
        return jsonify({"error": f"Server Error: {str(e)}"}), 500

@module1.route('/analyze', methods=['POST'])
def api_analyze():
    try:
        data = request.json
        text = data.get('message', '').strip()
        
        if not text:
            return jsonify({"error": "Empty text"}), 400
            
        response_text = analyze_legal_text(text)
        return jsonify({"response": response_text})
        
    except Exception as e:
        print(f"ANALYZE ERROR: {e}")
        return jsonify({"error": f"Server Error: {str(e)}"}), 500

@module1.route('/guidelines', methods=['GET'])
def api_guidelines():
    return jsonify({"guidelines": get_all_guidelines()})

@module1.route('/legal-references', methods=['GET'])
def api_legal_references():
    return jsonify({"references": get_all_legal_references()})

@module1.route('/analyze-image', methods=['POST'])
def api_analyze_image():
    try:
        data = request.json
        base64_image = data.get('image', '')
        
        if not base64_image:
            return jsonify({"error": "No image provided"}), 400
            
        # Strip the HTML data prefix so Groq can read the pure image code
        if "," in base64_image:
            base64_image = base64_image.split(",")[1]
            
        response_text = analyze_defect_image(base64_image)
        return jsonify({"response": response_text})
        
    except Exception as e:
        print(f"VISION ERROR: {e}")
        return jsonify({"error": f"Server Error: {str(e)}"}), 500

@module1.route('/analyze-pdf', methods=['POST'])
def api_analyze_pdf():
    try:
        if 'pdf' not in request.files:
            return jsonify({"error": "No PDF file uploaded"}), 400
        
        pdf_file = request.files['pdf']
        
        if pdf_file.filename == '':
            return jsonify({"error": "No selected file"}), 400
            
        if not pdf_file.filename.lower().endswith('.pdf'):
            return jsonify({"error": "Invalid file format. Please upload a PDF."}), 400

        # Read the file as bytes
        pdf_bytes = pdf_file.read()
        
        # Send to core logic
        response_text = analyze_pdf_document(pdf_bytes)
        
        return jsonify({"response": response_text})
        
    except Exception as e:
        print(f"PDF ROUTE ERROR: {e}")
        return jsonify({"error": f"Server Error: {str(e)}"}), 500


