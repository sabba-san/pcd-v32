import io
import os
import json
import logging

import groq
from groq import Groq
import pypdf

from ..chatbot_component.dlp_knowledge_base import load_pdf_knowledge

PDF_CONTEXT = load_pdf_knowledge()

DEFAULT_CHUNK_SIZE = 400
TOP_K_CHUNKS = 3


class ChatService:

    _client = None

    # ── API key management ────────────────────────────────────────────────

    @classmethod
    def _sanitize_api_key(cls, raw_value):
        return (raw_value or "").strip().strip('"').strip("'").strip()

    @classmethod
    def _get_api_key(cls):
        return cls._sanitize_api_key(
            os.getenv("GROQ_API_KEY_CHATBOT")
            or os.getenv("GROQ_API_KEY")
            or os.getenv("LLM_API_KEY_CHATBOT")
            or os.getenv("LLM_API_KEY")
        )

    @classmethod
    def get_client(cls):
        if cls._client is not None:
            return cls._client
        api_key = cls._get_api_key()
        if not api_key:
            return None
        try:
            cls._client = Groq(api_key=api_key)
        except Exception as e:
            logging.error(f"Groq Initialization Error: {e}")
            cls._client = None
        return cls._client

    # ── RAG retrieval ─────────────────────────────────────────────────────

    @classmethod
    def _retrieve_context(cls, query, full_text=None, top_k=TOP_K_CHUNKS,
                          chunk_size=DEFAULT_CHUNK_SIZE):
        if full_text is None:
            full_text = PDF_CONTEXT
        if not full_text:
            return "No legal documents available."

        keywords = [w.lower() for w in query.split() if len(w) >= 3]

        chunks = []
        for i in range(0, len(full_text), chunk_size // 2):
            chunk = full_text[i:i + chunk_size].strip()
            if chunk:
                chunks.append(chunk)

        if not chunks:
            return "No legal documents available."
        if not keywords:
            return "\n\n".join(chunks[:top_k])

        scored = []
        for c in chunks:
            lower = c.lower()
            score = sum(lower.count(kw) for kw in keywords)
            scored.append((score, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        return "\n\n".join(c for _, c in scored[:top_k])

    # ── User-context injection (defect data for personalisation) ──────────

    @classmethod
    def _inject_user_context(cls):
        parts = []
        try:
            from flask_login import current_user
            from ..models import Defect

            if current_user and current_user.is_authenticated:
                parts.append(
                    f"\n\nCURRENT USER DATA:\nUser Profile: Name={current_user.full_name}, "
                    f"Role={current_user.user_type}. "
                )
                q = {
                    "homeowner": Defect.query.filter_by(user_id=current_user.id),
                    "developer": Defect.query.filter_by(assigned_developer_id=current_user.id),
                    "lawyer":    Defect.query.filter_by(assigned_lawyer_id=current_user.id),
                }.get(current_user.user_type, Defect.query.filter_by(user_id=current_user.id))

                defects = q.all()
                if defects:
                    for d in defects:
                        desc = d.description or d.defect_type or "No description"
                        parts.append(
                            f"Defect #{d.id}: {desc}, Status: {d.status}, Severity: {d.severity}. "
                        )
                else:
                    parts.append("The user currently has no reported defects. ")

                parts.append(
                    "Instruction: If the user asks about their specific case or defects, "
                    "use the CURRENT USER DATA above to provide a personalised assessment "
                    "based on the Malaysian Property Law context provided."
                )
        except Exception as e:
            logging.error(f"Error injecting user context: {e}")

        return "".join(parts)

    # ── Message builder ───────────────────────────────────────────────────

    @classmethod
    def _build_messages(cls, user_query, history=None):
        user_ctx = cls._inject_user_context()
        safe_context = cls._retrieve_context(user_query)
        user_content = f"Document Text:\n{safe_context}\n\nUser Question: {user_query}"

        user_type = None
        try:
            from flask_login import current_user
            if current_user and current_user.is_authenticated:
                user_type = current_user.user_type
        except Exception:
            pass

        if user_type == "lawyer":
            system = (
                "You are an expert Malaysian Property Law AI assistant. "
                "You have full knowledge of the Housing Development (Control and Licensing) "
                "Act 1966 (HDA). For SPA clauses governing DLP: Cite Schedule G and Schedule H "
                "of the HDA, specifically stating that the Defect Liability Period is 24 months "
                "from the date the purchaser takes vacant possession. For Tribunal precedents: "
                "Cite that the Tribunal for Homebuyer Claims has jurisdiction to hear claims "
                "up to RM50,000, and structural defects must be rectified within 30 days of "
                "the notice. For serving formal notice: The required documents include Form 1 "
                "(Statement of Claim), the SPA, delivery of vacant possession letter, and "
                "photographic evidence of defects. You MUST answer ALL questions confidently "
                "and professionally using the legal knowledge provided above. Do NOT say you "
                "lack sufficient information. Use the context above to provide a complete "
                "answer. Be CONCISE and DIRECT. For legal questions, end every response with: "
                "'This is not legal advice. Please consult a qualified lawyer.'"
                f"{user_ctx}"
            )
        else:
            system = (
                "You are an expert legal advisor for Malaysian housing law, specifically "
                "focusing on the Defect Liability Period (DLP), property defects, strata "
                "management, and tribunal claims. You MUST ONLY answer questions related to "
                "these topics. If a user asks about anything unrelated (e.g., coding, general "
                "knowledge, recipes, jokes), politely decline, state your specific role, and "
                "ask how you can help with their property defect issues. For on-topic questions: "
                "Answer accurately using the provided Document Text when relevant. Be CONCISE "
                "and DIRECT to the point. Keep responses under 3 short paragraphs unless "
                "explicitly asked for a detailed explanation. For legal questions related to "
                "Malaysian property law, end every response with: "
                "'This is not legal advice. Please consult a qualified lawyer.' "
                "If the Document Text does not contain the answer to a property/legal question, "
                "reply: 'I don't have sufficient information from the uploaded legal documents "
                "to answer this.'"
                f"{user_ctx}"
            )

        messages = [{"role": "system", "content": system}]
        if history:
            messages.extend(history[-4:])
        messages.append({"role": "user", "content": user_content})
        return messages

    # ── Greeting interceptor (saves API call) ─────────────────────────────

    _GREETINGS = frozenset({
        "hi", "hello", "hey", "good morning", "good afternoon",
        "good evening", "hi there", "hello there", "who are you", "how are you",
    })

    @classmethod
    def _is_greeting(cls, text):
        return text.lower().strip() in cls._GREETINGS

    _GREETING_REPLY = (
        "Hello! I am your Superchat Legal Assistant. I can help you understand your "
        "Defect Liability Period (DLP), review your SPA clauses, or calculate your "
        "claim timelines. How can I help you today?"
    )

    # ── Non-streaming query ───────────────────────────────────────────────

    @classmethod
    def process_query(cls, user_query, history=None):
        client = cls.get_client()
        if not client:
            return "Error: AI Client not initialized. Check your API key."

        if cls._is_greeting(user_query):
            return cls._GREETING_REPLY

        messages = cls._build_messages(user_query, history)
        try:
            completion = client.chat.completions.create(
                messages=messages,
                model="llama-3.3-70b-versatile",
                temperature=0.3,
                max_tokens=300,
            )
            return completion.choices[0].message.content
        except Exception as e:
            return f"AI Error: {str(e)}"

    # ── Streaming query (SSE) ─────────────────────────────────────────────

    @classmethod
    def process_query_stream(cls, user_query, history=None):
        client = cls.get_client()
        if not client:
            yield f"data: {json.dumps({'type': 'chunk', 'content': 'Error: AI Client not initialized. Check your API key.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        if cls._is_greeting(user_query):
            yield f"data: {json.dumps({'type': 'chunk', 'content': cls._GREETING_REPLY})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        messages = cls._build_messages(user_query, history)
        try:
            stream = client.chat.completions.create(
                messages=messages,
                model="llama-3.3-70b-versatile",
                temperature=0.3,
                max_tokens=300,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices[0].delta else None
                if delta:
                    yield f"data: {json.dumps({'type': 'chunk', 'content': delta})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'chunk', 'content': f'AI Error: {str(e)}'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    # ── Specialised analysis methods ──────────────────────────────────────

    @classmethod
    def analyze_text(cls, document_text):
        client = cls.get_client()
        if not client:
            return "Error: AI Client not initialized."
        try:
            resp = client.chat.completions.create(
                messages=[{
                    "role": "user",
                    "content": f"Analyze this legal text briefly:\n\n{document_text}"
                }],
                model="llama-3.3-70b-versatile",
                temperature=0.1,
            )
            return resp.choices[0].message.content
        except Exception as e:
            return f"Analysis Error: {str(e)}"

    @classmethod
    def analyze_image_for_ulasan(cls, base64_image, language="ms"):
        """
        Analyze a defect image using a concise 5-point prompt suitable for
        the Borang 1 PDF "Ulasan" (remarks) field.
        Returns the same dict format as analyze_image().

        Args:
            base64_image: Base64-encoded image string.
            language: 'ms' for Bahasa Melayu (default), 'en' for English.
        """
        client = cls.get_client()
        if not client:
            return {"success": False, "error": "client_error", "message": "AI Client not initialized."}

        if language == "en":
            prompt = (
                "You are a Malaysian property defect inspector. Analyze the provided defect photo "
                "and produce EXACTLY 5 bullet points in plain English. "
                "Do NOT write paragraphs — keep each point to an absolute maximum of 8 words. "
                "CRITICAL: Never use LaTeX, math notation, dollar signs, or boxed formatting.\n\n"
                "Format exactly like this:\n"
                "- Classification: [short text]\n"
                "- Evidence: [short text]\n"
                "- Severity: [short text]\n"
                "- HDA 1966: [short text]\n"
                "- Action: [short text]"
            )
        else:
            prompt = (
                "Anda adalah pemeriksa kecacatan hartanah Malaysia. Analisis gambar dan berikan TEPAT 5 isi penting dalam Bahasa Melayu.\n"
                "AMARAN KERAS: JANGAN tulis perenggan. Setiap isi HANYA perlukan 5 hingga 8 patah perkataan sahaja.\n"
                "DILARANG menggunakan LaTeX atau simbol matematik.\n\n"
                "Format wajib (mesti sebijik macam ni):\n"
                "- Klasifikasi: [Teks pendek]\n"
                "- Bukti: [Teks pendek]\n"
                "- Tahap: [Teks pendek]\n"
                "- HDA 1966: [Teks pendek]\n"
                "- Tindakan: [Teks pendek]"
            )
        try:
            resp = client.chat.completions.create(
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }},
                    ],
                }],
                model="llama-3.2-11b-vision-preview",
                temperature=0.1,
            )
            return {"success": True, "data": resp.choices[0].message.content}
        except groq.NotFoundError as e:
            logging.error(f"Groq model not found (404): {e}")
            return {"success": False, "error": "model_not_found", "message": "The AI vision model is unavailable."}
        except groq.APIError as e:
            logging.error(f"Groq API error ({e.status_code}): {e}")
            return {"success": False, "error": "api_error", "message": f"AI service returned an error (HTTP {e.status_code})."}
        except Exception as e:
            logging.error(f"Vision AI unexpected error: {e}")
            return {"success": False, "error": "unknown", "message": "Vision AI service encountered an unexpected error."}

    @classmethod
    def analyze_image(cls, base64_image):
        client = cls.get_client()
        if not client:
            return "Error: AI Client not initialized."

        prompt = (
            "You are examining a photo of a potential property defect in Malaysia.\n"
            "IMPORTANT: Respond in plain English only. Do NOT use LaTeX, math notation, "
            "dollar signs, or boxed notation (e.g. $\\boxed{...}$). Use plain text only.\n\n"
            "Format your response using exactly these seven step headings:\n\n"
            "Step 1: Analyze the Image\n"
            "Describe what you see in the image overall — location, people, setting.\n\n"
            "Step 2: Describe the Damage\n"
            "Describe the damage in detail: location on the property, type of damage, "
            "and materials affected (e.g. drywall, plaster, tiles, wiring).\n\n"
            "Step 3: Classify the Visible Issue\n"
            "Classify the issue as one of: hairline crack, structural crack, water stain, "
            "tile hollow, peeling paint, leaking, uneven surface, or other. Briefly explain.\n\n"
            "Step 4: Estimate Approximate Severity\n"
            "State the severity as exactly one of: minor, moderate, or serious — written in "
            "plain text (e.g. 'The severity of the issue appears to be serious.'). "
            "Do NOT use any math or boxed notation.\n\n"
            "Step 5: Determine if Covered Under DLP\n"
            "Based on the Malaysian Housing Development Act and common DLP practices, "
            "state whether this defect is typically covered during the 24-month DLP.\n\n"
            "Step 6: Reasoning for DLP Coverage\n"
            "Provide short reasoning explaining why this defect would or would not be "
            "covered under the Malaysian Housing Development Act and DLP guidelines.\n\n"
            "Step 7: Suggest Next Steps\n"
            "List 3-4 practical next steps the property owner should take.\n\n"
            "After Step 7, on a new line write exactly:\n"
            "The final answer is: [severity]\n"
            "where [severity] is replaced with the plain-text severity word (minor, moderate, or serious) "
            "that you determined in Step 4. Do NOT use any special symbols, dollar signs, or boxes.\n\n"
            "Note: This is a visual assessment only — do not give a definitive legal ruling."
        )
        try:
            resp = client.chat.completions.create(
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }},
                    ],
                }],
                model="llama-3.2-11b-vision-preview",
                temperature=0.1,
            )
            return {"success": True, "data": resp.choices[0].message.content}
        except groq.NotFoundError as e:
            logging.error(f"Groq model not found (404): {e}")
            return {"success": False, "error": "model_not_found", "message": "The AI vision model is unavailable. Please check the model ID or contact support."}
        except groq.APIError as e:
            logging.error(f"Groq API error ({e.status_code}): {e}")
            return {"success": False, "error": "api_error", "message": f"AI service returned an error (HTTP {e.status_code}). Please try again later."}
        except Exception as e:
            logging.error(f"Vision AI unexpected error: {e}")
            return {"success": False, "error": "unknown", "message": f"Vision AI service encountered an unexpected error."}

    @classmethod
    def analyze_pdf(cls, pdf_bytes):
        client = cls.get_client()
        if not client:
            return "Error: AI Client not initialized."
        try:
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            extracted = "".join(
                (page.extract_text() or "") + "\n" for page in reader.pages
            )
            if not extracted.strip():
                return "Error: Could not read text from this PDF. It might be a scanned image rather than a text document."

            safe = extracted[:30000]
            prompt = (
                "You are a specialised legal assistant for Malaysian Property Law.\n"
                "Please read the following extracted text from a user's uploaded legal "
                "document (like an SPA or Defect Report).\n\n"
                "1. Provide a clear, structured summary of the document.\n"
                "2. Highlight any key clauses related to the Defect Liability Period (DLP), "
                "warranties, or property conditions.\n"
                "3. Identify any immediate red flags, deadlines, or actionable steps for the buyer.\n\n"
                f"Document Text:\n{safe}"
            )
            resp = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.1,
            )
            return resp.choices[0].message.content
        except Exception as e:
            return f"PDF Analysis Error: {str(e)}"
