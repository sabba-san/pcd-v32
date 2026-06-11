from flask import Blueprint, request, jsonify, Response, stream_with_context

try:
    from ..services.chat_service import ChatService
    from ..services.notice_service import NoticeService
    from ..chatbot_component.conversation_logger import save_history, load_history
    from ..chatbot_component.dlp_knowledge_base import get_all_guidelines, get_all_legal_references
    from ..chatbot_component.feedback_manager import save_feedback
except Exception as e:
    error_msg = str(e)
    print(f"CRITICAL IMPORT ERROR: {error_msg}")

    class ChatService:
        @staticmethod
        def process_query(msg, history=None): return f"Backend Error: {error_msg}"
        @staticmethod
        def process_query_stream(msg, history=None):
            import json
            yield f"data: {json.dumps({'type': 'chunk', 'content': f'Backend Error: {error_msg}'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        @staticmethod
        def analyze_text(t): return f"Backend Error: {error_msg}"
        @staticmethod
        def analyze_image(img): return f"Backend Error: {error_msg}"
        @staticmethod
        def analyze_pdf(pdf): return f"Backend Error: {error_msg}"

    class NoticeService:
        @staticmethod
        def save_notice(user, data): return None

    save_history = lambda x, **kwargs: None
    load_history = lambda user_id="guest": []
    get_all_guidelines = lambda: []
    get_all_legal_references = lambda: []
    save_feedback = lambda *args, **kwargs: None


module1 = Blueprint('module1', __name__, url_prefix='/api')


# ── Chat (non-streaming, backward-compatible) ───────────────────────────

@module1.route('/chat', methods=['POST'])
def api_chat():
    try:
        from flask_login import current_user

        data = request.json
        message = (data.get('message') or '').strip()
        history = data.get('history')

        if not message:
            return jsonify({"error": "Empty message"}), 400

        response_text = ChatService.process_query(message, history)

        try:
            user_id = current_user.id if current_user.is_authenticated else "guest"
            save_history({"user": message, "bot": response_text}, user_id=user_id)
        except Exception:
            pass

        return jsonify({"response": response_text})

    except Exception as e:
        return jsonify({"error": f"Server Error: {str(e)}"}), 500


# ── Chat (SSE streaming) ────────────────────────────────────────────────

@module1.route('/chat/stream', methods=['POST'])
def api_chat_stream():
    try:
        data = request.json
        message = (data.get('message') or '').strip()
        history = data.get('history')

        if not message:
            return jsonify({"error": "Empty message"}), 400

        def generate():
            yield from ChatService.process_query_stream(message, history)

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
                'Connection': 'keep-alive',
            },
        )

    except Exception as e:
        return jsonify({"error": f"Server Error: {str(e)}"}), 500


# ── Chat history ────────────────────────────────────────────────────────

@module1.route('/chat/history', methods=['GET'])
def api_chat_history():
    from flask_login import current_user
    if not current_user.is_authenticated:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        return jsonify({"history": load_history(user_id=current_user.id)})
    except Exception as e:
        return jsonify({"error": f"Server Error: {str(e)}"}), 500


# ── Legal text analysis ─────────────────────────────────────────────────

@module1.route('/analyze', methods=['POST'])
def api_analyze():
    try:
        data = request.json
        text = (data.get('message') or '').strip()
        if not text:
            return jsonify({"error": "Empty text"}), 400
        return jsonify({"response": ChatService.analyze_text(text)})
    except Exception as e:
        return jsonify({"error": f"Server Error: {str(e)}"}), 500


# ── Static reference endpoints ──────────────────────────────────────────

@module1.route('/guidelines', methods=['GET'])
def api_guidelines():
    return jsonify({"guidelines": get_all_guidelines()})


@module1.route('/legal-references', methods=['GET'])
def api_legal_references():
    return jsonify({"references": get_all_legal_references()})


# ── AI vision (image analysis) ─────────────────────────────────────────

@module1.route('/analyze-image', methods=['POST'])
def api_analyze_image():
    try:
        data = request.json
        base64_image = data.get('image', '')
        if not base64_image:
            return jsonify({"error": "No image provided"}), 400

        if "," in base64_image:
            base64_image = base64_image.split(",", 1)[-1]

        return jsonify({"response": ChatService.analyze_image(base64_image)})

    except Exception as e:
        return jsonify({"error": f"Server Error: {str(e)}"}), 500


# ── PDF analysis ────────────────────────────────────────────────────────

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

        return jsonify({"response": ChatService.analyze_pdf(pdf_file.read())})

    except Exception as e:
        return jsonify({"error": f"Server Error: {str(e)}"}), 500


# ── Formal Notice persistence ───────────────────────────────────────────

@module1.route('/save-formal-notice', methods=['POST'])
def api_save_formal_notice():
    from flask_login import current_user
    if not current_user.is_authenticated:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        data = request.get_json(silent=True) or {}
        notice = NoticeService.save_notice(current_user, data)
        return jsonify({"status": "ok", "notice_id": notice.id}), 201

    except Exception as e:
        from ..extensions import db
        db.session.rollback()
        return jsonify({"error": f"Server Error: {str(e)}"}), 500
