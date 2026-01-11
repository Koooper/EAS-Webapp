/**
 * EAS Webapp - Frontend Application
 */

// State
const state = {
    eventCodes: {},
    originators: {},
    states: {},
    locations: [],
    tts: {
        available: false,
        backend: null,
        voices: []
    }
};

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    await loadCodes();
    render();
    setupEventListeners();
});

// Load reference data
async function loadCodes() {
    try {
        const [events, originators, states, tts] = await Promise.all([
            fetch('/api/codes/events').then(r => r.json()),
            fetch('/api/codes/originators').then(r => r.json()),
            fetch('/api/codes/states').then(r => r.json()),
            fetch('/api/tts/status').then(r => r.json()).catch(() => ({ available: false }))
        ]);
        state.eventCodes = events;
        state.originators = originators;
        state.states = states;
        state.tts = tts;
    } catch (e) {
        console.error('Failed to load codes:', e);
    }
}

// Main render
function render() {
    const app = document.getElementById('app');
    app.innerHTML = `
        <header class="header">
            <h1>EAS Webapp</h1>
            <div class="subtitle">SAME/CAP Emergency Alert Encoder & Decoder</div>
        </header>

        <nav class="tabs">
            <button class="tab active" data-panel="encode">Encode</button>
            <button class="tab" data-panel="decode">Decode</button>
            <button class="tab" data-panel="reference">Reference</button>
        </nav>

        <section id="encode" class="panel active">
            ${renderEncodePanel()}
        </section>

        <section id="decode" class="panel">
            ${renderDecodePanel()}
        </section>

        <section id="reference" class="panel">
            ${renderReferencePanel()}
        </section>
    `;
}

function renderEncodePanel() {
    const originatorOptions = Object.entries(state.originators)
        .map(([code, info]) => `<option value="${code}">${code} - ${info.name}</option>`)
        .join('');

    // Group events by category
    const eventsByCategory = {};
    Object.entries(state.eventCodes).forEach(([code, info]) => {
        if (!eventsByCategory[info.category]) {
            eventsByCategory[info.category] = [];
        }
        eventsByCategory[info.category].push({ code, ...info });
    });

    const eventOptions = Object.entries(eventsByCategory)
        .map(([category, events]) => {
            const options = events
                .sort((a, b) => a.priority - b.priority)
                .map(e => `<option value="${e.code}">${e.code} - ${e.name}</option>`)
                .join('');
            return `<optgroup label="${category.toUpperCase()}">${options}</optgroup>`;
        })
        .join('');

    const stateOptions = Object.entries(state.states)
        .filter(([code]) => code !== '00')
        .map(([code, name]) => `<option value="${code}">${name}</option>`)
        .join('');

    return `
        <form id="encode-form">
            <div class="form-row">
                <div class="form-group">
                    <label>Originator</label>
                    <select name="originator" required>
                        ${originatorOptions}
                    </select>
                </div>
                <div class="form-group">
                    <label>Event Code</label>
                    <select name="event" required>
                        ${eventOptions}
                    </select>
                </div>
            </div>

            <div class="form-row">
                <div class="form-group">
                    <label>State</label>
                    <select id="state-select">
                        <option value="">Select state...</option>
                        ${stateOptions}
                    </select>
                </div>
                <div class="form-group">
                    <label>County Code (000 = entire state)</label>
                    <input type="text" id="county-input" placeholder="000" maxlength="3" pattern="[0-9]{3}">
                </div>
                <div class="form-group">
                    <label>&nbsp;</label>
                    <button type="button" class="btn" id="add-location">Add Location</button>
                </div>
            </div>

            <div class="form-group">
                <label>Locations</label>
                <div id="locations-container" class="locations-container">
                    ${state.locations.length === 0 ? '<span style="color: var(--text-secondary)">No locations added</span>' : ''}
                </div>
            </div>

            <div class="form-row">
                <div class="form-group">
                    <label>Duration (minutes)</label>
                    <input type="number" name="duration" value="30" min="1" max="9959" required>
                </div>
                <div class="form-group">
                    <label>Callsign</label>
                    <input type="text" name="callsign" placeholder="WXYZ/FM" maxlength="8" required>
                </div>
                <div class="form-group">
                    <label>Attention Tone (seconds)</label>
                    <input type="number" name="attention_duration" value="8" min="8" max="25">
                </div>
            </div>

            ${state.tts.available ? `
            <div class="form-group" style="margin-top: 20px; padding: 16px; background: var(--bg-tertiary); border: 1px solid var(--border-color);">
                <label style="display: flex; align-items: center; gap: 10px;">
                    <input type="checkbox" name="include_voice" id="include-voice" checked style="width: auto;">
                    Include Voice Message
                    <span style="color: var(--text-secondary); font-size: 0.8rem;">(TTS: ${state.tts.backend})</span>
                </label>

                <div id="voice-options" style="margin-top: 12px;">
                    <div class="form-row">
                        <div class="form-group">
                            <label>Voice</label>
                            <select name="voice">
                                ${state.tts.voices.map(v =>
                                    `<option value="${v.name}">${v.name.replace(/_/g, ' ')}</option>`
                                ).join('')}
                            </select>
                        </div>
                    </div>
                    <div class="form-group">
                        <label>Custom Message (leave empty for auto-generated)</label>
                        <textarea name="voice_text" rows="3" placeholder="The following message is transmitted at the request of..."></textarea>
                    </div>
                </div>
            </div>
            ` : `
            <div class="form-group" style="margin-top: 20px; padding: 16px; background: var(--bg-tertiary); border: 1px solid var(--border-color);">
                <span style="color: var(--text-secondary);">Voice messages unavailable - install edge-tts for TTS support</span>
            </div>
            `}

            <div class="form-row" style="margin-top: 20px;">
                <div class="form-group">
                    <button type="submit" class="btn btn-primary">Generate Alert</button>
                    <button type="button" class="btn btn-secondary" id="header-only">Header Only</button>
                    ${state.tts.available ? '<button type="button" class="btn" id="with-voice">With Voice</button>' : ''}
                </div>
            </div>
        </form>

        <div id="encode-output"></div>
    `;
}

function renderDecodePanel() {
    return `
        <div class="drop-zone" id="drop-zone">
            <input type="file" id="audio-file" accept="audio/*">
            <p>Drop audio file here or click to upload</p>
            <p style="color: var(--text-secondary); font-size: 0.8rem; margin-top: 8px;">WAV, MP3, or other audio formats</p>
        </div>

        <div class="form-group" style="margin-top: 20px;">
            <label>Or parse a SAME header string</label>
            <div style="display: flex; gap: 10px;">
                <input type="text" id="header-input" placeholder="ZCZC-WXR-TOR-029095+0030-1051234-KWNS/NWS-" style="flex: 1;">
                <button class="btn" id="parse-header">Parse</button>
            </div>
        </div>

        <div id="decode-output"></div>
    `;
}

function renderReferencePanel() {
    // Weather events
    const weatherEvents = Object.entries(state.eventCodes)
        .filter(([, info]) => info.category === 'weather')
        .sort((a, b) => a[1].priority - b[1].priority);

    // Civil events
    const civilEvents = Object.entries(state.eventCodes)
        .filter(([, info]) => info.category === 'civil')
        .sort((a, b) => a[1].priority - b[1].priority);

    // National events
    const nationalEvents = Object.entries(state.eventCodes)
        .filter(([, info]) => info.category === 'national')
        .sort((a, b) => a[1].priority - b[1].priority);

    // Test events
    const testEvents = Object.entries(state.eventCodes)
        .filter(([, info]) => info.category === 'test');

    const renderEvents = (events) => events
        .map(([code, info]) => `
            <div class="info-item">
                <div class="code">${code}</div>
                <div class="name">${info.name}</div>
                <div class="desc">${info.description}</div>
            </div>
        `).join('');

    return `
        <h3 class="category-header">National Emergency</h3>
        <div class="info-grid">${renderEvents(nationalEvents)}</div>

        <h3 class="category-header">Weather Alerts</h3>
        <div class="info-grid">${renderEvents(weatherEvents)}</div>

        <h3 class="category-header">Civil Emergency</h3>
        <div class="info-grid">${renderEvents(civilEvents)}</div>

        <h3 class="category-header">Test Messages</h3>
        <div class="info-grid">${renderEvents(testEvents)}</div>

        <h3 class="category-header">Originators</h3>
        <div class="info-grid">
            ${Object.entries(state.originators).map(([code, info]) => `
                <div class="info-item">
                    <div class="code">${code}</div>
                    <div class="name">${info.name}</div>
                    <div class="desc">${info.description}</div>
                </div>
            `).join('')}
        </div>
    `;
}

// Event listeners
function setupEventListeners() {
    // Tab switching
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(tab.dataset.panel).classList.add('active');
        });
    });

    // Add location
    document.getElementById('add-location')?.addEventListener('click', () => {
        const stateCode = document.getElementById('state-select').value;
        const countyCode = document.getElementById('county-input').value || '000';

        if (!stateCode) {
            alert('Select a state');
            return;
        }

        const locationCode = `0${stateCode}${countyCode.padStart(3, '0')}`;
        if (!state.locations.includes(locationCode)) {
            state.locations.push(locationCode);
            updateLocationsDisplay();
        }
    });

    // Encode form
    document.getElementById('encode-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        await encodeMessage('full');
    });

    // Header only button
    document.getElementById('header-only')?.addEventListener('click', async () => {
        await encodeMessage('header-only');
    });

    // With voice button
    document.getElementById('with-voice')?.addEventListener('click', async () => {
        await encodeMessage('with-voice');
    });

    // Toggle voice options visibility
    document.getElementById('include-voice')?.addEventListener('change', (e) => {
        const voiceOptions = document.getElementById('voice-options');
        if (voiceOptions) {
            voiceOptions.style.display = e.target.checked ? 'block' : 'none';
        }
    });

    // File drop zone
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('audio-file');

    dropZone?.addEventListener('click', () => fileInput.click());
    dropZone?.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });
    dropZone?.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });
    dropZone?.addEventListener('drop', async (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file) await decodeFile(file);
    });
    fileInput?.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (file) await decodeFile(file);
    });

    // Parse header
    document.getElementById('parse-header')?.addEventListener('click', async () => {
        const header = document.getElementById('header-input').value;
        if (header) await parseHeader(header);
    });
}

function updateLocationsDisplay() {
    const container = document.getElementById('locations-container');
    if (!container) return;

    if (state.locations.length === 0) {
        container.innerHTML = '<span style="color: var(--text-secondary)">No locations added</span>';
        return;
    }

    container.innerHTML = state.locations.map((loc, i) => {
        const stateCode = loc.substring(1, 3);
        const stateName = state.states[stateCode] || 'Unknown';
        const countyCode = loc.substring(3);
        const countyText = countyCode === '000' ? 'Entire state' : `County ${countyCode}`;

        return `
            <div class="location-chip">
                <span>${loc}</span>
                <span style="color: var(--text-secondary)">(${stateName}, ${countyText})</span>
                <span class="remove" data-index="${i}">&times;</span>
            </div>
        `;
    }).join('');

    // Add remove listeners
    container.querySelectorAll('.remove').forEach(btn => {
        btn.addEventListener('click', () => {
            state.locations.splice(parseInt(btn.dataset.index), 1);
            updateLocationsDisplay();
        });
    });
}

async function encodeMessage(mode) {
    const form = document.getElementById('encode-form');
    const formData = new FormData(form);
    const output = document.getElementById('encode-output');

    if (state.locations.length === 0) {
        output.innerHTML = '<div class="status error">Add at least one location</div>';
        return;
    }

    output.innerHTML = '<div class="loading"></div> Generating...';

    const payload = {
        originator: formData.get('originator'),
        event: formData.get('event'),
        locations: state.locations,
        duration: parseInt(formData.get('duration')),
        callsign: formData.get('callsign'),
        attention_duration: parseFloat(formData.get('attention_duration'))
    };

    // add voice options if with-voice mode
    if (mode === 'with-voice') {
        payload.include_voice = true;
        payload.voice = formData.get('voice');
        const voiceText = formData.get('voice_text')?.trim();
        if (voiceText) {
            payload.voice_text = voiceText;
        }
    }

    try {
        let endpoint;
        if (mode === 'header-only') {
            endpoint = '/api/encode/header-only';
        } else if (mode === 'with-voice') {
            endpoint = '/api/encode/with-voice';
        } else {
            endpoint = '/api/encode';
        }

        const res = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();

        if (!data.success) {
            output.innerHTML = `<div class="status error">${data.error}</div>`;
            return;
        }

        const audioUrl = `data:audio/wav;base64,${data.audio}`;

        output.innerHTML = `
            <div class="status success">Alert generated successfully</div>

            <div class="header-display">${data.header}</div>

            ${data.parsed ? `
                <div class="decoded-message">
                    <div class="field">
                        <span class="field-label">Originator:</span>
                        <span class="field-value">${data.parsed.originator} - ${data.parsed.originator_name}</span>
                    </div>
                    <div class="field">
                        <span class="field-label">Event:</span>
                        <span class="field-value">${data.parsed.event} - ${data.parsed.event_name}</span>
                    </div>
                    <div class="field">
                        <span class="field-label">Locations:</span>
                        <span class="field-value">${data.parsed.locations_formatted.join(', ')}</span>
                    </div>
                    <div class="field">
                        <span class="field-label">Duration:</span>
                        <span class="field-value">${data.parsed.purge_time.substring(0, 2)}h ${data.parsed.purge_time.substring(2)}m</span>
                    </div>
                    <div class="field">
                        <span class="field-label">Callsign:</span>
                        <span class="field-value">${data.parsed.callsign}</span>
                    </div>
                </div>
            ` : ''}

            <div class="audio-container">
                <label>Audio Output</label>
                <audio controls src="${audioUrl}"></audio>
                <div style="margin-top: 10px;">
                    <a href="${audioUrl}" download="eas_alert.wav" class="btn btn-secondary">Download WAV</a>
                </div>
            </div>
        `;
    } catch (e) {
        output.innerHTML = `<div class="status error">Request failed: ${e.message}</div>`;
    }
}

async function decodeFile(file) {
    const output = document.getElementById('decode-output');
    output.innerHTML = '<div class="loading"></div> Decoding...';

    const formData = new FormData();
    formData.append('audio', file);

    try {
        const res = await fetch('/api/decode', {
            method: 'POST',
            body: formData
        });

        const data = await res.json();

        if (!data.success) {
            output.innerHTML = `<div class="status error">${data.error}</div>`;
            return;
        }

        if (data.messages.length === 0) {
            output.innerHTML = '<div class="status error">No SAME messages found in audio</div>';
            return;
        }

        output.innerHTML = `
            <div class="status success">Found ${data.messages.length} message(s)</div>
            ${data.messages.map(msg => renderDecodedMessage(msg)).join('')}
        `;
    } catch (e) {
        output.innerHTML = `<div class="status error">Decode failed: ${e.message}</div>`;
    }
}

async function parseHeader(header) {
    const output = document.getElementById('decode-output');
    output.innerHTML = '<div class="loading"></div> Parsing...';

    try {
        const res = await fetch('/api/parse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ header })
        });

        const data = await res.json();

        if (!data.success) {
            output.innerHTML = `<div class="status error">${data.error}</div>`;
            return;
        }

        output.innerHTML = `
            <div class="status success">Header parsed successfully</div>
            ${renderDecodedMessage({
                raw: data.raw,
                type: 'header',
                originator: data.originator,
                originator_name: data.originator_name,
                event: data.event,
                event_name: data.event_name,
                locations: data.locations,
                locations_formatted: data.locations_formatted,
                purge_time: data.purge_time,
                issue_time: data.issue_time,
                callsign: data.callsign
            })}
        `;
    } catch (e) {
        output.innerHTML = `<div class="status error">Parse failed: ${e.message}</div>`;
    }
}

function renderDecodedMessage(msg) {
    if (msg.type === 'eom') {
        return `
            <div class="decoded-message eom">
                <span class="type-badge eom">End of Message</span>
                <div class="header-display">${msg.raw}</div>
            </div>
        `;
    }

    if (msg.parse_error) {
        return `
            <div class="decoded-message">
                <span class="type-badge header">Header</span>
                <div class="header-display">${msg.raw}</div>
                <div class="status error">Parse error: ${msg.parse_error}</div>
            </div>
        `;
    }

    return `
        <div class="decoded-message">
            <span class="type-badge header">Header</span>
            <div class="header-display">${msg.raw}</div>
            <div class="field">
                <span class="field-label">Originator:</span>
                <span class="field-value">${msg.originator} - ${msg.originator_name}</span>
            </div>
            <div class="field">
                <span class="field-label">Event:</span>
                <span class="field-value">${msg.event} - ${msg.event_name}</span>
            </div>
            <div class="field">
                <span class="field-label">Locations:</span>
                <span class="field-value">${msg.locations_formatted?.join(', ') || msg.locations?.join(', ')}</span>
            </div>
            <div class="field">
                <span class="field-label">Duration:</span>
                <span class="field-value">${msg.purge_time?.substring(0, 2)}h ${msg.purge_time?.substring(2)}m</span>
            </div>
            <div class="field">
                <span class="field-label">Issue Time:</span>
                <span class="field-value">Day ${msg.issue_time?.substring(0, 3)}, ${msg.issue_time?.substring(3, 5)}:${msg.issue_time?.substring(5)} UTC</span>
            </div>
            <div class="field">
                <span class="field-label">Callsign:</span>
                <span class="field-value">${msg.callsign}</span>
            </div>
        </div>
    `;
}
