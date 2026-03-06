import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom';
import { useState } from 'react';
import Onboarding from './pages/Onboarding';
import CompetitorAdd from './pages/CompetitorAdd';
import Analysis from './pages/Analysis';
import Dashboard from './pages/Dashboard';
import CompareView from './pages/CompareView';
import ChatBot from './components/ChatBot';

function App() {
    const [companyId, setCompanyId] = useState(null);
    const [companyData, setCompanyData] = useState(null);

    // Multi-competitor state
    const [competitors, setCompetitors] = useState([]);         // [{id, name, url, status, page_count}]
    const [activeCompetitorId, setActiveCompetitorId] = useState(null);
    const [analysisDataMap, setAnalysisDataMap] = useState({});  // { competitorId: analysisResult }
    const [planDataMap, setPlanDataMap] = useState({});           // { competitorId: planResult }

    const addCompetitorToList = (comp) => {
        setCompetitors((prev) => {
            const exists = prev.find((c) => c.id === comp.id);
            if (exists) return prev.map((c) => (c.id === comp.id ? { ...c, ...comp } : c));
            return [...prev, comp];
        });
        if (!activeCompetitorId) setActiveCompetitorId(comp.id);
    };

    const updateCompetitorInList = (comp) => {
        setCompetitors((prev) =>
            prev.map((c) => (c.id === comp.id ? { ...c, ...comp } : c))
        );
    };

    const setAnalysisData = (competitorId, data) => {
        setAnalysisDataMap((prev) => ({ ...prev, [competitorId]: data }));
    };

    const setPlanData = (competitorId, data) => {
        setPlanDataMap((prev) => ({ ...prev, [competitorId]: data }));
    };

    const hasCompetitors = competitors.length > 0;
    const activeAnalysis = analysisDataMap[activeCompetitorId] || null;
    const activePlan = planDataMap[activeCompetitorId] || null;

    return (
        <BrowserRouter>
            <div className="app-layout">
                <nav className="navbar">
                    <div className="navbar-brand">
                        <div className="logo">⚡</div>
                        <span>Compy</span>
                    </div>
                    <ul className="navbar-nav">
                        <li><NavLink to="/" end>Onboard</NavLink></li>
                        <li>
                            <NavLink to="/competitor" className={!companyId ? 'disabled' : ''}>
                                Scout {hasCompetitors ? `(${competitors.length})` : ''}
                            </NavLink>
                        </li>
                        <li>
                            <NavLink to="/analysis" className={!hasCompetitors ? 'disabled' : ''}>
                                Analyze
                            </NavLink>
                        </li>
                        <li>
                            <NavLink to="/dashboard" className={!hasCompetitors ? 'disabled' : ''}>
                                Dashboard
                            </NavLink>
                        </li>
                        <li>
                            <NavLink to="/compare" className={!companyId ? 'disabled' : ''}>
                                Compare
                            </NavLink>
                        </li>
                    </ul>
                </nav>

                <div className="page-container">
                    <Routes>
                        <Route
                            path="/"
                            element={
                                <Onboarding
                                    onComplete={(company) => {
                                        setCompanyId(company.id);
                                        setCompanyData(company);
                                    }}
                                    companyData={companyData}
                                />
                            }
                        />
                        <Route
                            path="/competitor"
                            element={
                                companyId ? (
                                    <CompetitorAdd
                                        companyId={companyId}
                                        competitors={competitors}
                                        onCompetitorAdded={addCompetitorToList}
                                        onCompetitorUpdated={updateCompetitorInList}
                                        onSelectCompetitor={setActiveCompetitorId}
                                        activeCompetitorId={activeCompetitorId}
                                    />
                                ) : (
                                    <Navigate to="/" replace />
                                )
                            }
                        />
                        <Route
                            path="/analysis"
                            element={
                                hasCompetitors ? (
                                    <Analysis
                                        competitors={competitors}
                                        activeCompetitorId={activeCompetitorId}
                                        onSelectCompetitor={setActiveCompetitorId}
                                        analysisDataMap={analysisDataMap}
                                        planDataMap={planDataMap}
                                        onAnalysisComplete={(id, data) => setAnalysisData(id, data)}
                                        onPlanComplete={(id, data) => setPlanData(id, data)}
                                    />
                                ) : (
                                    <Navigate to="/" replace />
                                )
                            }
                        />
                        <Route
                            path="/dashboard"
                            element={
                                hasCompetitors ? (
                                    <Dashboard
                                        competitors={competitors}
                                        activeCompetitorId={activeCompetitorId}
                                        onSelectCompetitor={setActiveCompetitorId}
                                        companyData={companyData}
                                        analysisDataMap={analysisDataMap}
                                        planDataMap={planDataMap}
                                    />
                                ) : (
                                    <Navigate to="/" replace />
                                )
                            }
                        />
                        <Route
                            path="/compare"
                            element={
                                companyId ? (
                                    <CompareView
                                        companyId={companyId}
                                        companyData={companyData}
                                    />
                                ) : (
                                    <Navigate to="/" replace />
                                )
                            }
                        />
                    </Routes>
                </div>

                {/* Global floating AI Analyst Chatbot - ONLY visible if analysis exists */}
                {activeAnalysis && (
                    <ChatBot
                        competitorId={activeCompetitorId}
                        competitorName={competitors.find(c => c.id === activeCompetitorId)?.name || null}
                        analysisData={activeAnalysis}
                    />
                )}
            </div>
        </BrowserRouter>
    );
}

export default App;
