"""
Flask Application for Computing History Agent Client.

This is the main Flask application that provides a web interface
for interacting with the Computing History agent.
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
import markdown
import bleach
from agent_client import AgentClient
from speech_client import synthesize_text_to_wav
import json
import os

app = Flask(__name__, static_folder='static', template_folder='templates')

ALLOWED_CATEGORIES = {
    'daily life': 'Vida diaria',
    'shopping': 'Compras',
    'food': 'Comida',
    'travel': 'Viajes',
    'education': 'Educación'
}
MAX_CHAT_MESSAGE_LENGTH = 10000
MAX_TTS_TEXT_LENGTH = 2000
MAX_FIELD_LENGTH = 200


@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' https://cdn.jsdelivr.net; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self';"
    )
    return response


def _set_external_link_attributes(attrs, new=False):
    """Force safe external link attributes for rendered markdown links."""
    href_key = (None, 'href')
    href_value = attrs.get(href_key, '')
    if isinstance(href_value, str) and href_value.startswith(('http://', 'https://')):
        attrs[(None, 'target')] = '_blank'
        attrs[(None, 'rel')] = 'noopener noreferrer nofollow'
    return attrs


def render_markdown_to_safe_html(text: str) -> str:
    """Convert markdown to safe HTML for display in chat bubbles."""
    raw_html = markdown.markdown(
        text,
        extensions=['extra', 'sane_lists', 'nl2br']
    )

    allowed_tags = [
        'p', 'br', 'hr', 'blockquote',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'ul', 'ol', 'li',
        'strong', 'em', 'code', 'pre',
        'a',
        'table', 'thead', 'tbody', 'tr', 'th', 'td'
    ]
    allowed_attrs = {
        'a': ['href', 'title', 'target', 'rel'],
        'code': ['class']
    }

    safe_html = bleach.clean(
        raw_html,
        tags=allowed_tags,
        attributes=allowed_attrs,
        protocols=['http', 'https', 'mailto'],
        strip=True
    )

    # Linkify plain URLs while leaving code blocks untouched.
    safe_html = bleach.linkify(
        safe_html,
        skip_tags=['pre', 'code'],
        callbacks=[_set_external_link_attributes]
    )
    return safe_html

# Initialize the agent client
try:
    agent = AgentClient()
except Exception as e:
    print(f"Warning: Failed to initialize agent client: {e}")
    agent = None

@app.route('/')
def index():
    """Render the main chat interface."""
    return render_template('index.html')


@app.route('/generate_text', methods=['POST'])
def generate_text():
    """Generate a lesson text based on a selected category and options.

    Expects JSON: { "category": "daily life", "situation": "asking for help", "role": "tourist", "emotion": "urgency" }
    Returns structured JSON produced by the agent.
    """
    if not agent:
        return jsonify({'error': 'Agent client not initialized.'}), 500

    if not request.is_json:
        return jsonify({'error': 'Expected application/json content type.'}), 400

    data = request.get_json(silent=True) or {}
    category = str(data.get('category', 'daily life')).strip().lower()
    if category not in ALLOWED_CATEGORIES:
        return jsonify({'error': 'Invalid category.'}), 400

    situation = str(data.get('situation', 'general')).strip()
    role = str(data.get('role', 'learner')).strip()
    emotion = str(data.get('emotion', 'neutral')).strip()

    if len(situation) > MAX_FIELD_LENGTH or len(role) > MAX_FIELD_LENGTH or len(emotion) > MAX_FIELD_LENGTH:
        return jsonify({'error': 'Payload fields exceed allowed length.'}), 400

    prompt = (
        "You are a precise English pronunciation tutor. Follow a multi-step process: "
        "(1) determine the category and scenario, "
        "(2) compose a natural English sentence or short dialogue, "
        "(3) derive a Spanish-friendly pronunciation adaptation, "
        "(4) choose the most relevant pronunciation techniques and character spans, "
        "(5) return only a single valid JSON object with the required fields. "
        f"Generate a short English sentence or short dialogue for category '{category}'. "
        f"Context: situation={situation}, role={role}, emotion={emotion}. "
        "Return only a single JSON object with keys: original_text (English sentence/dialogue), "
        "interlinear (array of [English, Spanish_adaptation] pairs), "
        "highlights (array of {word, technique, color, start, end}). "
        "The Spanish_adaptation should be a pronunciation-friendly adaptation for Spanish speakers, not a literal translation. "
        "For example, enough should be written as i-NAF. "
        "Do not add a separate Spanish translation line or any text outside the JSON object. "
        "Use British English pronunciation patterns and focus on linking, blending, assimilation, and reductions. "
        "Keep the JSON minimal and valid."
    )

    try:
        response = agent.send_prompt(prompt, add_to_history=False)
        parsed = parse_agent_json_response(response)
        if isinstance(parsed, dict):
            if validate_agent_payload(parsed):
                return jsonify({'ok': True, 'data': parsed})
            return jsonify({'error': 'Agent output did not match expected schema.'}), 500

        return jsonify({'ok': True, 'data': {'original_text': response}})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def parse_agent_json_response(response_text: str):
    """Try to extract a valid JSON object from the agent response."""
    if not isinstance(response_text, str):
        return None

    response_text = response_text.strip()
    if not response_text:
        return None

    try:
        return json.loads(response_text)
    except Exception:
        pass

    # Remove markdown fences or extra wrappers and attempt to parse JSON again.
    cleaned = response_text
    cleaned = cleaned.replace('```json', '{').replace('```', '}')
    cleaned = cleaned.strip()

    start = cleaned.find('{')
    end = cleaned.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except Exception:
            pass

    return None


def validate_agent_payload(payload):
    """Verify the agent payload contains the expected fields and structure."""
    if not isinstance(payload, dict):
        return False

    if not payload.get('original_text') or not isinstance(payload['original_text'], str):
        return False

    interlinear = payload.get('interlinear', [])
    if interlinear is not None:
        if not isinstance(interlinear, list):
            return False
        for item in interlinear:
            if not isinstance(item, list) or len(item) != 2:
                return False
            if not all(isinstance(value, str) for value in item):
                return False

    highlights = payload.get('highlights', [])
    if highlights is not None:
        if not isinstance(highlights, list):
            return False
        for item in highlights:
            if not isinstance(item, dict):
                return False
            if 'word' not in item or 'technique' not in item:
                return False
            if 'start' in item:
                try:
                    int(item['start'])
                except Exception:
                    return False
            if 'end' in item:
                try:
                    int(item['end'])
                except Exception:
                    return False

    return True


@app.route('/synthesize_audio', methods=['POST'])
def synthesize_audio():
    """Synthesize provided text to audio and return a URL to the audio file."""
    if not request.is_json:
        return jsonify({'error': 'Expected application/json content type.'}), 400

    data = request.get_json(silent=True) or {}
    text = str(data.get('text', '')).strip()
    if not text:
        return jsonify({'error': 'Text is required'}), 400

    if len(text) > MAX_TTS_TEXT_LENGTH:
        return jsonify({'error': f'Text too long for TTS (max {MAX_TTS_TEXT_LENGTH} characters).'}), 400

    try:
        audio_url = synthesize_text_to_wav(text)
        return jsonify({'ok': True, 'audio_url': audio_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages from the user."""
    if not agent:
        return jsonify({
            'error': 'Agent client not initialized. Check your .env configuration.'
        }), 500
    
    if not request.is_json:
        return jsonify({'error': 'Expected application/json content type.'}), 400

    data = request.get_json(silent=True) or {}
    user_message = str(data.get('message', '')).strip()
    
    if not user_message:
        return jsonify({'error': 'Message is required'}), 400
    
    # Validate message length to prevent abuse
    if len(user_message) > MAX_CHAT_MESSAGE_LENGTH:
        return jsonify({'error': 'Message too long'}), 400
    
    # Note: We do NOT escape HTML here because:
    # 1. The agent needs to receive the raw text to understand it properly
    # 2. HTML escaping is performed on the frontend when displaying messages
    # 3. This follows the principle: escape at the point of use (display), not at input
    response = agent.send_message(user_message)
    response_html = render_markdown_to_safe_html(response)

    return jsonify({
        'response': response,
        'response_html': response_html
    })

@app.route('/reset', methods=['POST'])
def reset():
    """Reset the conversation history."""
    if agent:
        agent.reset_conversation()
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(debug=False, port=5000)
