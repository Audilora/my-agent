// DOM elements
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const chatMessages = document.getElementById('chatMessages');
const categorySelect = document.getElementById('categorySelect');
const generateTextBtn = document.getElementById('generateTextBtn');
const playAudioBtn = document.getElementById('playAudioBtn');
const generatedBox = document.getElementById('generatedBox');

// Event listeners
sendBtn.addEventListener('click', sendMessage);
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});
if (generateTextBtn) generateTextBtn.addEventListener('click', handleGenerateText);
if (playAudioBtn) playAudioBtn.addEventListener('click', handlePlayAudio);

// Keyboard accessibility: Allow Space key to activate buttons
sendBtn.addEventListener('keydown', (e) => {
    if (e.key === ' ' || e.key === 'Spacebar') {
        e.preventDefault();
        sendMessage();
    }
});

// Functions
function sendMessage() {
    const message = messageInput.value.trim();

    if (!message) {
        return;
    }

    // Clear welcome message if present
    const welcomeMessage = document.querySelector('.welcome-message');
    if (welcomeMessage) {
        welcomeMessage.remove();
    }

    // Add user message to chat
    addMessage(message, 'user');

    // Clear input
    messageInput.value = '';

    // Disable input while processing
    setInputDisabled(true);

    // Show typing indicator
    const typingIndicator = addTypingIndicator();

    // Send to server
    fetch('/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            message: message
        })
    })
        .then(response => response.json())
        .then(data => {
            // Remove typing indicator
            typingIndicator.remove();

            if (data.error) {
                addMessage(`Error: ${data.error}`, 'agent');
            } else if (data.response_html) {
                addMessage(data.response_html, 'agent', { isHtml: true });
            } else {
                addMessage(data.response, 'agent');
            }

            // Re-enable input
            setInputDisabled(false);
            messageInput.focus();
        })
        .catch(error => {
            typingIndicator.remove();
            addMessage(`Error: ${error.message}`, 'agent');
            setInputDisabled(false);
            messageInput.focus();
        });
}

// ----- Generated text / audio handlers -----
let lastGeneratedText = '';

function handleGenerateText() {
    const category = categorySelect ? categorySelect.value : 'daily life';

    generateTextBtn.disabled = true;
    generateTextBtn.textContent = 'Generando...';

    fetch('/generate_text', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category })
    })
        .then(r => r.json())
        .then(data => {
            generateTextBtn.disabled = false;
            generateTextBtn.textContent = 'Texto';
            if (data.error) {
                generatedBox.innerHTML = `<div class="error">Error: ${data.error}</div>`;
                return;
            }
            const payload = data.data || {};
            renderGeneratedPayload(payload);
        })
        .catch(err => {
            generateTextBtn.disabled = false;
            generateTextBtn.textContent = 'Texto';
            generatedBox.innerHTML = `<div class="error">Error: ${err.message}</div>`;
        });
}

function renderGeneratedPayload(payload) {
    // payload may be { original_text, interlinear, highlights }
    lastGeneratedText = '';
    if (payload.original_text) {
        lastGeneratedText = payload.original_text;
    } else if (typeof payload === 'string') {
        lastGeneratedText = payload;
    }

    // Build rendering for generated content.
    let html = '';
    if (payload.original_text) {
        html += `<div class="generated-text">${renderHighlightedText(payload.original_text, payload.highlights)}</div>`;
    }

    if (Array.isArray(payload.interlinear) && payload.interlinear.length) {
        // Build a single-line adaptation from the Spanish-friendly pieces.
        const adaptationParts = payload.interlinear.map(pair => pair && pair[1] ? pair[1] : '').filter(Boolean);
        const adaptationLine = escapeHtml(adaptationParts.join(' '));
        html += `<div class="interlinear-box"><div class="interline"><div class="es adaptation">${adaptationLine}</div></div></div>`;
    }

    if (!html) {
        html = '<pre>No hay texto generado.</pre>';
    }

    generatedBox.innerHTML = html;
    if (lastGeneratedText) playAudioBtn.disabled = false;
}

function renderHighlightedText(text, highlights) {
    if (!Array.isArray(highlights) || highlights.length === 0) {
        return `<pre>${escapeHtml(text)}</pre>`;
    }

    const sortedHighlights = highlights.slice().sort((a, b) => (a.start || 0) - (b.start || 0));
    let html = '';
    let lastIndex = 0;

    for (const highlight of sortedHighlights) {
        const start = Math.max(0, Math.min(text.length, Number(highlight.start) || 0));
        const end = Math.max(start, Math.min(text.length, Number(highlight.end) || start));

        if (lastIndex < start) {
            html += escapeHtml(text.substring(lastIndex, start));
        }

        const spanText = escapeHtml(text.substring(start, end));

        // Normalize technique names to stable CSS class keys
        const rawTechnique = String(highlight.technique || '').toLowerCase();
        const techniqueMap = {
            linking: 'linking',
            blend: 'blending',
            blending: 'blending',
            assimilate: 'assimilation',
            assimilation: 'assimilation',
            reduction: 'reductions',
            reductions: 'reductions',
            reduce: 'reductions'
        };
        const techniqueKey = techniqueMap[rawTechnique] || (rawTechnique || 'highlight');
        const title = escapeHtml(`${techniqueKey}${highlight.word ? `: ${highlight.word}` : ''}`);

        html += `<span class="highlight highlight-${techniqueKey}" data-technique="${techniqueKey}" aria-label="${title}" title="${title}">${spanText}</span>`;
        lastIndex = end;
    }

    if (lastIndex < text.length) {
        html += escapeHtml(text.substring(lastIndex));
    }

    return `<pre>${html}</pre>`;
}

function handlePlayAudio() {
    if (!lastGeneratedText) return;
    playAudioBtn.disabled = true;
    playAudioBtn.textContent = 'Generando audio...';

    fetch('/synthesize_audio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: lastGeneratedText })
    })
        .then(r => r.json())
        .then(data => {
            playAudioBtn.disabled = false;
            playAudioBtn.textContent = 'Audio';
            if (data.error) {
                alert('Error: ' + data.error);
                return;
            }
            if (data.audio_url) {
                const audio = new Audio(data.audio_url);
                audio.play();
            }
        })
        .catch(err => {
            playAudioBtn.disabled = false;
            playAudioBtn.textContent = 'Audio';
            alert('Error: ' + err.message);
        });
}

function addMessage(text, sender, options = {}) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;
    messageDiv.setAttribute('role', 'article');
    messageDiv.setAttribute('aria-label', `${sender === 'user' ? 'User' : 'Agent'} message`);

    const content = document.createElement('div');
    content.className = 'message-content';

    if (options.isHtml === true) {
        content.innerHTML = text;
    } else {
        // Security: Escape HTML first, then safely render structured response content.
        const formattedText = renderMessageContent(text);
        content.innerHTML = formattedText;
    }

    messageDiv.appendChild(content);

    chatMessages.appendChild(messageDiv);
    scrollToBottom();

    // Scroll again after a short delay to ensure content is fully rendered
    setTimeout(scrollToBottom, 100);
}

function renderMessageContent(text) {
    const normalizedText = String(text || '').replace(/\r\n/g, '\n');
    const markedLib = resolveMarkedLibrary();
    const purifyLib = resolvePurifyLibrary();

    // Fallback rendering if markdown libraries fail to load.
    if (!markedLib || !purifyLib) {
        return renderFallbackMarkdown(normalizedText);
    }

    const renderer = new markedLib.Renderer();
    renderer.link = (hrefOrToken, title, textValue) => {
        let href = hrefOrToken;
        let linkTitle = title;
        let textContent = textValue;

        // Marked v12+ uses an object argument; older versions pass (href, title, text).
        if (hrefOrToken && typeof hrefOrToken === 'object') {
            href = hrefOrToken.href;
            linkTitle = hrefOrToken.title;
            textContent = markedLib.Parser && hrefOrToken.tokens
                ? markedLib.Parser.parseInline(hrefOrToken.tokens)
                : hrefOrToken.text;
        }

        const safeHref = href || '#';
        const safeTitle = linkTitle ? ` title="${escapeHtml(linkTitle)}"` : '';
        return `<a href="${safeHref}"${safeTitle} target="_blank" rel="noopener noreferrer">${textContent}</a>`;
    };

    markedLib.setOptions({
        gfm: true,
        breaks: true,
        renderer
    });

    const rawHtml = markedLib.parse(normalizedText);
    return purifyLib.sanitize(rawHtml, {
        USE_PROFILES: { html: true },
        ALLOWED_ATTR: ['href', 'title', 'target', 'rel', 'class']
    });
}

function resolveMarkedLibrary() {
    if (typeof marked === 'undefined' && typeof window === 'undefined') {
        return null;
    }

    const candidate = typeof marked !== 'undefined' ? marked : window.marked;
    if (!candidate) {
        return null;
    }

    if (typeof candidate.parse === 'function') {
        return candidate;
    }

    if (typeof candidate.marked === 'function') {
        return {
            parse: candidate.marked,
            setOptions: candidate.setOptions ? candidate.setOptions.bind(candidate) : () => { },
            Renderer: candidate.Renderer,
            Parser: candidate.Parser
        };
    }

    if (typeof candidate === 'function') {
        return {
            parse: candidate,
            setOptions: candidate.setOptions ? candidate.setOptions.bind(candidate) : () => { },
            Renderer: candidate.Renderer,
            Parser: candidate.Parser
        };
    }

    return null;
}

function resolvePurifyLibrary() {
    if (typeof DOMPurify !== 'undefined') {
        return DOMPurify;
    }

    if (typeof window !== 'undefined') {
        if (window.DOMPurify) {
            return window.DOMPurify;
        }
        if (window.dompurify && typeof window.dompurify.sanitize === 'function') {
            return window.dompurify;
        }
    }

    return null;
}

function renderFallbackMarkdown(text) {
    let html = escapeHtml(text);

    // Fenced code blocks.
    html = html.replace(/```(\w+)?\n([\s\S]*?)```/g, (_, _language, code) => {
        return `<pre><code>${code.trimEnd()}</code></pre>`;
    });

    // Inline code, strong, emphasis.
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // Links.
    html = html.replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');

    // Basic line breaks.
    return html.replace(/\n/g, '<br>');
}

function escapeHtml(text) {
    return text.replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function addTypingIndicator() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message agent';
    messageDiv.id = 'typing-indicator';
    messageDiv.setAttribute('role', 'status');
    messageDiv.setAttribute('aria-label', 'Agent is typing');
    messageDiv.setAttribute('aria-live', 'polite');

    const content = document.createElement('div');
    content.className = 'message-content';

    const indicator = document.createElement('div');
    indicator.className = 'typing-indicator';
    indicator.setAttribute('aria-hidden', 'true');
    indicator.innerHTML = '<span></span><span></span><span></span>';

    content.appendChild(indicator);
    messageDiv.appendChild(content);

    chatMessages.appendChild(messageDiv);
    scrollToBottom();

    return messageDiv;
}

function setInputDisabled(disabled) {
    messageInput.disabled = disabled;
    sendBtn.disabled = disabled;

    // Update ARIA attributes for better screen reader support
    if (disabled) {
        sendBtn.setAttribute('aria-busy', 'true');
        messageInput.setAttribute('aria-busy', 'true');
    } else {
        sendBtn.removeAttribute('aria-busy');
        messageInput.removeAttribute('aria-busy');
    }
}

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Focus input on load
messageInput.focus();
