import { useState, useEffect } from 'react';
import {
    Chart as ChartJS,
    RadialLinearScale,
    PointElement,
    LineElement,
    Filler,
    Tooltip,
    Legend,
} from 'chart.js';
import { Radar } from 'react-chartjs-2';
import { listCompetitors, compareCompetitors } from '../utils/api';

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend);

const RADAR_COLORS = [
    { border: 'rgba(108, 92, 231, 1)', bg: 'rgba(108, 92, 231, 0.15)' },
    { border: 'rgba(255, 107, 107, 1)', bg: 'rgba(255, 107, 107, 0.15)' },
    { border: 'rgba(0, 206, 201, 1)', bg: 'rgba(0, 206, 201, 0.15)' },
    { border: 'rgba(253, 203, 110, 1)', bg: 'rgba(253, 203, 110, 0.15)' },
    { border: 'rgba(0, 184, 148, 1)', bg: 'rgba(0, 184, 148, 0.15)' },
    { border: 'rgba(162, 155, 254, 1)', bg: 'rgba(162, 155, 254, 0.15)' },
];

const RADAR_LABELS = ['Features', 'Pricing', 'Market Position', 'Growth Signals', 'Enterprise', 'Community'];

export default function CompareView({ companyId, companyData }) {
    const [competitors, setCompetitors] = useState([]);
    const [selected, setSelected] = useState([]);
    const [loading, setLoading] = useState(false);
    const [loadingCompetitors, setLoadingCompetitors] = useState(true);
    const [compareData, setCompareData] = useState(null);
    const [error, setError] = useState('');

    // Load all competitors for this company
    useEffect(() => {
        if (!companyId) return;
        setLoadingCompetitors(true);
        listCompetitors(companyId)
            .then((data) => {
                const analyzed = data.filter(c => c.status === 'crawled');
                setCompetitors(analyzed);
                setLoadingCompetitors(false);
            })
            .catch(() => setLoadingCompetitors(false));
    }, [companyId]);

    const toggleSelect = (id) => {
        setSelected((prev) =>
            prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
        );
    };

    const handleCompare = async () => {
        if (selected.length < 2) {
            setError('Select at least 2 competitors to compare');
            return;
        }
        setLoading(true);
        setError('');
        setCompareData(null);
        try {
            const data = await compareCompetitors(selected);
            setCompareData(data);
        } catch (err) {
            setError(err.message || 'Comparison failed');
        } finally {
            setLoading(false);
        }
    };

    // Build radar chart data
    const radarData = compareData ? {
        labels: RADAR_LABELS,
        datasets: compareData.competitors.map((comp, i) => ({
            label: comp.name,
            data: [
                comp.radar.features,
                comp.radar.pricing,
                comp.radar.market_position,
                comp.radar.growth_signals,
                comp.radar.enterprise_readiness,
                comp.radar.community,
            ],
            borderColor: RADAR_COLORS[i % RADAR_COLORS.length].border,
            backgroundColor: RADAR_COLORS[i % RADAR_COLORS.length].bg,
            borderWidth: 2,
            pointBackgroundColor: RADAR_COLORS[i % RADAR_COLORS.length].border,
        })),
    } : null;

    const radarOptions = {
        responsive: true,
        plugins: {
            legend: {
                position: 'bottom',
                labels: { color: '#8b8b9e', font: { family: 'Inter', size: 13 } },
            },
        },
        scales: {
            r: {
                min: 0,
                max: 10,
                ticks: { stepSize: 2, color: '#5a5a6e', backdropColor: 'transparent' },
                grid: { color: 'rgba(255,255,255,0.05)' },
                pointLabels: { color: '#8b8b9e', font: { size: 12, family: 'Inter' } },
            },
        },
    };

    // Collect all unique features across all competitors
    const allFeatures = compareData
        ? [...new Set(compareData.competitors.flatMap(c => Object.keys(c.feature_gaps || {})))]
        : [];

    return (
        <div className="animate-fade-in-up">
            <h1 className="page-title">Side-by-Side Comparison</h1>
            <p className="page-subtitle">
                Compare multiple competitors across strategic dimensions
            </p>

            {/* Competitor Selection */}
            <div className="glass-card--static" style={{ marginBottom: 'var(--space-xl)' }}>
                <div className="section-title">🎯 Select Competitors</div>

                {loadingCompetitors ? (
                    <div className="loading-state" style={{ padding: 'var(--space-lg)' }}>
                        <div className="loading-spinner" />
                        <span>Loading competitors...</span>
                    </div>
                ) : competitors.length === 0 ? (
                    <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: 'var(--space-lg)' }}>
                        No analyzed competitors found. Add and analyze competitors first.
                    </p>
                ) : (
                    <>
                        <div className="compare-checklist">
                            {competitors.map((comp) => (
                                <label
                                    className={`compare-check-item ${selected.includes(comp.id) ? 'selected' : ''}`}
                                    key={comp.id}
                                >
                                    <input
                                        type="checkbox"
                                        checked={selected.includes(comp.id)}
                                        onChange={() => toggleSelect(comp.id)}
                                    />
                                    <span className="compare-check-box">
                                        {selected.includes(comp.id) ? '✓' : ''}
                                    </span>
                                    <div className="compare-check-info">
                                        <span className="compare-check-name">{comp.name || comp.url}</span>
                                        <span className="compare-check-meta">{comp.page_count} pages crawled</span>
                                    </div>
                                </label>
                            ))}
                        </div>

                        <div style={{ marginTop: 'var(--space-md)', display: 'flex', gap: 'var(--space-sm)', alignItems: 'center' }}>
                            <button
                                className="btn btn-primary btn-lg"
                                onClick={handleCompare}
                                disabled={loading || selected.length < 2}
                                id="compare-btn"
                            >
                                {loading ? (
                                    <>
                                        <span className="loading-spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
                                        Comparing...
                                    </>
                                ) : (
                                    `⚡ Compare ${selected.length} Competitor${selected.length !== 1 ? 's' : ''}`
                                )}
                            </button>
                            {selected.length < 2 && selected.length > 0 && (
                                <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                                    Select at least 2
                                </span>
                            )}
                        </div>
                    </>
                )}

                {error && (
                    <p style={{ color: 'var(--accent-danger)', fontSize: '0.85rem', marginTop: 'var(--space-sm)' }}>
                        ❌ {error}
                    </p>
                )}
            </div>

            {/* Results */}
            {compareData && (
                <div className="stagger-children">
                    {/* Radar Chart */}
                    <div className="glass-card--static" style={{ marginBottom: 'var(--space-xl)' }}>
                        <div className="section-title">📊 Strategic Radar</div>
                        <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: 'var(--space-md)' }}>
                            AI-scored comparison across 6 strategic dimensions (0-10)
                        </p>
                        <div style={{ maxWidth: 550, margin: '0 auto' }}>
                            <Radar data={radarData} options={radarOptions} />
                        </div>
                    </div>

                    {/* Feature Gap Matrix */}
                    {allFeatures.length > 0 && (
                        <div className="glass-card--static" style={{ marginBottom: 'var(--space-xl)' }}>
                            <div className="section-title">🧩 Feature Gap Matrix</div>
                            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: 'var(--space-md)' }}>
                                Feature coverage detected from competitor pages
                            </p>
                            <div style={{ overflowX: 'auto' }}>
                                <table className="feature-matrix">
                                    <thead>
                                        <tr>
                                            <th>Feature</th>
                                            {compareData.competitors.map((comp) => (
                                                <th key={comp.id}>{comp.name}</th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {allFeatures.map((feature) => (
                                            <tr key={feature}>
                                                <td className="feature-matrix-label">{feature}</td>
                                                {compareData.competitors.map((comp) => {
                                                    const has = comp.feature_gaps?.[feature];
                                                    return (
                                                        <td
                                                            key={comp.id}
                                                            className={`feature-matrix-cell ${has ? 'has' : 'missing'}`}
                                                        >
                                                            {has ? '✅' : '❌'}
                                                        </td>
                                                    );
                                                })}
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}

                    {/* Competitive Intensity Leaderboard */}
                    <div className="glass-card--static">
                        <div className="section-title">🏆 Competitive Intensity Leaderboard</div>
                        <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: 'var(--space-md)' }}>
                            Higher score = more competitive threat
                        </p>
                        <div className="intensity-leaderboard">
                            {[...compareData.competitors]
                                .sort((a, b) => b.intensity_score - a.intensity_score)
                                .map((comp, i) => (
                                    <div className="intensity-row" key={comp.id}>
                                        <div className="intensity-rank">#{i + 1}</div>
                                        <div className="intensity-info">
                                            <div className="intensity-name">{comp.name}</div>
                                            <div className="intensity-meta">
                                                <span className="badge badge-threat">{comp.threats} threats</span>
                                                <span className="badge badge-opportunity">{comp.opportunities} opps</span>
                                                <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                                                    {comp.signal_count} signals
                                                </span>
                                            </div>
                                        </div>
                                        <div className="intensity-bar-area">
                                            <div className="score-bar-track" style={{ height: 10 }}>
                                                <div
                                                    className="score-bar-fill"
                                                    style={{
                                                        width: `${comp.intensity_score}%`,
                                                        background: comp.intensity_score > 70
                                                            ? 'linear-gradient(90deg, var(--accent-danger), #ff4444)'
                                                            : comp.intensity_score > 40
                                                                ? 'linear-gradient(90deg, var(--accent-warning), #fdcb6e)'
                                                                : 'linear-gradient(90deg, var(--accent-success), #00d2d3)',
                                                    }}
                                                />
                                            </div>
                                            <span className="intensity-score">{comp.intensity_score}</span>
                                        </div>
                                    </div>
                                ))}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
