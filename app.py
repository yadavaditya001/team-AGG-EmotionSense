import json
import os
import uuid
import datetime
import requests
from flask import Flask, render_template, request, jsonify

# ─────────────────────────────────────────────────────────────────────────────
# Flask App & Database Configuration
# ─────────────────────────────────────────────────────────────────────────────
app = Flask(__name__)

GROQ_API_KEY = "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"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "llama-3.1-8b-instant"

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "student_reports.json")

def load_db():
    if not os.path.exists(DB_FILE):
        return []
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_db(data):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        print(f"Error saving DB: {exc}")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")



# ─────────────────────────────────────────────────────────────────────────────
# /api/chat  — Structured interview counselor reply
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/chat", methods=["POST"])
def api_chat():
    payload   = request.get_json(force=True) or {}
    user_text = payload.get("text", "").strip()
    emotion   = payload.get("emotion", "neutral").strip() or "neutral"
    history   = payload.get("history", [])
    lang      = payload.get("lang", "en").strip().lower()

    if not user_text:
        return jsonify({"error": "No text provided"}), 400

    language_instruction = ""
    if lang == "hi":
        language_instruction = """
• CONDUCT THE ENTIRE SESSION IN HINDI.
• You must write and respond ONLY in clear, conversational, and warm Hindi (Devanagari script).
• Keep your sentence structure simple and easy to understand out loud.
• If the user's name is requested, ask for it in Hindi: "क्या आप मुझे अपना नाम बता सकते हैं?"
"""
    else:
        language_instruction = """
• CONDUCT THE SESSION IN ENGLISH.
• If the user speaks or replies in Hindi, you can respond in Hindi. Otherwise, default to English.
"""

    system_prompt = f"""You are Aura, a warm and empathetic AI video-call wellness counselor at IIBM (Indian Institute of Business Management) Patna. You conduct structured mental health check-in sessions and look like a real human counselor on a video call.

YOUR PERSONALITY: Caring, gentle, professional, non-judgmental — like a trusted friend who is also a trained counselor.

──────────────────────────────────────────────
LANGUAGE RULE:
{language_instruction}
──────────────────────────────────────────────

──────────────────────────────────────────────
STRUCTURED INTERVIEW PROTOCOL (follow in order)
──────────────────────────────────────────────

PHASE 1 — INTRODUCTION:
→ Warmly introduce yourself as Aura and ask for their name.

PHASE 2 — DEMOGRAPHICS:
→ Use their name warmly. Ask their age.
→ Ask where they are from / their city or college.

PHASE 3 — GENERAL WELLBEING:
→ Ask: "How have you been feeling emotionally lately, [Name]?" (or translate to Hindi if session is in Hindi)

PHASE 4 — MENTAL HEALTH SCREENING (cover each topic naturally, one per turn):
→ SLEEP:        How is their sleep? Too little, too much, disturbed?
→ MOOD:         Do they feel sad, empty, low, or hopeless often?
→ INTEREST:     Have they lost interest in things they used to enjoy?
→ ENERGY:       Do they feel tired or drained most of the time?
→ FOCUS:        Is it hard to concentrate on studies or daily tasks?
→ SOCIAL:       Do they feel lonely, isolated, or disconnected from friends?
→ ANXIETY:      Do they feel frequently worried, stressed, or overwhelmed?
→ SELF-WORTH:   How do they feel about themselves lately?

PHASE 5 — WRAP UP (after covering at least 5 mental health topics):
→ Say EXACTLY (fill in real name, or translate to Hindi): "Thank you so much for sharing with me today, [Name]. I now have everything I need to prepare your personalized wellness report." (Hindi translation: "मेरे साथ बातचीत करने के लिए बहुत-बहुत धन्यवाद, [Name]। अब मेरे पास आपकी वेलनेस रिपोर्ट तैयार करने के लिए पर्याप्त जानकारी है।")

──────────────────────────────────────────────
STRICT RULES
──────────────────────────────────────────────
• Respond with ONE SHORT sentence. Two sentences maximum.
• Sound completely natural — like a real video call with a friend-counselor.
• NEVER use clinical terms: no "depression", "disorder", "DSM", "diagnosis".
• NEVER repeat a question already asked (check conversation history).
• Use the user's first name occasionally once you know it.
• The user's current facial emotion detected by webcam: {emotion.upper()}.
  If they look sad/fearful/disgusted, be extra gentle and validate their feelings first.
• Progress naturally — do NOT jump between topics randomly."""

    messages = [{"role": "system", "content": system_prompt}]
    for turn in history[-18:]:
        if turn.get("role") in ("user", "assistant") and turn.get("content"):
            messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": user_text})

    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    body    = {"model": GROQ_MODEL, "messages": messages, "temperature": 0.82, "max_tokens": 110}

    try:
        resp  = requests.post(GROQ_API_URL, headers=headers, json=body, timeout=20)
        resp.raise_for_status()
        reply = resp.json()["choices"][0]["message"]["content"].strip()
        reply = reply.replace("*", "").replace("#", "").replace("_", "").strip()

        # Signal to the frontend that the structured interview is complete
        is_complete = (
            "personalized wellness report" in reply.lower() or
            "wellness report" in reply.lower() or
            "वेलनेस रिपोर्ट" in reply or
            "पर्याप्त जानकारी है" in reply
        )

        return jsonify({"reply": reply, "session_complete": is_complete})
    except requests.Timeout:
        return jsonify({"error": "Request timed out"}), 504
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


# ─────────────────────────────────────────────────────────────────────────────
# /api/report  — Full analysis with database persistence & speech metrics
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/report", methods=["POST"])
def api_report():
    payload        = request.get_json(force=True) or {}
    transcript     = payload.get("transcript",  [])
    emotion_log    = payload.get("emotion_log", [])
    speech_metrics = payload.get("speech_metrics", {})
    lang           = payload.get("lang", "en")

    transcript_str = "\n".join(
        f"{t.get('role','user').upper()}: {t.get('text','')}"
        for t in transcript
    ) or "No conversation was recorded."

    seen, unique_emotions = set(), []
    for e in emotion_log:
        em = e.get("emotion", "neutral")
        if em not in seen:
            seen.add(em)
            unique_emotions.append(em)
    emotion_str = ", ".join(unique_emotions) if unique_emotions else "neutral"

    avg_wpm = speech_metrics.get("avg_wpm", 0)
    hesitations = speech_metrics.get("hesitations", 0)
    avg_volume = speech_metrics.get("avg_volume", 50)
    total_duration = speech_metrics.get("total_duration", 0)

    system_prompt = """You are a compassionate AI mental health analyst. Carefully analyze this student wellness screening session.

Return ONLY a valid JSON object — no markdown, no backticks, no extra text. Use exactly these keys:
{
  "overall_status": "Healthy" or "Moderate Concern" or "High Concern",
  "severity_score": integer 0-10 (0=very healthy, 10=severe distress),
  "user_name": "user's first name from transcript, or 'Friend'",
  "user_age": "user's age from transcript, or 'Unknown'",
  "user_location": "user's college, city, or location from transcript, or 'Unknown'",
  "mood_summary": "1-2 sentences on their overall emotional state during this session",
  "speech_analysis": "2-3 sentences about HOW they expressed themselves — comment on their vocabulary, openness, and also interpret the speech style metrics (speaking rate, hesitations, volume) and what they suggest about their mental health state.",
  "face_analysis": "2-3 sentences about WHAT their facial expressions revealed — the emotions detected and what they suggest about inner state",
  "key_concerns": ["array", "of", "specific", "concerns", "mentioned", "or", "empty", "array"],
  "positive_factors": ["strengths", "or", "positive", "coping", "signs", "observed", "or", "empty", "array"],
  "user_friendly_summary": "4-5 warm, comforting sentences written DIRECTLY to the user (second person). Simple everyday language, no medical terms. Validate feelings, highlight strengths, give realistic hope.",
  "needs_professional_help": true or false,
  "professional_recommendation": "If needs_professional_help is true: 2-3 warm, encouraging sentences explaining why talking to a professional would help right now. If false: 1-2 uplifting sentences encouraging continued self-care."
}

Set needs_professional_help = true if:
- severity_score >= 5, OR
- transcript mentions self-harm, hopelessness, suicidal thoughts, OR
- multiple mental health domains show significant distress"""

    user_prompt = (
        f"WELLNESS SESSION TRANSCRIPT:\n{transcript_str}\n\n"
        f"FACIAL EMOTIONS DETECTED DURING SESSION: {emotion_str}\n\n"
        f"SPEECH STYLE METRICS CAPTURED DURING SESSION:\n"
        f"- Average Speaking Rate: {avg_wpm:.1f} Words Per Minute (WPM) [Typical normal conversation is 110-150 WPM]\n"
        f"- Total Hesitations (um, uh, er, like): {hesitations} occurrences\n"
        f"- Average Vocal Volume: {avg_volume:.1f}/100 (where <30 is soft/whisper, 30-70 is normal, >70 is loud)\n"
        f"- Total Speaking Duration: {total_duration:.1f} seconds\n\n"
        "Analyze and return the JSON report now."
    )

    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model":           GROQ_MODEL,
        "messages":        [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "temperature":     0.3,
        "max_tokens":      900,
        "response_format": {"type": "json_object"},
    }

    report_id = "rep_" + str(uuid.uuid4())[:8]
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        resp = requests.post(GROQ_API_URL, headers=headers, json=body, timeout=35)
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        if raw.startswith("```"):
            raw = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        
        # Inject server-side metadata
        result["id"] = report_id
        result["timestamp"] = timestamp
        result["language"] = lang
        result["transcript"] = transcript

        # Save to local database
        db = load_db()
        db.append(result)
        save_db(db)

        return jsonify(result)

    except Exception as exc:
        print(f"[/api/report ERROR] {exc}")
        # Graceful fallback — user always gets redirected
        fallback = {
            "id":                        report_id,
            "timestamp":                 timestamp,
            "language":                  lang,
            "transcript":                transcript,
            "user_name":                 "Friend",
            "user_age":                  "Unknown",
            "user_location":             "Unknown",
            "overall_status":            "Moderate Concern",
            "severity_score":            5,
            "mood_summary":              "The session reflected a mix of emotional experiences worth paying attention to.",
            "speech_analysis":           f"Spoke at {avg_wpm:.1f} WPM with {hesitations} hesitations. The way you expressed yourself suggested real emotional depth.",
            "face_analysis":             f"Your expressions during the session included {emotion_str} — authentic emotions that speak volumes about your inner experience.",
            "key_concerns":              ["Emotional wellbeing needs attention"],
            "positive_factors":          ["Reached out for support", "Engaged openly"],
            "user_friendly_summary":     "Thank you for taking this important step today — it shows real self-awareness and courage. Whatever you're feeling right now is valid and understandable. You don't have to carry this alone, and there are warm, caring people ready to support you. One conversation at a time, things can get better.",
            "needs_professional_help":   True,
            "professional_recommendation": "Based on what you've shared today, speaking with a professional counselor could make a meaningful difference in how you feel. They can offer tools and support that are personalized just for you — and it only takes one step to start.",
        }
        
        # Save fallback to local database
        db = load_db()
        db.append(fallback)
        save_db(db)

        return jsonify(fallback)


# ─────────────────────────────────────────────────────────────────────────────
# Counselor Dashboard API Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/counselor/reports", methods=["GET"])
def api_counselor_reports():
    return jsonify(load_db())


@app.route("/api/counselor/reports/<report_id>", methods=["GET"])
def api_counselor_report_detail(report_id):
    db = load_db()
    for report in db:
        if report.get("id") == report_id:
            return jsonify(report)
    return jsonify({"error": "Report not found"}), 404


@app.route("/counselor")
def counselor_dashboard():
    return render_template("counselor.html")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

