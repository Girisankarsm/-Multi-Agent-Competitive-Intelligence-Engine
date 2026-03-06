import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { analyzeCompany } from '../utils/api';

export default function Onboarding({ onComplete, companyData }) {
    const [url, setUrl] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const navigate = useNavigate();

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!url.trim()) return;

        setLoading(true);
        setError('');

        try {
            const company = await analyzeCompany(url.trim());
            onComplete(company);
        } catch (err) {
            setError(err.message || 'Failed to analyze company');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="animate-fade-in-up">
            {/* Step Indicator */}
            <div className="steps">
                <div className="step active">🧬 1. Company DNA</div>
                <div className="step-connector" />
                <div className="step">🕵️ 2. Scout</div>
                <div className="step-connector" />
                <div className="step">🔬 3. Analyze</div>
                <div className="step-connector" />
                <div className="step">📊 4. Dashboard</div>
            </div>

            <h1 className="page-title">Tell Compy About Your Company</h1>
            <p className="page-subtitle">
                Enter your company's website URL. Compy will extract your DNA — features, positioning, pricing, and ideal customer profile.
            </p>

            {/* URL Input */}
            <form onSubmit={handleSubmit} style={{ marginBottom: 'var(--space-2xl)' }}>
                <div className="input-group">
                    <input
                        type="text"
                        className="input"
                        placeholder="https://yourcompany.com"
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        disabled={loading}
                        id="company-url-input"
                    />
                    <button
                        type="submit"
                        className="btn btn-primary btn-lg"
                        disabled={loading || !url.trim()}
                        id="analyze-btn"
                    >
                        {loading ? (
                            <>
                                <span className="loading-spinner" style={{ width: 20, height: 20, borderWidth: 2 }} />
                                Analyzing...
                            </>
                        ) : (
                            <>🧬 Extract DNA</>
                        )}
                    </button>
                </div>
            </form>

            {error && (
                <div className="glass-card--static" style={{ borderColor: 'var(--accent-danger)', marginBottom: 'var(--space-lg)' }}>
                    <p style={{ color: 'var(--accent-danger)' }}>❌ {error}</p>
                </div>
            )}

            {loading && (
                <div className="loading-state">
                    <div className="loading-spinner" />
                    <p>Scraping your website and extracting company DNA...</p>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>This takes 15-30 seconds</p>
                </div>
            )}

            {/* Company Profile Display */}
            {companyData && !loading && (
                <div className="animate-fade-in-up">
                    <div className="section-title">
                        <span>✅ Company DNA Extracted</span>
                    </div>

                    <div className="glass-card--static" style={{ marginBottom: 'var(--space-lg)' }}>
                        <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: 'var(--space-sm)' }}>
                            {companyData.name}
                        </h2>
                        <p style={{ color: 'var(--text-secondary)', lineHeight: 1.7 }}>{companyData.summary}</p>
                    </div>

                    <div className="profile-grid stagger-children">
                        {/* Features */}
                        <div className="glass-card--static profile-section">
                            <h3>🔧 Features</h3>
                            <div className="tag-list">
                                {(companyData.features || []).map((f, i) => (
                                    <div className="tag" key={i} title={f.description}>
                                        {f.name || f}
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* ICP */}
                        <div className="glass-card--static profile-section">
                            <h3>🎯 Ideal Customer Profile</h3>
                            {companyData.icp?.segments && (
                                <div style={{ marginBottom: 'var(--space-sm)' }}>
                                    <div className="label">Segments</div>
                                    <div className="tag-list" style={{ marginTop: 4 }}>
                                        {companyData.icp.segments.map((s, i) => (
                                            <div className="tag" key={i}>{s}</div>
                                        ))}
                                    </div>
                                </div>
                            )}
                            {companyData.icp?.pain_points && (
                                <div>
                                    <div className="label" style={{ marginTop: 'var(--space-sm)' }}>Pain Points</div>
                                    <ul style={{ paddingLeft: 'var(--space-md)', marginTop: 4, color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                                        {companyData.icp.pain_points.map((p, i) => (
                                            <li key={i}>{p}</li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </div>

                        {/* Positioning */}
                        <div className="glass-card--static profile-section">
                            <h3>🏆 Positioning</h3>
                            {companyData.positioning?.value_proposition && (
                                <p style={{ color: 'var(--accent-secondary)', fontWeight: 600, marginBottom: 'var(--space-sm)', fontSize: '0.9rem' }}>
                                    "{companyData.positioning.value_proposition}"
                                </p>
                            )}
                            {companyData.positioning?.differentiators && (
                                <div className="tag-list">
                                    {companyData.positioning.differentiators.map((d, i) => (
                                        <div className="tag" key={i}>{d}</div>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Pricing */}
                        <div className="glass-card--static profile-section">
                            <h3>💰 Pricing</h3>
                            {companyData.pricing?.model && (
                                <p style={{ marginBottom: 'var(--space-sm)', color: 'var(--accent-opportunity)', fontSize: '0.9rem', lineHeight: 1.5 }}>
                                    {companyData.pricing.model}
                                </p>
                            )}
                            {(companyData.pricing?.tiers || []).map((tier, i) => (
                                <div key={i} style={{ marginBottom: 'var(--space-xs)', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                                    <strong style={{ color: 'var(--text-primary)' }}>{tier.name}</strong>: {tier.price}
                                </div>
                            ))}
                        </div>
                    </div>

                    <div style={{ marginTop: 'var(--space-xl)', textAlign: 'center' }}>
                        <button
                            className="btn btn-success btn-lg"
                            onClick={() => navigate('/competitor')}
                            id="go-to-scout-btn"
                        >
                            🕵️ Next: Add Competitor →
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
