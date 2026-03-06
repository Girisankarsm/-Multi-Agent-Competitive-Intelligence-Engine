/**
 * Compy API client — fetch wrapper + SSE helper with polling fallback
 */

const API_BASE = '/api';

async function request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const config = {
        headers: { 'Content-Type': 'application/json', ...options.headers },
        ...options,
    };

    if (config.body && typeof config.body === 'object') {
        config.body = JSON.stringify(config.body);
    }

    const res = await fetch(url, config);
    if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || `API error: ${res.status}`);
    }
    return res.json();
}

// --- Company ---
export const analyzeCompany = (url) =>
    request('/company/analyze', { method: 'POST', body: { url } });

export const getCompany = (id) =>
    request(`/company/${id}`);

export const listCompanies = () =>
    request('/company/');

// --- Competitor ---
export const addCompetitor = (url, companyId) =>
    request('/competitor/add', { method: 'POST', body: { url, company_id: companyId } });

export const getCompetitor = (id) =>
    request(`/competitor/${id}`);

export const listCompetitors = (companyId) =>
    request(`/competitor/company/${companyId}`);

// --- Analysis ---
export const runAnalysis = (competitorId) =>
    request(`/analysis/run/${competitorId}`, { method: 'POST' });

export const getSignals = (competitorId) =>
    request(`/analysis/${competitorId}/signals`);

// --- Plan ---
export const generatePlan = (competitorId) =>
    request(`/plan/generate/${competitorId}`, { method: 'POST' });

export const getPlan = (competitorId) =>
    request(`/plan/${competitorId}`);

// --- Monitor ---
export const setMonitor = (competitorId, schedule, isActive) =>
    request(`/monitor/${competitorId}`, {
        method: 'POST',
        body: { schedule, is_active: isActive },
    });

export const getMonitor = (competitorId) =>
    request(`/monitor/${competitorId}`);

export const getAlerts = (competitorId) =>
    request(`/monitor/${competitorId}/alerts`);

// --- Compare ---
export const compareCompetitors = (competitorIds) =>
    request(`/compare?competitor_ids=${competitorIds.join(',')}`);

// --- Sales ---
export const generateSalesSequence = (competitorId, data) =>
    request(`/sales/generate/${competitorId}`, { method: 'POST', body: data });

export const sendSalesEmail = (recipientEmail, subject, body) =>
    request('/sales/send', { method: 'POST', body: { recipient_email: recipientEmail, subject, body } });

// --- Voice ---
export const triggerVoiceCall = (competitorId) =>
    request('/voice/call', { method: 'POST', body: { competitor_id: competitorId } });

// --- Chat ---
export const sendChatMessage = (competitorId, context, history, message) =>
    request('/chat', { method: 'POST', body: { competitor_id: competitorId, context, history, message } });
// --- SSE Helper with job_id ---
export function subscribeToStream(competitorId, onEvent, jobId = null) {
    // Use job_id endpoint if available (more reliable), otherwise fall back to competitor_id
    const sseUrl = jobId
        ? `${API_BASE}/competitor/job/${jobId}/stream`
        : `${API_BASE}/competitor/${competitorId}/stream`;

    let eventSource;
    let closed = false;
    let reconnectAttempts = 0;
    const MAX_RECONNECTS = 3;

    function connect() {
        if (closed) return;

        eventSource = new EventSource(sseUrl);

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                // Skip keepalive pings
                if (data.event === 'ping') return;

                onEvent(data);
                reconnectAttempts = 0; // Reset on successful message

                if (data.event === 'done') {
                    closed = true;
                    eventSource.close();
                }
            } catch (e) {
                console.warn('SSE parse error:', e);
            }
        };

        eventSource.onerror = () => {
            eventSource.close();
            reconnectAttempts++;

            if (reconnectAttempts <= MAX_RECONNECTS && !closed) {
                // Try reconnecting after a delay
                console.log(`SSE reconnecting (attempt ${reconnectAttempts}/${MAX_RECONNECTS})...`);
                setTimeout(connect, 2000);
            } else if (!closed) {
                // Fall back to polling
                console.log('SSE failed, falling back to polling...');
                startPolling();
            }
        };
    }

    function startPolling() {
        if (closed) return;

        const pollInterval = setInterval(async () => {
            try {
                const comp = await getCompetitor(competitorId);
                if (comp.status === 'crawled') {
                    clearInterval(pollInterval);
                    closed = true;
                    onEvent({
                        event: 'done',
                        data: {
                            message: `✅ Crawl complete! Scraped ${comp.page_count} strategic pages.`,
                            total_pages: comp.page_count
                        }
                    });
                } else if (comp.status === 'failed') {
                    clearInterval(pollInterval);
                    closed = true;
                    onEvent({
                        event: 'done',
                        data: { message: '❌ Crawl failed', total_pages: 0 }
                    });
                }
                // Otherwise keep polling
            } catch (e) {
                console.warn('Polling error:', e);
            }
        }, 3000);
    }

    connect();

    return () => {
        closed = true;
        if (eventSource) eventSource.close();
    };
}
