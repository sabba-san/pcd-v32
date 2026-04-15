from groq import Groq
from .dlp_knowledge_base import load_pdf_knowledge
import pypdf
import io

# ⚠️ Paste your actual Groq API key here
GROQ_API_KEY = "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"

try:
    client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    print(f"Groq Initialization Error: {e}")
    client = None

# Load the PDF text when the app starts
PDF_CONTEXT = load_pdf_knowledge()

def process_query(user_query):
    if not client:
        return "Error: AI Client not initialized. Check your API key."

    # 1. INSTANT GREETING INTERCEPTOR (Saves API calls and responds instantly)
    clean_message = user_query.lower().strip()
    basic_greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening', 'hi there', 'hello there', 'who are you', 'how are you']
    
    if clean_message in basic_greetings:
        return "Hello! I am your Superchat Legal Assistant. I can help you understand your Defect Liability Period (DLP), review your SPA clauses, or calculate your claim timelines. How can I help you today?"

    # Groq's Llama model can read huge amounts of text. 
    # We pass the first 50,000 characters to keep it fast and safe.
    safe_context = PDF_CONTEXT[:50000] if PDF_CONTEXT else "No documents available."

    # 2. UPDATED SYSTEM PROMPT
    prompt = f"""You are 'Superchat', a specialized legal assistant for Malaysian Property Law.
    Read the following official legal documents carefully.
    
    Rules for responding:
    1. If the user is just making small talk, reply politely and concisely, then offer to help with property law. Do NOT append the legal disclaimer for basic small talk.
    2. For property law questions, answer using ONLY the provided Document Text.
    3. If it is a legal question and the Document Text does not contain the answer, strictly reply: "I don't have sufficient information from the uploaded legal documents to answer this."
    4. End every legal-related response with: "This is not legal advice. Please consult a qualified lawyer."

    Document Text:
    {safe_context}
    
    User Question: {user_query}
    """

    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.3 # Slightly higher temperature allows for a more natural conversation
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"AI Error: {str(e)}"
        
def analyze_legal_text(document_text):
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

        