import { useState, useRef, useEffect } from 'react';
import { sendChatMessage } from '../utils/api';

const SUGGESTED_QUESTIONS = [
    "Write and send a cold email to test@example.com",
    "Why are customers leaving this competitor?",
    "What's their biggest pricing weakness?",
    "Who should we target first?",
];

export default function ChatBot({ competitorId, competitorName, analysisData }) {
    const [isOpen, setIsOpen] = useState(false);
    const [messages, setMessages] = useState([
        {
            role: 'assistant',
            content: `👋 I'm Compy AI — your Competitive Intelligence Analyst. I have a full dossier on **${competitorName || 'your competitor'}**. Ask me anything about their pricing weaknesses, who to target, or how to position against them.`
        }
    ]);
    const [inputValue, setInputValue] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const messagesEndRef = useRef(null);
    const inputRef = useRef(null);

    useEffect(() => {
        if (isOpen) {
            messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
            inputRef.current?.focus();
        }
    }, [messages, isOpen]);

    // Reset chat when competitor changes
    useEffect(() => {
        setMessages([{
            role: 'assistant',
            content: `👋 I'm Compy AI — your Competitive Intelligence Analyst. I have a full dossier on **${competitorName || 'your competitor'}**. Ask me anything about their pricing weaknesses, who to target, or how to position against them.`
        }]);
    }, [competitorId, competitorName]);

    const sendMessage = async (text) => {
        const messageText = text || inputValue.trim();
        if (!messageText || isLoading || !competitorId) return;

        const userMessage = { role: 'user', content: messageText };
        const newMessages = [...messages, userMessage];
        setMessages(newMessages);
        setInputValue('');
        setIsLoading(true);

        // Build history to send (exclude the initial greeting)
        const historyToSend = newMessages.slice(1, -1).map(m => ({
            role: m.role === 'assistant' ? 'assistant' : 'user',
            content: m.content
        }));

        // Build context object
        const context = {
            competitor_name: analysisData?.competitor_name || competitorName || "Unknown",
            competitor_url: "",
            pricing_model: analysisData?.pricing_intelligence?.model || "Unknown",
            pricing_complaints: analysisData?.pricing_intelligence?.pricing_complaints || [],
            community_price_perception: analysisData?.pricing_intelligence?.community_price_perception || "Unknown",
            we_win: (analysisData?.feature_gap_analysis?.we_win || []).map(f => f.feature || f.area || String(f)),
            they_win: (analysisData?.feature_gap_analysis?.they_win || []).map(f => f.feature || f.area || String(f)),
            sentiment_score: String(analysisData?.community_sentiment?.overall_score || "N/A"),
            sentiment_trend: analysisData?.community_sentiment?.sentiment_trend || "N/A",
            top_praise: (analysisData?.community_sentiment?.top_praise || []).map(p => p.point || String(p)),
            top_complaints: (analysisData?.community_sentiment?.top_complaints || []).map(c => c.point || String(c)),
            positioning: typeof analysisData?.positioning === 'string' ? analysisData.positioning : JSON.stringify(analysisData?.positioning || {}),
        };

        try {
            const result = await sendChatMessage(competitorId, context, historyToSend, messageText);
            setMessages(prev => [...prev, { role: 'assistant', content: result.reply }]);
        } catch (err) {
            setMessages(prev => [...prev, { role: 'assistant', content: `❌ Sorry, I hit an error: ${err.message}` }]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    return (
        <>
            {/* Floating Chat Bubble */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                style={{
                    position: 'fixed',
                    bottom: '24px',
                    right: '24px',
                    width: '56px',
                    height: '56px',
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg, var(--accent-primary), #a29bfe)',
                    border: 'none',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '1.5rem',
                    zIndex: 1000,
                    boxShadow: '0 4px 20px rgba(108, 92, 231, 0.5)',
                    transition: 'transform 0.2s ease, box-shadow 0.2s ease',
                }}
                onMouseEnter={e => e.currentTarget.style.transform = 'scale(1.1)'}
                onMouseLeave={e => e.currentTarget.style.transform = 'scale(1)'}
                title="Ask Compy AI"
            >
                {isOpen ? '✕' : '🧠'}
            </button>

            {/* Chat Panel */}
            {isOpen && (
                <div style={{
                    position: 'fixed',
                    bottom: '92px',
                    right: '24px',
                    width: '380px',
                    maxHeight: '550px',
                    borderRadius: '16px',
                    background: 'rgba(15, 15, 25, 0.97)',
                    backdropFilter: 'blur(20px)',
                    border: '1px solid rgba(108, 92, 231, 0.4)',
                    boxShadow: '0 8px 40px rgba(0,0,0,0.5), 0 0 0 1px rgba(108,92,231,0.2)',
                    display: 'flex',
                    flexDirection: 'column',
                    zIndex: 999,
                    overflow: 'hidden',
                }}>
                    {/* Header */}
                    <div style={{
                        padding: '14px 18px',
                        borderBottom: '1px solid rgba(255,255,255,0.06)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        background: 'rgba(108, 92, 231, 0.1)',
                    }}>
                        <span style={{ fontSize: '1.2rem' }}>🧠</span>
                        <div>
                            <div style={{ fontWeight: '700', fontSize: '0.95rem', color: '#fff' }}>Compy AI Analyst</div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--accent-success)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                                <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--accent-success)', display: 'inline-block' }}></span>
                                {competitorName ? `Briefed on ${competitorName}` : 'Online'}
                            </div>
                        </div>
                    </div>

                    {/* Messages */}
                    <div style={{
                        flex: 1,
                        overflowY: 'auto',
                        padding: '16px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '12px',
                        maxHeight: '320px',
                    }}>
                        {messages.map((msg, i) => (
                            <div key={i} style={{
                                display: 'flex',
                                justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                            }}>
                                <div style={{
                                    maxWidth: '85%',
                                    padding: '10px 14px',
                                    borderRadius: msg.role === 'user' ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                                    background: msg.role === 'user'
                                        ? 'linear-gradient(135deg, var(--accent-primary), #a29bfe)'
                                        : 'rgba(255,255,255,0.06)',
                                    color: '#fff',
                                    fontSize: '0.875rem',
                                    lineHeight: '1.5',
                                    whiteSpace: 'pre-wrap',
                                }}>
                                    {msg.content}
                                </div>
                            </div>
                        ))}
                        {isLoading && (
                            <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                                <div style={{
                                    padding: '12px 16px',
                                    borderRadius: '16px 16px 16px 4px',
                                    background: 'rgba(255,255,255,0.06)',
                                    display: 'flex',
                                    gap: '4px',
                                    alignItems: 'center',
                                }}>
                                    {[0, 1, 2].map(i => (
                                        <span key={i} style={{
                                            width: '6px', height: '6px', borderRadius: '50%',
                                            background: 'var(--accent-primary)',
                                            animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
                                            display: 'inline-block',
                                        }} />
                                    ))}
                                </div>
                            </div>
                        )}
                        <div ref={messagesEndRef} />
                    </div>

                    {/* Suggested Questions (only for first message) */}
                    {messages.length === 1 && (
                        <div style={{ padding: '0 16px 8px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                            {SUGGESTED_QUESTIONS.map((q, i) => (
                                <button
                                    key={i}
                                    onClick={() => sendMessage(q)}
                                    style={{
                                        textAlign: 'left',
                                        padding: '8px 12px',
                                        background: 'rgba(108, 92, 231, 0.1)',
                                        border: '1px solid rgba(108, 92, 231, 0.25)',
                                        borderRadius: '8px',
                                        color: 'var(--text-secondary)',
                                        fontSize: '0.8rem',
                                        cursor: 'pointer',
                                        transition: 'background 0.15s',
                                    }}
                                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(108, 92, 231, 0.2)'}
                                    onMouseLeave={e => e.currentTarget.style.background = 'rgba(108, 92, 231, 0.1)'}
                                >
                                    {q}
                                </button>
                            ))}
                        </div>
                    )}

                    {/* Input */}
                    <div style={{
                        padding: '12px 16px',
                        borderTop: '1px solid rgba(255,255,255,0.06)',
                        display: 'flex',
                        gap: '8px',
                        alignItems: 'flex-end',
                    }}>
                        <textarea
                            ref={inputRef}
                            rows={1}
                            placeholder={competitorId ? "Ask anything about this competitor..." : "Open a competitor first to start chatting"}
                            value={inputValue}
                            onChange={e => setInputValue(e.target.value)}
                            onKeyDown={handleKeyDown}
                            disabled={isLoading || !competitorId}
                            style={{
                                flex: 1,
                                background: 'rgba(255,255,255,0.06)',
                                border: '1px solid rgba(255,255,255,0.1)',
                                borderRadius: '10px',
                                color: '#fff',
                                padding: '10px 12px',
                                fontSize: '0.875rem',
                                resize: 'none',
                                outline: 'none',
                                fontFamily: 'inherit',
                                lineHeight: '1.4',
                                maxHeight: '80px',
                                overflowY: 'auto',
                            }}
                        />
                        <button
                            onClick={() => sendMessage()}
                            disabled={isLoading || !inputValue.trim() || !competitorId}
                            style={{
                                width: '38px',
                                height: '38px',
                                borderRadius: '10px',
                                background: inputValue.trim() && !isLoading
                                    ? 'linear-gradient(135deg, var(--accent-primary), #a29bfe)'
                                    : 'rgba(255,255,255,0.06)',
                                border: 'none',
                                cursor: inputValue.trim() && !isLoading ? 'pointer' : 'not-allowed',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontSize: '1rem',
                                transition: 'background 0.2s',
                                flexShrink: 0,
                            }}
                        >
                            ➤
                        </button>
                    </div>
                </div>
            )}

            <style>{`
                @keyframes bounce {
                    0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
                    30% { transform: translateY(-6px); opacity: 1; }
                }
            `}</style>
        </>
    );
}
