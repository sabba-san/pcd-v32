import io
import os

import pypdf
from groq import Groq

from .dlp_knowledge_base import load_pdf_knowledge

_chatbot_client = None


def _sanitize_api_key(raw_value):
    return (raw_value or "").strip().strip('"').strip("'").strip()


def _get_chatbot_api_key():
    return _sanitize_api_key(
        os.getenv("GROQ_API_KEY_CHATBOT") or os.getenv("GROQ_API_KEY") or
        os.getenv("LLM_API_KEY_CHATBOT") or os.getenv("LLM_API_KEY")
    )


def get_chatbot_client():
    global _chatbot_client

    if _chatbot_client is not None:
        return _chatbot_client

    api_key = _get_chatbot_api_key()
    if not api_key:
        return None

    try:
        _chatbot_client = Groq(api_key=api_key)
    except Exception as e:
        import logging
        logging.error(f"Groq Initialization Error: {e}")
        _chatbot_client = None

    return _chatbot_client

# Load the PDF text when the app starts
PDF_CONTEXT = load_pdf_knowledge()

# ---------------------------------------------------------------------------
# Retrieval helper — keyword-based top-N paragraph selector
# ---------------------------------------------------------------------------
DEFAULT_CHUNK_SIZE = 400   # characters per paragraph chunk
TOP_K_CHUNKS = 3            # number of most-relevant chunks to pass to LLM

def _retrieve_relevant_context(query: str, full_text: str,
                               top_k: int = TOP_K_CHUNKS,
                               chunk_size: int = DEFAULT_CHUNK_SIZE) -> str:
    """Split the corpus into fixed-size paragraphs and return the top-k chunks
    ranked by the number of query keywords they contain.  This keeps the
    context payload small and focused rather than dumping the full PDF."""
    if not full_text:
        return "No legal documents available."

    # Tokenise the query into meaningful keywords (≥ 3 chars)
    keywords = [w.lower() for w in query.split() if len(w) >= 3]

    # Split corpus into overlapping chunks
    chunks = []
    for i in range(0, len(full_text), chunk_size // 2):
        chunk = full_text[i : i + chunk_size].strip()
        if chunk:
            chunks.append(chunk)

    if not chunks:
        return "No legal documents available."

    if not keywords:
        # No useful keywords — return the very first chunks as fallback
        return "\n\n".join(chunks[:top_k])

    # Score each chunk by keyword hits
    scored = []
    for chunk in chunks:
        lower_chunk = chunk.lower()
        score = sum(lower_chunk.count(kw) for kw in keywords)
        scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_chunks = [c for _, c in scored[:top_k]]
    return "\n\n".join(top_chunks)


def process_query(user_query):
    client = get_chatbot_client()
    if not client:
        return "Error: AI Client not initialized. Check your API key."

    # 1. INSTANT GREETING INTERCEPTOR (Saves API calls and responds instantly)
    clean_message = user_query.lower().strip()
    basic_greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon',
                       'good evening', 'hi there', 'hello there', 'who are you', 'how are you']

    if clean_message in basic_greetings:
        return ("Hello! I am your Superchat Legal Assistant. I can help you understand your "
                "Defect Liability Period (DLP), review your SPA clauses, or calculate your "
                "claim timelines. How can I help you today?")

    # 2. OPTIMISED RETRIEVAL — top-3 relevant paragraphs only (~1,200 chars max)
    safe_context = _retrieve_relevant_context(user_query, PDF_CONTEXT)

    # 2.5 CONTEXT-AWARE INJECTION
    user_context_str = ""
    try:
        from flask_login import current_user
        from app.models import Defect
        
        if current_user and current_user.is_authenticated:
            user_context_str = f"\n\nCURRENT USER DATA:\nUser Profile: Name={current_user.full_name}, Role={current_user.user_type}. "
            
            if current_user.user_type == 'homeowner':
                defects = Defect.query.filter_by(user_id=current_user.id).all()
            elif current_user.user_type == 'developer':
                defects = Defect.query.filter_by(assigned_developer_id=current_user.id).all()
            elif current_user.user_type == 'lawyer':
                defects = Defect.query.filter_by(assigned_lawyer_id=current_user.id).all()
            else:
                defects = Defect.query.filter_by(user_id=current_user.id).all()
            
            if defects:
                for d in defects:
                    desc = d.description or d.defect_type or "No description"
                    user_context_str += f"Defect #{d.id}: {desc}, Status: {d.status}, Severity: {d.severity}. "
            else:
                user_context_str += "The user currently has no reported defects."
                
            user_context_str += "\nInstruction: If the user asks about their specific case or defects, use the CURRENT USER DATA above to provide a personalized assessment based on the Malaysian Property Law context provided."
    except Exception as e:
        import logging
        logging.error(f"Error injecting user context: {e}")

    # 3. OPTIMISED SYSTEM PROMPT — broader intelligence, still property-focused
    system_prompt = (
        "You are a knowledgeable AI Legal and Property Advisor for Malaysia. "
        "Your primary expertise is the Defect Liability Period (DLP) and Housing Development Act (HDA). "
        "However, you possess broad general knowledge. "
        "If the user asks general questions, answer them intelligently, politely, and naturally. "
        "You don't have to force every conversation back to property, but maintain a helpful and professional tone. "
        "For property and legal topics: Answer accurately using the provided Document Text when relevant. "
        "Be CONCISE and DIRECT to the point. "
        "Keep responses under 3 short paragraphs unless explicitly asked for a detailed explanation. "
        "For legal questions related to Malaysian property law, end every response with: "
        "'This is not legal advice. Please consult a qualified lawyer.' "
        "If the Document Text does not contain the answer to a property/legal question, reply: "
        "'I don't have sufficient information from the uploaded legal documents to answer this.'"
        f"{user_context_str}"
    )

    user_content = f"Document Text:\n{safe_context}\n\nUser Question: {user_query}"

    try:
        # 4. max_tokens=300 caps output length → faster responses
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_content},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            max_tokens=300,
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"AI Error: {str(e)}"
        
def analyze_legal_text(document_text):
    client = get_chatbot_client()
    if not client: return "Error: AI Client not initialized."
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": f"Analyze this legal text briefly:\n\n{document_text}"}],
            model="llama-3.3-70b-versatile",
            temperature=0.1
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Analysis Error: {str(e)}"

def analyze_defect_image(base64_image):
    """Sends an image to Groq's Vision Model for defect analysis."""
    client = get_chatbot_client()
    if not client: return "Error: AI Client not initialized."
    
    prompt = """You are examining a photo of a potential property defect in Malaysia.
    1. Describe in detail what you see in the image (location, type of damage, severity, materials affected).
    2. Classify the visible issue: hairline crack / structural crack / water stain / tile hollow / peeling paint / leaking / uneven surface / other.
    3. Estimate approximate severity: minor / moderate / serious.
    4. Based on Malaysian Housing Development Act and common DLP practice:
       - Is this the type of defect that is USUALLY covered during the 24-month Defect Liability Period?
       - Give short reasoning using typical DLP rules.
    5. Suggest next steps for the user.
    Image description task only — do not give definitive legal ruling."""

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            temperature=0.1
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"Vision AI Error: {str(e)}"

def analyze_pdf_document(pdf_bytes):
    """Extracts text from a PDF and sends it to Groq for legal summarization."""
    client = get_chatbot_client()
    if not client: return "Error: AI Client not initialized."
    
    try:
        # 1. Read the PDF
        pdf_file = io.BytesIO(pdf_bytes)
        reader = pypdf.PdfReader(pdf_file)
        extracted_text = ""
        
        for page in reader.pages:
            text = page.extract_text()
            if text:
                extracted_text += text + "\n"
        
        if not extracted_text.strip():
            return "Error: Could not read text from this PDF. It might be a scanned image rather than a text document."

        # 2. Limit text size for the AI (first 30,000 characters)
        safe_text = extracted_text[:30000]

        # 3. Create the legal summarization prompt
        prompt = f"""You are a specialized legal assistant for Malaysian Property Law.
        Please read the following extracted text from a user's uploaded legal document (like an SPA or Defect Report).
        
        1. Provide a clear, structured summary of the document.
        2. Highlight any key clauses related to the Defect Liability Period (DLP), warranties, or property conditions.
        3. Identify any immediate red flags, deadlines, or actionable steps for the buyer.
        
        Document Text:
        {safe_text}
        """

        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            temperature=0.1
        )
        return chat_completion.choices[0].message.content
        
    except Exception as e:
        return f"PDF Analysis Error: {str(e)}"

        
