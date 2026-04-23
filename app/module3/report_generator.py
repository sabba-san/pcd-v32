# report_generator.py
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

try:
    from .groqai_client import get_ai_client
    from .prompts import build_prompt, get_language_config
except ImportError:  # pragma: no cover - fallback for direct execution from module3/
    from groqai_client import get_ai_client
    from prompts import build_prompt, get_language_config

def generate_ai_report(role, report_data, language="ms"):
    """
    Menjana laporan sokongan tribunal berasaskan data berstruktur
    Defect Liability Period (DLP) menggunakan bantuan AI.
    
    Generate tribunal support report based on structured data
    using AI assistance (Google Gemini).
    
    Args:
        role: "Homeowner", "Developer", or "Legal"
        report_data: Dictionary containing case information
        language: "ms" for Bahasa Malaysia, "en" for English
    """

    client = get_ai_client("report")
    lang_config = get_language_config(language)

    # Build tribunal-safe prompt with language support
    prompt = build_prompt(role, report_data, language)
    
    # Combine system instruction with user prompt
    full_prompt = f"""{lang_config["system_instruction"]}

{prompt}"""

    try:
        # Use Groq API with Llama model (fast and supports multilingual)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": lang_config["system_instruction"]
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0,
            max_tokens=4096
        )
        ai_text = response.choices[0].message.content

        if not ai_text:
            ai_text = (
                "This report is generated based on the records submitted. "
                "No further narrative is available for the Tribunal’s consideration."
            )

    except Exception as e:
        error_msg = str(e)
        if "quota" in error_msg.lower() or "429" in error_msg or "rate" in error_msg.lower():
            raise Exception(
                "Groq API rate limit reached. Please try again in a moment."
            )
        elif "401" in error_msg or "invalid" in error_msg.lower() or "api_key" in error_msg.lower():
            raise Exception(
                "Invalid Groq API key. Please check your API key configuration."
            )
        else:
            raise Exception(f"Groq AI API error: {error_msg}")

    # Format date based on configured application timezone.
    app_timezone = os.getenv("APP_TIMEZONE", "Asia/Kuala_Lumpur")
    try:
        now = datetime.now(ZoneInfo(app_timezone))
    except Exception:
        if app_timezone == "Asia/Kuala_Lumpur":
            now = datetime.now(timezone.utc) + timedelta(hours=8)
        else:
            now = datetime.now()
    if language == "ms":
        # Bahasa Malaysia month names
        bulan_bm = {
            1: "Januari", 2: "Februari", 3: "Mac", 4: "April",
            5: "Mei", 6: "Jun", 7: "Julai", 8: "Ogos",
            9: "September", 10: "Oktober", 11: "November", 12: "Disember"
        }
        date_str = f"{now.day:02d} {bulan_bm[now.month]} {now.year}, {now.strftime('%H:%M')}"
    else:
        date_str = now.strftime('%d %B %Y, %H:%M')
    
    return f"""
{lang_config["report_title"]}
{lang_config["generated_label"]}: {date_str}

{ai_text}
""".strip()
