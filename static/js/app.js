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

// Audio visualization state
const audioViz = {
    audioContext: null,
    analyser: null,
    source: null,
    canvas: null,
    canvasCtx: null,
    animationId: null,
    mode: 'oscilloscope', // 'oscilloscope' | 'spectrogram'
    isPlaying: false
};

// Initialize Web Audio API
function initAudioContext() {
    if (!audioViz.audioContext) {
        audioViz.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    return audioViz.audioContext;
}

// Setup audio analyzer for visualization
function setupAnalyzer(audioElement) {
    const ctx = initAudioContext();

    if (audioViz.source) {
        audioViz.source.disconnect();
    }

    audioViz.analyser = ctx.createAnalyser();
    audioViz.analyser.fftSize = 2048;
    audioViz.analyser.smoothingTimeConstant = 0.8;

    audioViz.source = ctx.createMediaElementSource(audioElement);
    audioViz.source.connect(audioViz.analyser);
    audioViz.analyser.connect(ctx.destination);

    return audioViz.analyser;
}

// Draw oscilloscope waveform
function drawOscilloscope() {
    if (!audioViz.analyser || !audioViz.canvas) return;

    const canvas = audioViz.canvas;
    const ctx = audioViz.canvasCtx;
    const analyser = audioViz.analyser;
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    analyser.getByteTimeDomainData(dataArray);

    // terminal green on dark bg
    ctx.fillStyle = '#0a0a0a';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // draw grid
    ctx.strokeStyle = '#1a1a1a';
    ctx.lineWidth = 1;
    for (let i = 0; i < 10; i++) {
        const y = (canvas.height / 10) * i;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
        ctx.stroke();
    }
    for (let i = 0; i < 20; i++) {
        const x = (canvas.width / 20) * i;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
        ctx.stroke();
    }

    // draw waveform
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#33ff66';
    ctx.beginPath();

    const sliceWidth = canvas.width / bufferLength;
    let x = 0;

    for (let i = 0; i < bufferLength; i++) {
        const v = dataArray[i] / 128.0;
        const y = (v * canvas.height) / 2;

        if (i === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
        x += sliceWidth;
    }

    ctx.lineTo(canvas.width, canvas.height / 2);
    ctx.stroke();

    // draw center line
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, canvas.height / 2);
    ctx.lineTo(canvas.width, canvas.height / 2);
    ctx.stroke();

    if (audioViz.isPlaying) {
        audioViz.animationId = requestAnimationFrame(drawOscilloscope);
    }
}

// Draw spectrogram (frequency domain)
function drawSpectrogram() {
    if (!audioViz.analyser || !audioViz.canvas) return;

    const canvas = audioViz.canvas;
    const ctx = audioViz.canvasCtx;
    const analyser = audioViz.analyser;
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    analyser.getByteFrequencyData(dataArray);

    ctx.fillStyle = '#0a0a0a';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // draw frequency bars
    const barWidth = (canvas.width / bufferLength) * 2.5;
    let x = 0;

    // mark EAS frequencies - 853, 960, 1562.5, 2083.3 Hz
    // sample rate is typically 22050, so nyquist is 11025
    // fftSize 2048 means 1024 bins, each bin is ~10.8 Hz
    const sampleRate = audioViz.audioContext?.sampleRate || 22050;
    const binWidth = sampleRate / analyser.fftSize;

    const easFreqs = [
        { freq: 853, label: '853Hz', color: '#ff3333' },
        { freq: 960, label: '960Hz', color: '#ff3333' },
        { freq: 1562.5, label: 'SPACE', color: '#3399ff' },
        { freq: 2083.3, label: 'MARK', color: '#ffaa00' }
    ];

    for (let i = 0; i < bufferLength; i++) {
        const barHeight = (dataArray[i] / 255) * canvas.height;

        // color based on frequency range
        const freq = i * binWidth;
        let color;
        if (freq >= 800 && freq <= 1000) {
            color = `rgba(255, 51, 51, ${0.3 + dataArray[i]/255 * 0.7})`; // attention tone
        } else if (freq >= 1500 && freq <= 1700) {
            color = `rgba(51, 153, 255, ${0.3 + dataArray[i]/255 * 0.7})`; // space freq
        } else if (freq >= 2000 && freq <= 2200) {
            color = `rgba(255, 170, 0, ${0.3 + dataArray[i]/255 * 0.7})`; // mark freq
        } else {
            color = `rgba(51, 255, 102, ${0.2 + dataArray[i]/255 * 0.5})`;
        }

        ctx.fillStyle = color;
        ctx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);
        x += barWidth + 1;

        if (x > canvas.width) break;
    }

    // draw frequency markers
    ctx.font = '10px Consolas, monospace';
    ctx.fillStyle = '#808080';
    easFreqs.forEach(({ freq, label, color }) => {
        const binIndex = Math.round(freq / binWidth);
        const xPos = binIndex * (barWidth + 1);
        if (xPos < canvas.width) {
            ctx.fillStyle = color;
            ctx.fillText(label, xPos, 12);
            ctx.strokeStyle = color;
            ctx.setLineDash([2, 2]);
            ctx.beginPath();
            ctx.moveTo(xPos, 15);
            ctx.lineTo(xPos, canvas.height);
            ctx.stroke();
            ctx.setLineDash([]);
        }
    });

    if (audioViz.isPlaying) {
        audioViz.animationId = requestAnimationFrame(drawSpectrogram);
    }
}

// Start visualization
function startVisualization() {
    audioViz.isPlaying = true;
    if (audioViz.mode === 'oscilloscope') {
        drawOscilloscope();
    } else {
        drawSpectrogram();
    }
}

// Stop visualization
function stopVisualization() {
    audioViz.isPlaying = false;
    if (audioViz.animationId) {
        cancelAnimationFrame(audioViz.animationId);
        audioViz.animationId = null;
    }
}

// Toggle visualization mode
function toggleVizMode() {
    audioViz.mode = audioViz.mode === 'oscilloscope' ? 'spectrogram' : 'oscilloscope';
    const btn = document.getElementById('viz-mode-btn');
    if (btn) {
        btn.textContent = audioViz.mode === 'oscilloscope' ? 'Spectrogram' : 'Oscilloscope';
    }
    if (audioViz.isPlaying) {
        stopVisualization();
        startVisualization();
    }
}

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
            <button class="tab" data-panel="batch">Batch</button>
            <button class="tab" data-panel="archive">Archive</button>
            <button class="tab" data-panel="cap">CAP/IPAWS</button>
            <button class="tab" data-panel="live">Live Feed</button>
            <button class="tab" data-panel="wea">WEA Preview</button>
            <button class="tab" data-panel="endec">ENDEC</button>
            <button class="tab" data-panel="cascade">Cascade</button>
            <button class="tab" data-panel="reference">Reference</button>
        </nav>

        <section id="encode" class="panel active">
            ${renderEncodePanel()}
        </section>

        <section id="decode" class="panel">
            ${renderDecodePanel()}
        </section>

        <section id="batch" class="panel">
            ${renderBatchPanel()}
        </section>

        <section id="archive" class="panel">
            ${renderArchivePanel()}
        </section>

        <section id="cap" class="panel">
            ${renderCAPPanel()}
        </section>

        <section id="live" class="panel">
            ${renderLiveFeedPanel()}
        </section>

        <section id="wea" class="panel">
            ${renderWEAPanel()}
        </section>

        <section id="endec" class="panel">
            ${renderENDECPanel()}
        </section>

        <section id="cascade" class="panel">
            ${renderCascadePanel()}
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

function renderCascadePanel() {
    return `
        <div class="cascade-section">
            <h3 class="category-header">EAS Alert Cascade Visualization</h3>
            <p style="color: var(--text-secondary); margin-bottom: 20px;">
                Visualize how EAS alerts propagate through the broadcast daisy chain network.
                LP1 (Primary) stations receive alerts first and forward to LP2 stations.
            </p>

            <div class="form-row">
                <div class="form-group">
                    <label>Alert Type</label>
                    <select id="cascade-event">
                        <option value="TOR">TOR - Tornado Warning</option>
                        <option value="SVR">SVR - Severe Thunderstorm</option>
                        <option value="EAN">EAN - National Emergency</option>
                        <option value="RWT">RWT - Required Weekly Test</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Originator</label>
                    <select id="cascade-originator">
                        <option value="NWS">NWS - National Weather Service</option>
                        <option value="PEP">PEP - Primary Entry Point</option>
                        <option value="CIV">CIV - Civil Authorities</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>&nbsp;</label>
                    <button class="btn btn-primary" id="start-cascade">Start Cascade</button>
                </div>
            </div>

            <div class="cascade-diagram">
                <div class="cascade-tier tier-origin">
                    <div class="tier-label">ORIGIN</div>
                    <div class="cascade-node origin" id="node-origin">
                        <div class="node-icon">📡</div>
                        <div class="node-label">NWS/PEP</div>
                        <div class="node-status">READY</div>
                    </div>
                </div>

                <div class="cascade-connector"></div>

                <div class="cascade-tier tier-lp1">
                    <div class="tier-label">LP1 STATIONS</div>
                    <div class="cascade-nodes">
                        <div class="cascade-node lp1" id="node-lp1-1">
                            <div class="node-icon">📻</div>
                            <div class="node-label">WXYZ-TV</div>
                            <div class="node-status">MONITORING</div>
                        </div>
                        <div class="cascade-node lp1" id="node-lp1-2">
                            <div class="node-icon">📻</div>
                            <div class="node-label">WABC-AM</div>
                            <div class="node-status">MONITORING</div>
                        </div>
                        <div class="cascade-node lp1" id="node-lp1-3">
                            <div class="node-icon">📻</div>
                            <div class="node-label">KDEF-FM</div>
                            <div class="node-status">MONITORING</div>
                        </div>
                    </div>
                </div>

                <div class="cascade-connector"></div>

                <div class="cascade-tier tier-lp2">
                    <div class="tier-label">LP2 STATIONS</div>
                    <div class="cascade-nodes">
                        <div class="cascade-node lp2" id="node-lp2-1">
                            <div class="node-icon">📻</div>
                            <div class="node-label">WLMN-FM</div>
                            <div class="node-status">MONITORING</div>
                        </div>
                        <div class="cascade-node lp2" id="node-lp2-2">
                            <div class="node-icon">📻</div>
                            <div class="node-label">KOPQ-AM</div>
                            <div class="node-status">MONITORING</div>
                        </div>
                        <div class="cascade-node lp2" id="node-lp2-3">
                            <div class="node-icon">📻</div>
                            <div class="node-label">WRST-TV</div>
                            <div class="node-status">MONITORING</div>
                        </div>
                        <div class="cascade-node lp2" id="node-lp2-4">
                            <div class="node-icon">📻</div>
                            <div class="node-label">KUVY-FM</div>
                            <div class="node-status">MONITORING</div>
                        </div>
                    </div>
                </div>

                <div class="cascade-connector"></div>

                <div class="cascade-tier tier-public">
                    <div class="tier-label">PUBLIC</div>
                    <div class="cascade-nodes">
                        <div class="cascade-node public" id="node-public">
                            <div class="node-icon">👥</div>
                            <div class="node-label">LISTENERS</div>
                            <div class="node-status">STANDBY</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="cascade-timeline" id="cascade-timeline"></div>
        </div>
    `;
}

function renderENDECPanel() {
    return `
        <div class="endec-container">
            <div class="endec-unit">
                <div class="endec-front-panel">
                    <div class="endec-logo">
                        <span class="endec-brand">SAGE</span>
                        <span class="endec-model">ENDEC</span>
                    </div>
                    <div class="endec-display-section">
                        <div class="endec-led-row">
                            <div class="led-indicator" id="led-power">
                                <div class="led green on"></div>
                                <span>PWR</span>
                            </div>
                            <div class="led-indicator" id="led-alert">
                                <div class="led red"></div>
                                <span>ALERT</span>
                            </div>
                            <div class="led-indicator" id="led-attn">
                                <div class="led amber"></div>
                                <span>ATTN</span>
                            </div>
                            <div class="led-indicator" id="led-fwd">
                                <div class="led green"></div>
                                <span>FWD</span>
                            </div>
                            <div class="led-indicator" id="led-tx">
                                <div class="led red"></div>
                                <span>TX</span>
                            </div>
                        </div>
                        <div class="endec-lcd">
                            <div class="lcd-line" id="lcd-line1">READY</div>
                            <div class="lcd-line" id="lcd-line2">MONITORING...</div>
                        </div>
                    </div>
                    <div class="endec-controls">
                        <button class="endec-btn" id="endec-req-test">REQ TEST</button>
                        <button class="endec-btn" id="endec-fwd-alert">FWD ALERT</button>
                        <button class="endec-btn" id="endec-clear">CLEAR</button>
                    </div>
                </div>
                <div class="endec-serial-log">
                    <div class="serial-header">
                        <span>SERIAL LOG</span>
                        <span class="baud">9600 BAUD</span>
                    </div>
                    <div class="serial-output" id="endec-serial"></div>
                </div>
            </div>
            <div class="endec-input-section">
                <h3 class="category-header">Simulate Alert Reception</h3>
                <div class="form-group">
                    <label>SAME Header</label>
                    <input type="text" id="endec-header-input" placeholder="ZCZC-WXR-TOR-029095+0030-1051234-KWNS/NWS-">
                </div>
                <button class="btn btn-primary" id="endec-receive">Receive Alert</button>
            </div>
        </div>
    `;
}

function renderWEAPanel() {
    return `
        <div class="wea-section">
            <h3 class="category-header">Wireless Emergency Alert Preview</h3>
            <p style="color: var(--text-secondary); margin-bottom: 20px;">
                Preview how your alert would appear as a WEA message on mobile devices. WEA messages are limited to 360 characters.
            </p>

            <div class="form-row">
                <div class="form-group">
                    <label>Alert Type</label>
                    <select id="wea-alert-type">
                        <option value="EXTREME">EXTREME Alert</option>
                        <option value="SEVERE">SEVERE Alert</option>
                        <option value="AMBER">AMBER Alert</option>
                        <option value="PUBLIC_SAFETY">Public Safety</option>
                        <option value="TEST">Test Alert</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Phone Style</label>
                    <select id="wea-phone-style">
                        <option value="ios">iPhone (iOS)</option>
                        <option value="android">Android</option>
                    </select>
                </div>
            </div>

            <div class="form-group">
                <label>Alert Message <span id="wea-char-count" style="color: var(--text-secondary);">(0/360)</span></label>
                <textarea id="wea-message" rows="4" maxlength="360" placeholder="TORNADO WARNING for Smith County. Take shelter immediately in a basement or interior room. This is a life-threatening situation."></textarea>
            </div>

            <div class="form-group">
                <label>Source</label>
                <input type="text" id="wea-source" value="National Weather Service" placeholder="Alert source">
            </div>

            <button class="btn btn-primary" id="generate-wea">Generate Preview</button>

            <div id="wea-preview-container" style="margin-top: 30px;">
                <div class="wea-phones-row">
                    <div class="phone-mockup ios" id="phone-ios">
                        <div class="phone-notch"></div>
                        <div class="phone-screen">
                            <div class="phone-status-bar">
                                <span class="time">9:41</span>
                                <span class="icons">
                                    <span class="signal">●●●●○</span>
                                    <span class="battery">100%</span>
                                </span>
                            </div>
                            <div class="wea-alert-display" id="ios-alert"></div>
                        </div>
                        <div class="phone-home-bar"></div>
                    </div>
                    <div class="phone-mockup android" id="phone-android">
                        <div class="phone-camera"></div>
                        <div class="phone-screen">
                            <div class="phone-status-bar">
                                <span class="time">9:41</span>
                                <span class="icons">
                                    <span class="signal">▂▄▆█</span>
                                    <span class="battery">100%</span>
                                </span>
                            </div>
                            <div class="wea-alert-display" id="android-alert"></div>
                        </div>
                        <div class="phone-nav-bar">
                            <span>◁</span>
                            <span>○</span>
                            <span>▢</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function renderLiveFeedPanel() {
    const stateOptions = Object.entries(state.states)
        .filter(([code]) => code !== '00')
        .map(([code, name]) => `<option value="${code}">${name}</option>`)
        .join('');

    return `
        <div class="live-feed-section">
            <h3 class="category-header">NWS Active Alerts</h3>
            <div class="form-row">
                <div class="form-group">
                    <label>Filter by State</label>
                    <select id="nws-state-filter">
                        <option value="">All States</option>
                        ${stateOptions}
                    </select>
                </div>
                <div class="form-group">
                    <label>Severity</label>
                    <select id="nws-severity-filter">
                        <option value="">All</option>
                        <option value="Extreme">Extreme</option>
                        <option value="Severe">Severe</option>
                        <option value="Moderate">Moderate</option>
                        <option value="Minor">Minor</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Limit</label>
                    <select id="nws-limit">
                        <option value="25">25</option>
                        <option value="50" selected>50</option>
                        <option value="100">100</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>&nbsp;</label>
                    <button class="btn btn-primary" id="fetch-nws-alerts">Fetch Alerts</button>
                </div>
            </div>
            <div id="nws-summary" class="nws-summary"></div>
            <div id="nws-alerts-output"></div>
        </div>
    `;
}

function renderBatchPanel() {
    return `
        <div class="batch-section">
            <h3 class="category-header">Batch Alert Processing</h3>
            <p class="help-text">Upload CSV or JSON file to generate multiple alerts at once.</p>

            <div class="form-row">
                <div class="form-group" style="flex: 2">
                    <label>Upload Batch File</label>
                    <div class="file-dropzone" id="batch-dropzone">
                        <input type="file" id="batch-file-input" accept=".csv,.json" style="display:none">
                        <div class="dropzone-content">
                            <span class="dropzone-icon">📁</span>
                            <span>Drop CSV/JSON file here or click to browse</span>
                        </div>
                    </div>
                </div>
            </div>

            <div class="form-row">
                <div class="form-group">
                    <label>&nbsp;</label>
                    <button class="btn btn-primary" id="start-batch-job" disabled>Start Processing</button>
                    <button class="btn btn-secondary" id="download-batch-template">Download Template</button>
                </div>
            </div>

            <div id="batch-job-status" class="batch-status" style="display:none">
                <div class="status-header">
                    <span class="status-label">Job Status:</span>
                    <span class="status-value" id="batch-status-text">Pending</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" id="batch-progress" style="width: 0%"></div>
                </div>
                <div class="status-details">
                    <span>Progress: <span id="batch-progress-text">0/0</span></span>
                    <span>Errors: <span id="batch-errors-count">0</span></span>
                </div>
            </div>

            <div id="batch-results" class="batch-results"></div>

            <details class="format-help">
                <summary>CSV Format Help</summary>
                <pre>originator,event,locations,duration,callsign,attention_duration,voice_text
WXR,TOR,"029095 029097",30,WXYZ/FM,8,
CIV,EAN,000000,60,KCIV/TV,25,This is an emergency alert test</pre>
            </details>

            <details class="format-help">
                <summary>JSON Format Help</summary>
                <pre>[
  {
    "originator": "WXR",
    "event": "TOR",
    "locations": ["029095", "029097"],
    "duration": 30,
    "callsign": "WXYZ/FM"
  }
]</pre>
            </details>
        </div>
    `;
}

function renderArchivePanel() {
    const originatorOptions = Object.entries(state.originators)
        .map(([code, info]) => `<option value="${code}">${code} - ${info.name}</option>`)
        .join('');

    const eventOptions = Object.entries(state.eventCodes)
        .map(([code, info]) => `<option value="${code}">${code} - ${info.name}</option>`)
        .join('');

    return `
        <div class="archive-section">
            <h3 class="category-header">Alert Archive</h3>
            <p class="help-text">Search and replay previously generated or decoded alerts.</p>

            <div class="form-row">
                <div class="form-group">
                    <label>Event Type</label>
                    <select id="archive-event-filter">
                        <option value="">All Events</option>
                        ${eventOptions}
                    </select>
                </div>
                <div class="form-group">
                    <label>Originator</label>
                    <select id="archive-originator-filter">
                        <option value="">All Originators</option>
                        ${originatorOptions}
                    </select>
                </div>
                <div class="form-group">
                    <label>Has Voice</label>
                    <select id="archive-voice-filter">
                        <option value="">Any</option>
                        <option value="true">Yes</option>
                        <option value="false">No</option>
                    </select>
                </div>
            </div>

            <div class="form-row">
                <div class="form-group">
                    <label>From Date</label>
                    <input type="date" id="archive-start-date">
                </div>
                <div class="form-group">
                    <label>To Date</label>
                    <input type="date" id="archive-end-date">
                </div>
                <div class="form-group">
                    <label>&nbsp;</label>
                    <button class="btn btn-primary" id="search-archive">Search</button>
                    <button class="btn btn-secondary" id="load-archive-stats">Stats</button>
                </div>
            </div>

            <div id="archive-stats" class="archive-stats" style="display:none"></div>
            <div id="archive-results" class="archive-results"></div>
        </div>
    `;
}

function renderCAPPanel() {
    return `
        <div class="cap-section">
            <h3 class="category-header">Import CAP Alert</h3>
            <div class="form-group">
                <label>Paste CAP XML</label>
                <textarea id="cap-input" rows="10" placeholder="<?xml version='1.0'?>
<alert xmlns='urn:oasis:names:tc:emergency:cap:1.2'>
  <identifier>...</identifier>
  ...
</alert>"></textarea>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>Callsign (for SAME conversion)</label>
                    <input type="text" id="cap-callsign" value="EAS-WEB" maxlength="8">
                </div>
                <div class="form-group">
                    <label>&nbsp;</label>
                    <div style="display: flex; gap: 10px;">
                        <button class="btn btn-primary" id="parse-cap">Parse CAP</button>
                        <button class="btn" id="cap-to-same">Convert to SAME</button>
                    </div>
                </div>
            </div>
            <div id="cap-parse-output"></div>
        </div>

        <div class="cap-section" style="margin-top: 30px;">
            <h3 class="category-header">Export to CAP</h3>
            <div class="form-group">
                <label>SAME Header</label>
                <input type="text" id="same-to-cap-input" placeholder="ZCZC-WXR-TOR-029095+0030-1051234-KWNS/NWS-">
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>Headline (optional)</label>
                    <input type="text" id="cap-headline" placeholder="Tornado Warning for...">
                </div>
                <div class="form-group">
                    <label>Sender (optional)</label>
                    <input type="text" id="cap-sender" placeholder="w-nws.webmaster@noaa.gov">
                </div>
            </div>
            <div class="form-group">
                <label>Description (optional)</label>
                <textarea id="cap-description" rows="3" placeholder="Alert details..."></textarea>
            </div>
            <div class="form-group">
                <button class="btn" id="same-to-cap">Generate CAP XML</button>
            </div>
            <div id="cap-export-output"></div>
        </div>
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

    // CAP panel handlers
    document.getElementById('parse-cap')?.addEventListener('click', async () => {
        const xml = document.getElementById('cap-input').value;
        if (xml) await parseCAPXML(xml);
    });

    document.getElementById('cap-to-same')?.addEventListener('click', async () => {
        const xml = document.getElementById('cap-input').value;
        const callsign = document.getElementById('cap-callsign').value || 'EAS-WEB';
        if (xml) await convertCAPToSAME(xml, callsign);
    });

    document.getElementById('same-to-cap')?.addEventListener('click', async () => {
        const header = document.getElementById('same-to-cap-input').value;
        if (header) await convertSAMEToCAP(header);
    });

    // NWS Live Feed handlers
    document.getElementById('fetch-nws-alerts')?.addEventListener('click', async () => {
        await fetchNWSAlerts();
    });

    // Batch processing handlers
    const batchDropzone = document.getElementById('batch-dropzone');
    const batchFileInput = document.getElementById('batch-file-input');

    batchDropzone?.addEventListener('click', () => batchFileInput?.click());
    batchDropzone?.addEventListener('dragover', (e) => {
        e.preventDefault();
        batchDropzone.classList.add('dragover');
    });
    batchDropzone?.addEventListener('dragleave', () => {
        batchDropzone.classList.remove('dragover');
    });
    batchDropzone?.addEventListener('drop', async (e) => {
        e.preventDefault();
        batchDropzone.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file) handleBatchFileSelect(file);
    });
    batchFileInput?.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) handleBatchFileSelect(file);
    });

    document.getElementById('start-batch-job')?.addEventListener('click', async () => {
        await startBatchProcessing();
    });

    document.getElementById('download-batch-template')?.addEventListener('click', () => {
        downloadBatchTemplate();
    });

    // Archive handlers
    document.getElementById('search-archive')?.addEventListener('click', async () => {
        await searchArchive();
    });

    document.getElementById('load-archive-stats')?.addEventListener('click', async () => {
        await loadArchiveStats();
    });

    // WEA Preview handlers
    document.getElementById('generate-wea')?.addEventListener('click', () => {
        generateWEAPreview();
    });

    document.getElementById('wea-message')?.addEventListener('input', (e) => {
        const count = e.target.value.length;
        const counter = document.getElementById('wea-char-count');
        if (counter) {
            counter.textContent = `(${count}/360)`;
            counter.style.color = count > 360 ? 'var(--accent-red)' : 'var(--text-secondary)';
        }
    });

    // ENDEC handlers
    document.getElementById('endec-receive')?.addEventListener('click', () => {
        const header = document.getElementById('endec-header-input').value;
        if (header) simulateENDECReceive(header);
    });

    document.getElementById('endec-req-test')?.addEventListener('click', () => {
        simulateENDECTest();
    });

    document.getElementById('endec-clear')?.addEventListener('click', () => {
        clearENDEC();
    });

    // Cascade visualization handler
    document.getElementById('start-cascade')?.addEventListener('click', () => {
        const event = document.getElementById('cascade-event')?.value || 'TOR';
        const originator = document.getElementById('cascade-originator')?.value || 'NWS';
        startCascadeAnimation(event, originator);
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
                <div class="viz-container">
                    <div class="viz-header">
                        <span class="viz-label">Signal Analyzer</span>
                        <button type="button" class="btn btn-small" id="viz-mode-btn">Spectrogram</button>
                    </div>
                    <canvas id="audio-viz-canvas" width="800" height="200"></canvas>
                </div>
                <audio id="audio-player" controls src="${audioUrl}" crossorigin="anonymous"></audio>
                <div class="download-row" style="margin-top: 10px; display: flex; gap: 10px; align-items: center;">
                    <a href="${audioUrl}" download="eas_alert.wav" class="btn btn-secondary" id="download-wav-btn">Download WAV</a>
                    <select id="export-format-select" class="form-control" style="width: auto;">
                        <option value="wav">WAV (Original)</option>
                        <option value="mp3">MP3</option>
                        <option value="ogg">OGG Vorbis</option>
                        <option value="flac">FLAC</option>
                    </select>
                    <button type="button" class="btn btn-secondary" id="convert-format-btn">Convert & Download</button>
                </div>
            </div>
        `;

        // Setup audio visualization
        const audioPlayer = document.getElementById('audio-player');
        const vizCanvas = document.getElementById('audio-viz-canvas');
        const vizModeBtn = document.getElementById('viz-mode-btn');

        if (audioPlayer && vizCanvas) {
            audioViz.canvas = vizCanvas;
            audioViz.canvasCtx = vizCanvas.getContext('2d');

            // draw initial empty state
            audioViz.canvasCtx.fillStyle = '#0a0a0a';
            audioViz.canvasCtx.fillRect(0, 0, vizCanvas.width, vizCanvas.height);
            audioViz.canvasCtx.strokeStyle = '#333';
            audioViz.canvasCtx.beginPath();
            audioViz.canvasCtx.moveTo(0, vizCanvas.height / 2);
            audioViz.canvasCtx.lineTo(vizCanvas.width, vizCanvas.height / 2);
            audioViz.canvasCtx.stroke();

            audioPlayer.addEventListener('play', () => {
                // resume audio context if suspended (browser autoplay policy)
                if (audioViz.audioContext?.state === 'suspended') {
                    audioViz.audioContext.resume();
                }
                if (!audioViz.source) {
                    setupAnalyzer(audioPlayer);
                }
                startVisualization();
            });

            audioPlayer.addEventListener('pause', () => {
                stopVisualization();
            });

            audioPlayer.addEventListener('ended', () => {
                stopVisualization();
            });

            vizModeBtn?.addEventListener('click', toggleVizMode);
        }

        // Format conversion handler
        const convertBtn = document.getElementById('convert-format-btn');
        const formatSelect = document.getElementById('export-format-select');
        convertBtn?.addEventListener('click', async () => {
            const format = formatSelect?.value;
            if (!format || format === 'wav') {
                // just download the WAV
                document.getElementById('download-wav-btn')?.click();
                return;
            }

            convertBtn.disabled = true;
            convertBtn.textContent = 'Converting...';

            try {
                const res = await fetch('/api/audio/convert', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        audio: data.audio,
                        format: format
                    })
                });
                const result = await res.json();

                if (!result.success) {
                    throw new Error(result.error);
                }

                // download converted file
                const mimeTypes = {
                    'mp3': 'audio/mpeg',
                    'ogg': 'audio/ogg',
                    'flac': 'audio/flac'
                };
                const a = document.createElement('a');
                a.href = `data:${mimeTypes[format]};base64,${result.audio}`;
                a.download = `eas_alert.${format}`;
                a.click();
            } catch (e) {
                alert(`Conversion failed: ${e.message}`);
            } finally {
                convertBtn.disabled = false;
                convertBtn.textContent = 'Convert & Download';
            }
        });
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

// CAP handling functions
async function parseCAPXML(xml) {
    const output = document.getElementById('cap-parse-output');
    output.innerHTML = '<div class="loading"></div> Parsing CAP...';

    try {
        const res = await fetch('/api/cap/parse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ xml })
        });

        const data = await res.json();

        if (!data.success) {
            output.innerHTML = `<div class="status error">${data.error}</div>`;
            return;
        }

        const alert = data.alert;
        const info = alert.info[0] || {};

        output.innerHTML = `
            <div class="status success">CAP alert parsed successfully</div>
            <div class="decoded-message">
                <span class="type-badge header">CAP Alert</span>
                <div class="field">
                    <span class="field-label">Identifier:</span>
                    <span class="field-value">${alert.identifier}</span>
                </div>
                <div class="field">
                    <span class="field-label">Sender:</span>
                    <span class="field-value">${alert.sender}</span>
                </div>
                <div class="field">
                    <span class="field-label">Sent:</span>
                    <span class="field-value">${alert.sent}</span>
                </div>
                <div class="field">
                    <span class="field-label">Status:</span>
                    <span class="field-value">${alert.status}</span>
                </div>
                <div class="field">
                    <span class="field-label">Message Type:</span>
                    <span class="field-value">${alert.msg_type}</span>
                </div>
                ${info.event ? `
                <div class="field">
                    <span class="field-label">Event:</span>
                    <span class="field-value">${info.event}</span>
                </div>
                ` : ''}
                ${info.urgency ? `
                <div class="field">
                    <span class="field-label">Urgency:</span>
                    <span class="field-value">${info.urgency}</span>
                </div>
                ` : ''}
                ${info.severity ? `
                <div class="field">
                    <span class="field-label">Severity:</span>
                    <span class="field-value">${info.severity}</span>
                </div>
                ` : ''}
                ${info.headline ? `
                <div class="field">
                    <span class="field-label">Headline:</span>
                    <span class="field-value">${info.headline}</span>
                </div>
                ` : ''}
                ${info.description ? `
                <div class="field" style="flex-direction: column;">
                    <span class="field-label">Description:</span>
                    <span class="field-value" style="margin-top: 4px; white-space: pre-wrap;">${info.description}</span>
                </div>
                ` : ''}
                ${info.areas && info.areas.length > 0 ? `
                <div class="field">
                    <span class="field-label">Areas:</span>
                    <span class="field-value">${info.areas.map(a => a.area_desc).join('; ')}</span>
                </div>
                ` : ''}
                ${Object.keys(info.event_codes || {}).length > 0 ? `
                <div class="field">
                    <span class="field-label">Event Codes:</span>
                    <span class="field-value">${Object.entries(info.event_codes).map(([k,v]) => `${k}=${v}`).join(', ')}</span>
                </div>
                ` : ''}
            </div>
        `;
    } catch (e) {
        output.innerHTML = `<div class="status error">Parse failed: ${e.message}</div>`;
    }
}

async function convertCAPToSAME(xml, callsign) {
    const output = document.getElementById('cap-parse-output');
    output.innerHTML = '<div class="loading"></div> Converting to SAME...';

    try {
        const res = await fetch('/api/cap/to-same', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ xml, callsign, include_audio: true })
        });

        const data = await res.json();

        if (!data.success) {
            let errorHtml = `<div class="status error">${data.error}</div>`;
            if (data.issues && data.issues.length > 0) {
                errorHtml += `<ul style="color: var(--text-secondary); margin-top: 10px;">`;
                data.issues.forEach(issue => {
                    errorHtml += `<li>${issue}</li>`;
                });
                errorHtml += `</ul>`;
            }
            output.innerHTML = errorHtml;
            return;
        }

        let html = `
            <div class="status success">Converted to SAME successfully</div>
            <div class="header-display">${data.header}</div>
            <div class="decoded-message">
                <div class="field">
                    <span class="field-label">Originator:</span>
                    <span class="field-value">${data.parsed.originator}</span>
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
                    <span class="field-value">${data.parsed.purge_time.substring(0,2)}h ${data.parsed.purge_time.substring(2)}m</span>
                </div>
            </div>
        `;

        if (data.validation_issues && data.validation_issues.length > 0) {
            html += `<div style="color: var(--accent-amber); margin-top: 10px; font-size: 0.85rem;">`;
            html += `<strong>Notes:</strong><ul>`;
            data.validation_issues.forEach(issue => {
                html += `<li>${issue}</li>`;
            });
            html += `</ul></div>`;
        }

        if (data.audio) {
            const audioUrl = `data:audio/wav;base64,${data.audio}`;
            html += `
                <div class="audio-container">
                    <label>Generated Audio</label>
                    <audio controls src="${audioUrl}"></audio>
                    <div style="margin-top: 10px;">
                        <a href="${audioUrl}" download="cap_converted.wav" class="btn btn-secondary">Download WAV</a>
                    </div>
                </div>
            `;
        }

        output.innerHTML = html;
    } catch (e) {
        output.innerHTML = `<div class="status error">Conversion failed: ${e.message}</div>`;
    }
}

async function convertSAMEToCAP(header) {
    const output = document.getElementById('cap-export-output');
    output.innerHTML = '<div class="loading"></div> Generating CAP...';

    const headline = document.getElementById('cap-headline').value;
    const sender = document.getElementById('cap-sender').value;
    const description = document.getElementById('cap-description').value;

    try {
        const res = await fetch('/api/cap/from-same', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ header, headline, sender, description })
        });

        const data = await res.json();

        if (!data.success) {
            output.innerHTML = `<div class="status error">${data.error}</div>`;
            return;
        }

        // escape XML for display
        const escapedXml = data.cap_xml
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        output.innerHTML = `
            <div class="status success">CAP XML generated successfully</div>
            <div class="form-group">
                <label>CAP XML Output</label>
                <pre class="cap-xml-output">${escapedXml}</pre>
            </div>
            <button class="btn btn-secondary" id="copy-cap-xml">Copy to Clipboard</button>
        `;

        document.getElementById('copy-cap-xml')?.addEventListener('click', () => {
            navigator.clipboard.writeText(data.cap_xml).then(() => {
                const btn = document.getElementById('copy-cap-xml');
                btn.textContent = 'Copied!';
                setTimeout(() => { btn.textContent = 'Copy to Clipboard'; }, 2000);
            });
        });
    } catch (e) {
        output.innerHTML = `<div class="status error">Generation failed: ${e.message}</div>`;
    }
}

// NWS Live Feed functions
async function fetchNWSAlerts() {
    const output = document.getElementById('nws-alerts-output');
    const summaryDiv = document.getElementById('nws-summary');
    output.innerHTML = '<div class="loading"></div> Fetching alerts from NWS...';
    summaryDiv.innerHTML = '';

    const stateFilter = document.getElementById('nws-state-filter').value;
    const severityFilter = document.getElementById('nws-severity-filter').value;
    const limit = document.getElementById('nws-limit').value;

    try {
        let url = `/api/nws/alerts?limit=${limit}`;
        if (stateFilter) url += `&state=${stateFilter}`;
        if (severityFilter) url += `&severity=${severityFilter}`;

        const res = await fetch(url);
        const data = await res.json();

        if (!data.success) {
            output.innerHTML = `<div class="status error">${data.error}</div>`;
            return;
        }

        if (data.count === 0) {
            output.innerHTML = '<div class="status success">No active alerts matching filters</div>';
            return;
        }

        // show summary
        const severityCounts = {};
        data.alerts.forEach(alert => {
            const sev = alert.severity || 'Unknown';
            severityCounts[sev] = (severityCounts[sev] || 0) + 1;
        });

        summaryDiv.innerHTML = `
            <div class="nws-summary-inner">
                <span class="summary-count">${data.count} alerts</span>
                ${Object.entries(severityCounts).map(([sev, count]) =>
                    `<span class="severity-badge severity-${sev.toLowerCase()}">${sev}: ${count}</span>`
                ).join('')}
            </div>
        `;

        // render alerts
        output.innerHTML = data.alerts.map(alert => renderNWSAlert(alert)).join('');

        // add click handlers for expand/collapse
        output.querySelectorAll('.nws-alert-header').forEach(header => {
            header.addEventListener('click', () => {
                header.parentElement.classList.toggle('expanded');
            });
        });

    } catch (e) {
        output.innerHTML = `<div class="status error">Fetch failed: ${e.message}</div>`;
    }
}

function renderNWSAlert(alert) {
    const severityClass = alert.severity ? `severity-${alert.severity.toLowerCase()}` : '';
    const urgencyClass = alert.urgency === 'Immediate' ? 'urgency-immediate' : '';

    const expires = alert.expires ? new Date(alert.expires).toLocaleString() : 'N/A';
    const sent = alert.sent ? new Date(alert.sent).toLocaleString() : 'N/A';

    return `
        <div class="nws-alert ${severityClass} ${urgencyClass}">
            <div class="nws-alert-header">
                <div class="nws-alert-event">${alert.event}</div>
                <div class="nws-alert-meta">
                    <span class="severity-badge ${severityClass}">${alert.severity || 'Unknown'}</span>
                    <span class="urgency-badge">${alert.urgency || 'Unknown'}</span>
                </div>
            </div>
            <div class="nws-alert-body">
                <div class="nws-alert-headline">${alert.headline || ''}</div>
                <div class="nws-alert-details">
                    <div class="field">
                        <span class="field-label">Area:</span>
                        <span class="field-value">${alert.area_desc}</span>
                    </div>
                    <div class="field">
                        <span class="field-label">Sent:</span>
                        <span class="field-value">${sent}</span>
                    </div>
                    <div class="field">
                        <span class="field-label">Expires:</span>
                        <span class="field-value">${expires}</span>
                    </div>
                    <div class="field">
                        <span class="field-label">Sender:</span>
                        <span class="field-value">${alert.sender_name || alert.sender}</span>
                    </div>
                    ${alert.same_codes && alert.same_codes.length > 0 ? `
                    <div class="field">
                        <span class="field-label">SAME Codes:</span>
                        <span class="field-value">${alert.same_codes.join(', ')}</span>
                    </div>
                    ` : ''}
                </div>
                ${alert.description ? `
                <div class="nws-alert-description">
                    <strong>Description:</strong>
                    <p>${alert.description.substring(0, 500)}${alert.description.length > 500 ? '...' : ''}</p>
                </div>
                ` : ''}
                ${alert.instruction ? `
                <div class="nws-alert-instruction">
                    <strong>Instructions:</strong>
                    <p>${alert.instruction.substring(0, 300)}${alert.instruction.length > 300 ? '...' : ''}</p>
                </div>
                ` : ''}
            </div>
        </div>
    `;
}

// ENDEC Emulation functions
const endecState = {
    serialLog: [],
    alertActive: false
};

function addSerialLine(text) {
    const timestamp = new Date().toLocaleTimeString([], { hour12: false });
    endecState.serialLog.push(`[${timestamp}] ${text}`);
    if (endecState.serialLog.length > 50) {
        endecState.serialLog.shift();
    }
    const serial = document.getElementById('endec-serial');
    if (serial) {
        serial.innerHTML = endecState.serialLog.map(line =>
            `<div class="serial-line">${line}</div>`
        ).join('');
        serial.scrollTop = serial.scrollHeight;
    }
}

function setLED(id, on) {
    const indicator = document.getElementById(id);
    if (indicator) {
        const led = indicator.querySelector('.led');
        if (led) {
            led.classList.toggle('on', on);
        }
    }
}

function setLCD(line1, line2) {
    const lcd1 = document.getElementById('lcd-line1');
    const lcd2 = document.getElementById('lcd-line2');
    if (lcd1) lcd1.textContent = line1;
    if (lcd2) lcd2.textContent = line2 || '';
}

async function simulateENDECReceive(header) {
    if (endecState.alertActive) return;
    endecState.alertActive = true;

    // parse header for display
    let eventCode = 'UNK';
    let originator = 'UNK';
    const match = header.match(/ZCZC-([A-Z]{3})-([A-Z]{3})/);
    if (match) {
        originator = match[1];
        eventCode = match[2];
    }

    addSerialLine('RX: PREAMBLE DETECTED');
    setLED('led-alert', true);
    setLCD('RECEIVING...', 'HEADER 1/3');

    await sleep(500);
    addSerialLine(`RX: ${header}`);
    setLCD('RECEIVING...', 'HEADER 2/3');

    await sleep(500);
    addSerialLine(`RX: ${header}`);
    setLCD('RECEIVING...', 'HEADER 3/3');

    await sleep(500);
    addSerialLine(`RX: ${header}`);
    addSerialLine('RX: HEADER VALID - 3/3 MATCH');

    // decode and display
    setLCD(`${originator}-${eventCode}`, 'ALERT RECEIVED');
    addSerialLine(`DECODE: ORG=${originator} EVT=${eventCode}`);

    await sleep(300);
    setLED('led-attn', true);
    addSerialLine('ATTN: TONE DETECTED (853+960Hz)');
    setLCD(`${originator}-${eventCode}`, 'ATTN SIGNAL');

    await sleep(2000);
    setLED('led-attn', false);

    // check for EOM
    await sleep(1000);
    addSerialLine('RX: PREAMBLE DETECTED');
    addSerialLine('RX: NNNN');
    addSerialLine('RX: NNNN');
    addSerialLine('RX: NNNN');
    addSerialLine('RX: EOM VALID - 3/3 MATCH');
    setLCD(`${originator}-${eventCode}`, 'EOM RECEIVED');

    await sleep(500);
    setLED('led-alert', false);
    setLCD('ALERT COMPLETE', 'PENDING FWD');
    addSerialLine('STATUS: ALERT PENDING FORWARD');

    endecState.alertActive = false;
}

async function simulateENDECTest() {
    if (endecState.alertActive) return;
    endecState.alertActive = true;

    setLCD('RWT TEST', 'GENERATING...');
    addSerialLine('CMD: GENERATE RWT');
    setLED('led-tx', true);

    await sleep(300);
    addSerialLine('TX: PREAMBLE (16 BYTES)');
    addSerialLine('TX: ZCZC-EAS-RWT-000000+0015-0000000-EASWEB--');
    setLCD('TRANSMITTING', 'HEADER 1/3');

    await sleep(500);
    addSerialLine('TX: PREAMBLE (16 BYTES)');
    addSerialLine('TX: ZCZC-EAS-RWT-000000+0015-0000000-EASWEB--');
    setLCD('TRANSMITTING', 'HEADER 2/3');

    await sleep(500);
    addSerialLine('TX: PREAMBLE (16 BYTES)');
    addSerialLine('TX: ZCZC-EAS-RWT-000000+0015-0000000-EASWEB--');
    setLCD('TRANSMITTING', 'HEADER 3/3');

    await sleep(500);
    setLED('led-attn', true);
    addSerialLine('TX: ATTENTION SIGNAL (8s)');
    setLCD('TRANSMITTING', 'ATTN SIGNAL');

    await sleep(2000);
    setLED('led-attn', false);

    addSerialLine('TX: PREAMBLE (16 BYTES)');
    addSerialLine('TX: NNNN');
    setLCD('TRANSMITTING', 'EOM 1/3');

    await sleep(500);
    addSerialLine('TX: PREAMBLE (16 BYTES)');
    addSerialLine('TX: NNNN');
    setLCD('TRANSMITTING', 'EOM 2/3');

    await sleep(500);
    addSerialLine('TX: PREAMBLE (16 BYTES)');
    addSerialLine('TX: NNNN');
    setLCD('TRANSMITTING', 'EOM 3/3');

    await sleep(300);
    setLED('led-tx', false);
    addSerialLine('TX: COMPLETE');
    setLCD('RWT COMPLETE', 'READY');

    endecState.alertActive = false;
}

function clearENDEC() {
    setLED('led-alert', false);
    setLED('led-attn', false);
    setLED('led-fwd', false);
    setLED('led-tx', false);
    setLCD('READY', 'MONITORING...');
    addSerialLine('CMD: CLEAR');
    endecState.alertActive = false;
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// WEA Preview functions
function generateWEAPreview() {
    const alertType = document.getElementById('wea-alert-type').value;
    const message = document.getElementById('wea-message').value || 'Emergency Alert';
    const source = document.getElementById('wea-source').value || 'Government';

    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });

    const alertTypeLabels = {
        'EXTREME': 'Extreme Alert',
        'SEVERE': 'Severe Alert',
        'AMBER': 'AMBER Alert',
        'PUBLIC_SAFETY': 'Public Safety Alert',
        'TEST': 'Test Alert'
    };

    const alertLabel = alertTypeLabels[alertType] || 'Emergency Alert';

    // iOS style alert
    const iosAlert = document.getElementById('ios-alert');
    if (iosAlert) {
        iosAlert.innerHTML = `
            <div class="ios-wea-popup">
                <div class="ios-wea-header">
                    <div class="ios-wea-icon">⚠️</div>
                    <div class="ios-wea-title">
                        <div class="ios-wea-label">${alertLabel.toUpperCase()}</div>
                        <div class="ios-wea-subtitle">${source}</div>
                    </div>
                </div>
                <div class="ios-wea-body">
                    ${message}
                </div>
                <div class="ios-wea-time">${timeStr}</div>
                <div class="ios-wea-actions">
                    <button class="ios-btn">Dismiss</button>
                </div>
            </div>
        `;
    }

    // Android style alert
    const androidAlert = document.getElementById('android-alert');
    if (androidAlert) {
        androidAlert.innerHTML = `
            <div class="android-wea-popup ${alertType.toLowerCase()}">
                <div class="android-wea-header">
                    <span class="android-wea-icon">⚠</span>
                    <span class="android-wea-label">${alertLabel}</span>
                </div>
                <div class="android-wea-body">
                    ${message}
                </div>
                <div class="android-wea-footer">
                    <span class="android-wea-source">${source}</span>
                    <span class="android-wea-time">${timeStr}</span>
                </div>
                <div class="android-wea-actions">
                    <button class="android-btn">OK</button>
                </div>
            </div>
        `;
    }
}

// Batch processing functions
let currentBatchFile = null;
let currentBatchJobId = null;

function handleBatchFileSelect(file) {
    currentBatchFile = file;
    const dropzone = document.getElementById('batch-dropzone');
    if (dropzone) {
        dropzone.querySelector('.dropzone-content').innerHTML = `
            <span class="dropzone-icon">✓</span>
            <span>${file.name} (${(file.size / 1024).toFixed(1)} KB)</span>
        `;
    }
    document.getElementById('start-batch-job').disabled = false;
}

async function startBatchProcessing() {
    if (!currentBatchFile) return;

    const formData = new FormData();
    formData.append('file', currentBatchFile);

    const statusDiv = document.getElementById('batch-job-status');
    const resultsDiv = document.getElementById('batch-results');
    statusDiv.style.display = 'block';
    resultsDiv.innerHTML = '';

    try {
        // upload and create job
        const uploadRes = await fetch('/api/batch/upload', {
            method: 'POST',
            body: formData
        });
        const uploadData = await uploadRes.json();

        if (!uploadData.success) {
            throw new Error(uploadData.error);
        }

        currentBatchJobId = uploadData.job_id;
        document.getElementById('batch-status-text').textContent = 'Uploaded';
        document.getElementById('batch-progress-text').textContent = `0/${uploadData.alert_count}`;

        // start processing
        await fetch(`/api/batch/job/${currentBatchJobId}/start`, { method: 'POST' });
        document.getElementById('batch-status-text').textContent = 'Processing';

        // poll for status
        pollBatchStatus();

    } catch (e) {
        document.getElementById('batch-status-text').textContent = 'Error';
        resultsDiv.innerHTML = `<div class="status error">${e.message}</div>`;
    }
}

async function pollBatchStatus() {
    if (!currentBatchJobId) return;

    try {
        const res = await fetch(`/api/batch/job/${currentBatchJobId}`);
        const data = await res.json();

        if (!data.success) return;

        const job = data.job;
        document.getElementById('batch-status-text').textContent = job.status;
        document.getElementById('batch-progress').style.width = `${job.progress}%`;
        document.getElementById('batch-progress-text').textContent = `${job.current_index}/${job.total_count}`;
        document.getElementById('batch-errors-count').textContent = job.errors_count;

        if (job.status === 'completed' || job.status === 'failed') {
            // load results
            loadBatchResults();
        } else if (job.status === 'processing') {
            setTimeout(pollBatchStatus, 1000);
        }
    } catch (e) {
        console.error('Poll error:', e);
    }
}

async function loadBatchResults() {
    if (!currentBatchJobId) return;

    try {
        const res = await fetch(`/api/batch/job/${currentBatchJobId}/results`);
        const data = await res.json();

        if (!data.success) return;

        const resultsDiv = document.getElementById('batch-results');
        if (data.results.length === 0) {
            resultsDiv.innerHTML = '<div class="status">No results generated</div>';
            return;
        }

        resultsDiv.innerHTML = `
            <h4>Generated ${data.results.length} alerts</h4>
            <div class="batch-results-list">
                ${data.results.map((r, i) => `
                    <div class="batch-result-item">
                        <span class="result-index">#${i + 1}</span>
                        <span class="result-header">${r.header || 'Error'}</span>
                        ${r.audio ? `
                            <audio controls src="data:audio/wav;base64,${r.audio}"></audio>
                            <a href="data:audio/wav;base64,${r.audio}" download="batch_${i + 1}.wav" class="btn btn-small">↓</a>
                        ` : ''}
                        ${r.error ? `<span class="result-error">${r.error}</span>` : ''}
                    </div>
                `).join('')}
            </div>
        `;
    } catch (e) {
        console.error('Load results error:', e);
    }
}

function downloadBatchTemplate() {
    const csvContent = `originator,event,locations,duration,callsign,attention_duration,voice_text
WXR,TOR,029095,30,WXYZ/FM,8,
WXR,SVR,"029095 029097",45,WXYZ/FM,8,
EAS,RWT,000000,15,TEST/FM,8,This is a required weekly test`;

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'batch_template.csv';
    a.click();
    URL.revokeObjectURL(url);
}

// Archive functions
async function searchArchive() {
    const event = document.getElementById('archive-event-filter')?.value;
    const originator = document.getElementById('archive-originator-filter')?.value;
    const hasVoice = document.getElementById('archive-voice-filter')?.value;
    const startDate = document.getElementById('archive-start-date')?.value;
    const endDate = document.getElementById('archive-end-date')?.value;

    const resultsDiv = document.getElementById('archive-results');
    resultsDiv.innerHTML = '<div class="loading"></div> Searching...';

    const params = new URLSearchParams();
    if (event) params.append('event', event);
    if (originator) params.append('originator', originator);
    if (hasVoice) params.append('has_voice', hasVoice);
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);

    try {
        const res = await fetch(`/api/archive/alerts?${params}`);
        const data = await res.json();

        if (!data.success) {
            resultsDiv.innerHTML = `<div class="status error">${data.error}</div>`;
            return;
        }

        if (data.alerts.length === 0) {
            resultsDiv.innerHTML = '<div class="status">No alerts found</div>';
            return;
        }

        resultsDiv.innerHTML = `
            <h4>Found ${data.alerts.length} alerts</h4>
            <div class="archive-list">
                ${data.alerts.map(alert => `
                    <div class="archive-item">
                        <div class="archive-item-header">
                            <span class="archive-event">${alert.event}</span>
                            <span class="archive-originator">${alert.originator}</span>
                            <span class="archive-date">${new Date(alert.created_at).toLocaleString()}</span>
                        </div>
                        <div class="archive-item-body">
                            <code>${alert.header}</code>
                        </div>
                        <div class="archive-item-actions">
                            ${alert.has_audio ? `
                                <button class="btn btn-small" onclick="playArchiveAlert(${alert.id})">▶ Play</button>
                                <button class="btn btn-small" onclick="downloadArchiveAlert(${alert.id})">↓ Download</button>
                            ` : ''}
                            <button class="btn btn-small btn-danger" onclick="deleteArchiveAlert(${alert.id})">🗑</button>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    } catch (e) {
        resultsDiv.innerHTML = `<div class="status error">${e.message}</div>`;
    }
}

async function loadArchiveStats() {
    const statsDiv = document.getElementById('archive-stats');
    statsDiv.style.display = 'block';
    statsDiv.innerHTML = '<div class="loading"></div> Loading stats...';

    try {
        const res = await fetch('/api/archive/stats');
        const data = await res.json();

        if (!data.success) {
            statsDiv.innerHTML = `<div class="status error">${data.error}</div>`;
            return;
        }

        const stats = data.stats;
        statsDiv.innerHTML = `
            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-value">${stats.total_count}</div>
                    <div class="stat-label">Total Alerts</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${stats.voice_count}</div>
                    <div class="stat-label">With Voice</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${Object.keys(stats.event_counts).length}</div>
                    <div class="stat-label">Event Types</div>
                </div>
            </div>
            <div class="stats-breakdown">
                <h5>Top Events</h5>
                ${Object.entries(stats.event_counts).slice(0, 5).map(([code, count]) =>
                    `<div class="stat-row"><span>${code}</span><span>${count}</span></div>`
                ).join('')}
            </div>
        `;
    } catch (e) {
        statsDiv.innerHTML = `<div class="status error">${e.message}</div>`;
    }
}

async function playArchiveAlert(alertId) {
    try {
        const res = await fetch(`/api/archive/alerts/${alertId}?include_audio=true`);
        const data = await res.json();
        if (data.success && data.alert.audio) {
            const audio = new Audio(`data:audio/wav;base64,${data.alert.audio}`);
            audio.play();
        }
    } catch (e) {
        console.error('Play error:', e);
    }
}

async function downloadArchiveAlert(alertId) {
    try {
        const res = await fetch(`/api/archive/alerts/${alertId}?include_audio=true`);
        const data = await res.json();
        if (data.success && data.alert.audio) {
            const a = document.createElement('a');
            a.href = `data:audio/wav;base64,${data.alert.audio}`;
            a.download = `alert_${alertId}.wav`;
            a.click();
        }
    } catch (e) {
        console.error('Download error:', e);
    }
}

async function deleteArchiveAlert(alertId) {
    if (!confirm('Delete this alert from archive?')) return;

    try {
        const res = await fetch(`/api/archive/alerts/${alertId}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            searchArchive(); // refresh list
        }
    } catch (e) {
        console.error('Delete error:', e);
    }
}

// Cascade visualization animation
const cascadeState = {
    running: false,
    timeline: []
};

function setNodeStatus(nodeId, status, message) {
    const node = document.getElementById(nodeId);
    if (!node) return;

    const statusEl = node.querySelector('.node-status');
    if (statusEl) {
        statusEl.textContent = status;
    }

    // visual feedback
    node.classList.remove('active', 'transmitting', 'received');
    if (status.includes('TRANSMIT') || status.includes('FORWARD')) {
        node.classList.add('transmitting');
    } else if (status.includes('RECEIVED') || status.includes('ALERT')) {
        node.classList.add('received');
    } else if (status.includes('ACTIVE')) {
        node.classList.add('active');
    }
}

function addTimelineEvent(time, event) {
    cascadeState.timeline.push({ time, event });
    updateTimeline();
}

function updateTimeline() {
    const timeline = document.getElementById('cascade-timeline');
    if (!timeline) return;

    timeline.innerHTML = `
        <div class="timeline-header">Cascade Timeline</div>
        ${cascadeState.timeline.map(({ time, event }) => `
            <div class="timeline-entry">
                <span class="timeline-time">T+${time}s</span>
                <span class="timeline-event">${event}</span>
            </div>
        `).join('')}
    `;
    timeline.scrollTop = timeline.scrollHeight;
}

async function startCascadeAnimation(event, originator) {
    if (cascadeState.running) return;
    cascadeState.running = true;
    cascadeState.timeline = [];

    const timeline = document.getElementById('cascade-timeline');
    if (timeline) {
        timeline.innerHTML = '<div class="timeline-header">Cascade Timeline</div>';
    }

    // reset all nodes
    ['node-origin', 'node-lp1-1', 'node-lp1-2', 'node-lp1-3',
     'node-lp2-1', 'node-lp2-2', 'node-lp2-3', 'node-lp2-4', 'node-public'].forEach(id => {
        const node = document.getElementById(id);
        if (node) {
            node.classList.remove('active', 'transmitting', 'received');
            const status = node.querySelector('.node-status');
            if (status) {
                if (id === 'node-origin') status.textContent = 'READY';
                else if (id === 'node-public') status.textContent = 'STANDBY';
                else status.textContent = 'MONITORING';
            }
        }
    });

    const eventName = state.eventCodes[event]?.name || event;

    // T+0: Origin transmits
    addTimelineEvent(0, `${originator} originates ${event} alert`);
    setNodeStatus('node-origin', 'TRANSMITTING', null);
    await sleep(800);

    // T+1: LP1 stations receive
    addTimelineEvent(1, 'LP1 stations receive alert');
    setNodeStatus('node-origin', 'ACTIVE', null);
    setNodeStatus('node-lp1-1', 'RECEIVED', null);
    setNodeStatus('node-lp1-2', 'RECEIVED', null);
    setNodeStatus('node-lp1-3', 'RECEIVED', null);
    await sleep(1000);

    // T+2: LP1 validates and prepares forward
    addTimelineEvent(2, 'LP1 stations decode and validate');
    await sleep(500);

    // T+3: LP1 forwards to LP2
    addTimelineEvent(3, 'LP1 stations forward to LP2');
    setNodeStatus('node-lp1-1', 'FORWARDING', null);
    setNodeStatus('node-lp1-2', 'FORWARDING', null);
    setNodeStatus('node-lp1-3', 'FORWARDING', null);
    await sleep(800);

    // T+4: LP2 receives
    addTimelineEvent(4, 'LP2 stations receive forwarded alert');
    setNodeStatus('node-lp1-1', 'ACTIVE', null);
    setNodeStatus('node-lp1-2', 'ACTIVE', null);
    setNodeStatus('node-lp1-3', 'ACTIVE', null);
    setNodeStatus('node-lp2-1', 'RECEIVED', null);
    setNodeStatus('node-lp2-2', 'RECEIVED', null);
    setNodeStatus('node-lp2-3', 'RECEIVED', null);
    setNodeStatus('node-lp2-4', 'RECEIVED', null);
    await sleep(1000);

    // T+5: LP2 decodes
    addTimelineEvent(5, 'LP2 stations decode and validate');
    await sleep(500);

    // T+6: LP2 broadcasts to public
    addTimelineEvent(6, 'LP2 stations broadcast to public');
    setNodeStatus('node-lp2-1', 'BROADCASTING', null);
    setNodeStatus('node-lp2-2', 'BROADCASTING', null);
    setNodeStatus('node-lp2-3', 'BROADCASTING', null);
    setNodeStatus('node-lp2-4', 'BROADCASTING', null);
    await sleep(800);

    // T+7: Public receives
    addTimelineEvent(7, 'Public receives alert');
    setNodeStatus('node-public', 'ALERT ACTIVE', null);
    setNodeStatus('node-lp2-1', 'ACTIVE', null);
    setNodeStatus('node-lp2-2', 'ACTIVE', null);
    setNodeStatus('node-lp2-3', 'ACTIVE', null);
    setNodeStatus('node-lp2-4', 'ACTIVE', null);
    await sleep(1500);

    // T+9: Complete
    addTimelineEvent(9, `${eventName} - cascade complete`);

    cascadeState.running = false;
}
