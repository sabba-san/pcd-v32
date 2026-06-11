"""
Thin re-export layer — delegates to the ChatService in app/services/.
Keeps backward compatibility for any code importing from chatbot_component.
"""
from ..services.chat_service import ChatService as _ChatService

process_query       = _ChatService.process_query
process_query_stream = _ChatService.process_query_stream
analyze_legal_text  = _ChatService.analyze_text
analyze_defect_image = _ChatService.analyze_image
analyze_pdf_document = _ChatService.analyze_pdf
