import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { addCompetitor, subscribeToStream, getCompetitor, listCompetitors } from '../utils/api';

export default function CompetitorAdd({
    companyId,
    competitors,
    onCompetitorAdded,
    onCompetitorUpdated,
    onSelectCompetitor,
    activeCompetitorId,
}) {
    const [url, setUrl] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [logs, setLogs] = useState([]);
    const [crawlingCompId, setCrawlingCompId] = useState(null);
    const terminalRef = useRef(null);
    const navigate = useNavigate();

    // Load existing competitors on mount
    useEffect(() => {
        if (!companyId) return;
        listCompetitors(companyId).then((data) => {
            data.forEach((c) => onCompetitorAdded(c));
        }).catch(() => { });
    }, [companyId]);

    // Auto-scroll terminal
    useEffect(() => {
        if (terminalRef.current) {
            terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
        }
    }, [logs]);

    const getLogType = (event) => {
        switch (event) {
            case 'crawl': return 'info';
            case 'classified': return 'success';
            case 'ranking': return 'warning';
            case 'error': return 'error';
            case 'done': return 'success';
            default: return 'default';
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!url.trim()) return;

        setLoading(true);
        setError('');
        setLogs([]);
        setCrawlingCompId(null);

        try {
            const comp = await addCompetitor(url.trim(), companyId);
            onCompetitorAdded(comp);
            onSelectCompetitor(comp.id);
            setCrawlingCompId(comp.id);
            setUrl('');

            const unsubscribe = subscribeToStream(comp.id, (event) => {
                const logEntry = {
                    time: new Date().toLocaleTimeString(),
                    type: getLogType(event.event),
                    message: event.data?.message || '',
                    details: [],
                };
                if (event.data?.page_type) logEntry.details.push(event.data.page_type);
                if (event.data?.strategic_score) logEntry.details.push(event.data.strategic_score);

                setLogs((prev) => [...prev, logEntry]);

                if (event.event === 'done') {
                    setLoading(false);
                    getCompetitor(comp.id).then((updated) => {
                        onCompetitorUpdated(updated);
                    }).catch(() => { });
                }
            }, comp.job_id);

            return () => unsubscribe();
        } catch (err) {
            setError(err.message || 'Failed to add competitor');
            setLoading(false);
        }
    };

    const statusBadge = (status) => {
        switch (status) {
            case 'crawling': return <span className="badge" style={{ background: 'var(--accent-warning)', color: '#000' }}>⏳ Crawling</span>;
            case 'crawled': return <span className="badge badge-opportunity">✅ Ready</span>;
            case 'failed': return <span className="badge badge-threat">❌ Failed</span>;
            default: return <span className="badge">{status}</span>;
        }
    };

    return (
        <div className="animate-fade-in-up">
            {/* Step Indicator */}
            <div className="steps">
                <div className="step completed">✅ 1. Company DNA</div>
                <div className="step-connector" />
                <div className="step active">🕵️ 2. Scout</div>
                <div className="step-connector" />
                <div className="step">🔬 3. Analyze</div>
                <div className="step-connector" />
                <div className="step">📊 4. Dashboard</div>
            </div>

            <h1 className="page-title">Scout Competitors</h1>
            <p className="page-subtitle">
                Add competitor websites. Compy will intelligently crawl and classify their strategic pages.
            </p>

            {/* Existing Competitors List */}
            {competitors.length > 0 && (
                <div className="glass-card--static" style={{ marginBottom: 'var(--space-xl)' }}>
                    <div className="section-title">📋 Your Competitors ({competitors.length})</div>
                    <div className="competitor-list">
                        {competitors.map((comp) => (
                            <div
                                className={`competitor-row ${activeCompetitorId === comp.id ? 'active' : ''}`}
                                key={comp.id}
                                onClick={() => onSelectCompetitor(comp.id)}
                            >
                                <div className="competitor-row-info">
                                    <span className="competitor-row-name">{comp.name || comp.url}</span>
                                    <span className="competitor-row-url">{comp.url}</span>
                                </div>
                                <div className="competitor-row-meta">
                                    {statusBadge(comp.status)}
                                    {comp.page_count > 0 && (
                                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                            {comp.page_count} pages
                                        </span>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* URL Input — always visible */}
            <div className="glass-card--static" style={{ marginBottom: 'var(--space-xl)' }}>
                <div className="section-title">
                    {competitors.length > 0 ? '➕ Add Another Competitor' : '🕵️ Add Your First Competitor'}
                </div>
                <form onSubmit={handleSubmit}>
                    <div className="input-group">
                        <input
                            type="text"
                            className="input"
                            placeholder="https://competitor.com"
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                            disabled={loading}
                            id="competitor-url-input"
                        />
                        <button
                            type="submit"
                            className="btn btn-primary btn-lg"
                            disabled={loading || !url.trim()}
                            id="scout-btn"
                        >
                            {loading ? (
                                <>
                                    <span className="loading-spinner" style={{ width: 20, height: 20, borderWidth: 2 }} />
                                    Scouting...
                                </>
                            ) : (
                                <>🕵️ Start Scout</>
                            )}
                        </button>
                    </div>
                </form>
            </div>

            {error && (
                <div className="glass-card--static" style={{ borderColor: 'var(--accent-danger)', marginBottom: 'var(--space-lg)' }}>
                    <p style={{ color: 'var(--accent-danger)' }}>❌ {error}</p>
                </div>
            )}

            {/* Live Terminal */}
            {logs.length > 0 && (
                <div className="terminal animate-fade-in">
                    <div className="terminal-header">
                        <div className="terminal-dot terminal-dot--red" />
                        <div className="terminal-dot terminal-dot--yellow" />
                        <div className="terminal-dot terminal-dot--green" />
                        <div className="terminal-title">
                            Scout Agent — {loading ? '🔴 LIVE' : '✅ Complete'}
                        </div>
                    </div>
                    <div className="terminal-body" ref={terminalRef}>
                        {logs.map((log, i) => (
                            <div key={i}>
                                <div className={`terminal-line terminal-line--${log.type}`}>
                                    <span style={{ color: 'var(--text-muted)', marginRight: 8 }}>[{log.time}]</span>
                                    {log.message}
                                </div>
                                {log.details.map((detail, j) => (
                                    <div key={j} className="terminal-line terminal-line--default" style={{ paddingLeft: 24 }}>
                                        {detail}
                                    </div>
                                ))}
                            </div>
                        ))}
                        {loading && (
                            <div className="terminal-line terminal-line--info" style={{ animation: 'pulse 1.5s infinite' }}>
                                █ Waiting for next page...
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Navigate to Analysis */}
            {competitors.some((c) => c.status === 'crawled') && (
                <div style={{ marginTop: 'var(--space-xl)', textAlign: 'center' }} className="animate-fade-in-up">
                    <p style={{ marginBottom: 'var(--space-md)', color: 'var(--text-secondary)' }}>
                        ✅ <strong style={{ color: 'var(--accent-success)' }}>{competitors.filter(c => c.status === 'crawled').length}</strong> competitor{competitors.filter(c => c.status === 'crawled').length !== 1 ? 's' : ''} ready for analysis
                        {loading && <span style={{ marginLeft: 8, color: 'var(--accent-warning)' }}>(1 still crawling...)</span>}
                    </p>
                    <button
                        className="btn btn-success btn-lg"
                        onClick={() => navigate('/analysis')}
                        id="go-to-analysis-btn"
                    >
                        🔬 Next: Analyze Intelligence →
                    </button>
                </div>
            )}
        </div>
    );
}
