import React, { useState, useEffect, useRef } from 'react';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer } from 'recharts';
import { Play, RefreshCw, Send, Sparkles, CheckCircle, Code, MessageSquare, Award, ExternalLink, User as UserIcon, Lock, Mail, ShieldCheck, Settings, Briefcase, TrendingUp, XCircle, ArrowRight, LogOut, Check } from 'lucide-react';

const API_BASE = 'http://localhost:8000';

export default function App() {
  // Auth & Onboarding State
  const [authStep, setAuthStep] = useState('login'); // 'login' | 'signup' | 'otp' | 'onboarding' | 'dashboard'
  const [token, setToken] = useState(localStorage.getItem('access_token') || '');
  const [user, setUser] = useState(null);
  const [authError, setAuthError] = useState('');

  // Form Inputs
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [leetcodeHandle, setLeetcodeHandle] = useState('starbuggs');
  const [preferredLanguage, setPreferredLanguage] = useState('Java');

  // Active Dashboard Tab
  const [activeSection, setActiveSection] = useState('overview'); // 'overview' | 'recommendation' | 'interview' | 'analytics' | 'roadmap' | 'activity' | 'settings'

  // Dashboard Data States
  const [recommendation, setRecommendation] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [roadmap, setRoadmap] = useState(null);
  const [loadingRec, setLoadingRec] = useState(false);
  const [syncing, setSyncing] = useState(false);

  // Attempt Modal State
  const [showAttemptModal, setShowAttemptModal] = useState(false);
  const [attemptSuccess, setAttemptSuccess] = useState(true);
  const [timeSpent, setTimeSpent] = useState(15);

  // Mock Interview State
  const [interview, setInterview] = useState(null);
  const [interviewType, setInterviewType] = useState('DSA');
  const [interviewDiff, setInterviewDiff] = useState('Medium');
  const [interviewDuration, setInterviewDuration] = useState(45);
  const [chatMessages, setChatMessages] = useState([]);
  const [userInput, setUserInput] = useState('');
  const [code, setCode] = useState('// Write solution here\nclass Solution {\n    public int solve() {\n        return 0;\n    }\n}');
  const wsRef = useRef(null);

  // Settings Form Inputs
  const [newPassword, setNewPassword] = useState('');
  const [settingsSuccess, setSettingsSuccess] = useState('');

  useEffect(() => {
    if (token) {
      fetchCurrentUser();
    }
  }, [token]);

  const fetchCurrentUser = async () => {
    try {
      const res = await fetch(`${API_BASE}/users/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const u = await res.json();
        setUser(u);
        setLeetcodeHandle(u.leetcode_handle || 'starbuggs');
        setPreferredLanguage(u.preferred_language || 'Java');
        setAuthStep('dashboard');

        fetchDashboardData(u.leetcode_handle || 'starbuggs');
      } else {
        localStorage.removeItem('access_token');
        setToken('');
        setAuthStep('login');
      }
    } catch (err) {
      console.error('Fetch user failed:', err);
    }
  };

  const fetchDashboardData = (handle) => {
    fetchRecommendation(handle);
    fetchAnalytics(handle);
    fetchRoadmap();
  };

  const fetchRecommendation = async (handle) => {
    setLoadingRec(true);
    try {
      const res = await fetch(`${API_BASE}/recommendations/next?user_id=${handle}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setRecommendation(data);
      }
    } catch (err) {
      console.error('Failed recommendation:', err);
    } finally {
      setLoadingRec(false);
    }
  };

  const fetchAnalytics = async (handle) => {
    try {
      const res = await fetch(`${API_BASE}/analytics/me?user_id=${handle}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setAnalytics(data);
      }
    } catch (err) {
      console.error('Failed analytics:', err);
    }
  };

  const fetchRoadmap = async () => {
    try {
      const res = await fetch(`${API_BASE}/roadmap/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setRoadmap(data);
      }
    } catch (err) {
      console.error('Failed roadmap:', err);
    }
  };

  // AUTH HANDLERS
  const handleRegister = async (e) => {
    e.preventDefault();
    setAuthError('');
    try {
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, username, password }),
      });
      const data = await res.json();
      if (res.ok) {
        setOtpCode(data.otp_code || ''); // Pre-fill OTP for test DX
        setAuthStep('otp');
      } else {
        setAuthError(data.detail || 'Registration failed.');
      }
    } catch (err) {
      setAuthError('Connection error during registration.');
    }
  };

  const handleVerifyOTP = async (e) => {
    e.preventDefault();
    setAuthError('');
    try {
      const res = await fetch(`${API_BASE}/auth/verify-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, otp_code: otpCode }),
      });
      const data = await res.json();
      if (res.ok) {
        localStorage.setItem('access_token', data.access_token);
        setToken(data.access_token);
        setAuthStep('onboarding');
      } else {
        setAuthError(data.detail || 'OTP verification failed.');
      }
    } catch (err) {
      setAuthError('Connection error during OTP verification.');
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setAuthError('');
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identifier: email || username || leetcodeHandle, password }),
      });
      const data = await res.json();
      if (res.ok) {
        if (data.status === 'pending_verification') {
          setEmail(data.email);
          setOtpCode(data.otp_code || '');
          setAuthStep('otp');
        } else {
          localStorage.setItem('access_token', data.access_token);
          setToken(data.access_token);
          fetchCurrentUser();
        }
      } else {
        setAuthError(data.detail || 'Invalid username/email or password.');
      }
    } catch (err) {
      setAuthError('Connection error during login.');
    }
  };

  const handleCompleteOnboarding = async (e) => {
    e.preventDefault();
    setAuthError('');
    setSyncing(true);
    try {
      const res = await fetch(`${API_BASE}/users/profile`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ leetcode_handle: leetcodeHandle, preferred_language: preferredLanguage }),
      });
      if (res.ok) {
        fetchCurrentUser();
      } else {
        setAuthError('LeetCode profile not found or sync failed.');
      }
    } catch (err) {
      setAuthError('Failed to complete onboarding.');
    } finally {
      setSyncing(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    setToken('');
    setUser(null);
    setAuthStep('login');
  };

  const handleSyncLeetCode = async () => {
    setSyncing(true);
    try {
      const res = await fetch(`${API_BASE}/leetcode/sync`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        fetchCurrentUser();
      }
    } catch (err) {
      console.error('Sync failed:', err);
    } finally {
      setSyncing(false);
    }
  };

  const handleFeedback = async (action) => {
    if (!recommendation) return;
    try {
      await fetch(`${API_BASE}/recommendations/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          frontend_question_id: recommendation.problem_id,
          action: action,
          time_spent_seconds: timeSpent * 60,
        }),
      });
      setShowAttemptModal(false);
      fetchDashboardData(user?.leetcode_handle || 'starbuggs');
    } catch (err) {
      console.error('Feedback submission failed:', err);
    }
  };

  const startMockInterview = async () => {
    try {
      const res = await fetch(`${API_BASE}/interviews/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          interview_type: interviewType,
          difficulty: interviewDiff,
          duration_minutes: interviewDuration,
          target_topics: ['DP', 'Graphs', 'Trees'],
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setInterview(data);
        setChatMessages([{ speaker: 'SYSTEM_AI', message_text: data.initial_message }]);
        connectWebSocket(data.interview_id);
        setActiveSection('interview');
      }
    } catch (err) {
      console.error('Failed to start interview:', err);
    }
  };

  const connectWebSocket = (interviewId) => {
    if (wsRef.current) wsRef.current.close();
    const ws = new WebSocket(`ws://localhost:8000/ws/v1/interview/${interviewId}`);
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.event === 'message') {
        setChatMessages((prev) => [...prev, { speaker: data.speaker, message_text: data.message_text, hint_given: data.hint_given }]);
      }
    };
    wsRef.current = ws;
  };

  const sendChatMessage = (hint = null) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    if (!userInput.trim() && !hint) return;

    const payload = { message: userInput, hint_requested: hint };
    wsRef.current.send(JSON.stringify(payload));

    if (userInput.trim()) {
      setChatMessages((prev) => [...prev, { speaker: 'USER', message_text: userInput }]);
      setUserInput('');
    }
  };

  const finishMockInterview = async () => {
    if (!interview) return;
    try {
      const res = await fetch(`${API_BASE}/interviews/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ interview_id: interview.interview_id, submitted_code: code }),
      });
      if (res.ok) {
        const evalData = await res.json();
        alert(`Mock Interview Finished!\nOverall Performance Index: ${evalData.overall_performance_index}\nCommunication: ${evalData.communication_score}\nTechnical Code Quality: ${evalData.code_quality_score}`);
        fetchDashboardData(user?.leetcode_handle || 'starbuggs');
        setActiveSection('analytics');
      }
    } catch (err) {
      console.error('Failed to finish interview:', err);
    }
  };

  // --- RENDER STEP 1: AUTHENTICATION (LOGIN / SIGNUP) ---
  if (authStep === 'login' || authStep === 'signup') {
    return (
      <div className="app-container" style={{ justifyContent: 'center', alignItems: 'center', padding: '2rem' }}>
        <div className="card" style={{ maxWidth: '420px', width: '100%', padding: '2rem' }}>
          <div className="logo" style={{ justifyContent: 'center', marginBottom: '1.5rem' }}>
            <div className="logo-icon">DSA</div>
            <span>DSA Learning Agent</span>
          </div>

          <div className="nav-tabs" style={{ marginBottom: '1.5rem', justifyContent: 'center' }}>
            <button className={`tab-btn ${authStep === 'login' ? 'active' : ''}`} onClick={() => { setAuthStep('login'); setAuthError(''); }}>
              Log In
            </button>
            <button className={`tab-btn ${authStep === 'signup' ? 'active' : ''}`} onClick={() => { setAuthStep('signup'); setAuthError(''); }}>
              Sign Up
            </button>
          </div>

          {authError && (
            <div style={{ background: 'rgba(239, 68, 68, 0.2)', color: '#ef4444', padding: '0.75rem', borderRadius: '0.375rem', fontSize: '0.85rem', marginBottom: '1rem' }}>
              {authError}
            </div>
          )}

          <form onSubmit={authStep === 'login' ? handleLogin : handleRegister}>
            {authStep === 'signup' && (
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '0.25rem' }}>Username</label>
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="e.g. starbuggs"
                  style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', color: '#fff', padding: '0.6rem', borderRadius: '0.375rem' }}
                />
              </div>
            )}

            <div style={{ marginBottom: '1rem' }}>
              <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '0.25rem' }}>
                {authStep === 'login' ? 'Email or Username or LeetCode ID' : 'Email Address'}
              </label>
              <input
                type={authStep === 'login' ? 'text' : 'email'}
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={authStep === 'login' ? 'starbuggs or email@example.com' : 'email@example.com'}
                style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', color: '#fff', padding: '0.6rem', borderRadius: '0.375rem' }}
              />
            </div>

            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '0.25rem' }}>Password</label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', color: '#fff', padding: '0.6rem', borderRadius: '0.375rem' }}
              />
            </div>

            <button type="submit" className="sync-btn" style={{ width: '100%', justifyContent: 'center', padding: '0.75rem' }}>
              {authStep === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  // --- RENDER STEP 2: EMAIL OTP VERIFICATION ---
  if (authStep === 'otp') {
    return (
      <div className="app-container" style={{ justifyContent: 'center', alignItems: 'center', padding: '2rem' }}>
        <div className="card" style={{ maxWidth: '420px', width: '100%', padding: '2rem' }}>
          <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
            <ShieldCheck color="#10b981" size={48} style={{ margin: '0 auto 0.5rem' }} />
            <h2 style={{ fontSize: '1.4rem' }}>Verify Email OTP</h2>
            <p style={{ fontSize: '0.85rem', color: '#94a3b8', marginTop: '0.25rem' }}>
              Enter the 6-digit OTP code sent to <strong>{email}</strong>.
            </p>
          </div>

          {authError && (
            <div style={{ background: 'rgba(239, 68, 68, 0.2)', color: '#ef4444', padding: '0.75rem', borderRadius: '0.375rem', fontSize: '0.85rem', marginBottom: '1rem' }}>
              {authError}
            </div>
          )}

          <form onSubmit={handleVerifyOTP}>
            <div style={{ marginBottom: '1.5rem' }}>
              <input
                type="text"
                required
                maxLength={6}
                value={otpCode}
                onChange={(e) => setOtpCode(e.target.value)}
                placeholder="123456"
                style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', color: '#10b981', padding: '0.75rem', borderRadius: '0.375rem', fontSize: '1.5rem', textAlign: 'center', letterSpacing: '0.25rem', fontFamily: 'monospace' }}
              />
            </div>

            <button type="submit" className="sync-btn" style={{ width: '100%', justifyContent: 'center', padding: '0.75rem' }}>
              Verify Account
            </button>
          </form>
        </div>
      </div>
    );
  }

  // --- RENDER STEP 3: LEETCODE ONBOARDING ---
  if (authStep === 'onboarding') {
    return (
      <div className="app-container" style={{ justifyContent: 'center', alignItems: 'center', padding: '2rem' }}>
        <div className="card" style={{ maxWidth: '480px', width: '100%', padding: '2rem' }}>
          <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
            <Sparkles color="#8b5cf6" size={40} style={{ margin: '0 auto 0.5rem' }} />
            <h2 style={{ fontSize: '1.4rem' }}>Link LeetCode Profile</h2>
            <p style={{ fontSize: '0.85rem', color: '#94a3b8', marginTop: '0.25rem' }}>
              We'll fetch your live LeetCode stats to initialize your LinUCB skill matrix.
            </p>
          </div>

          {authError && (
            <div style={{ background: 'rgba(239, 68, 68, 0.2)', color: '#ef4444', padding: '0.75rem', borderRadius: '0.375rem', fontSize: '0.85rem', marginBottom: '1rem' }}>
              {authError}
            </div>
          )}

          <form onSubmit={handleCompleteOnboarding}>
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '0.25rem' }}>LeetCode Username</label>
              <input
                type="text"
                required
                value={leetcodeHandle}
                onChange={(e) => setLeetcodeHandle(e.target.value)}
                placeholder="e.g. starbuggs"
                style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', color: '#fff', padding: '0.6rem', borderRadius: '0.375rem' }}
              />
            </div>

            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '0.25rem' }}>Preferred Programming Language</label>
              <select
                value={preferredLanguage}
                onChange={(e) => setPreferredLanguage(e.target.value)}
                style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', color: '#fff', padding: '0.6rem', borderRadius: '0.375rem' }}
              >
                <option value="Java">Java</option>
                <option value="Python">Python</option>
                <option value="C++">C++</option>
                <option value="JavaScript">JavaScript</option>
              </select>
            </div>

            <button type="submit" className="sync-btn" style={{ width: '100%', justifyContent: 'center', padding: '0.75rem' }} disabled={syncing}>
              {syncing ? 'Fetching Live LeetCode Stats...' : 'Complete Onboarding & Enter Dashboard'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  // --- RENDER STEP 4: AUTHENTICATED DASHBOARD (SECTIONS A TO G) ---
  return (
    <div className="app-container">
      {/* HEADER */}
      <header className="header">
        <div className="logo">
          <div className="logo-icon">DSA</div>
          <span>DSA Learning Agent</span>
        </div>

        <nav className="nav-tabs">
          <button className={`tab-btn ${activeSection === 'overview' ? 'active' : ''}`} onClick={() => setActiveSection('overview')}>Overview</button>
          <button className={`tab-btn ${activeSection === 'recommendation' ? 'active' : ''}`} onClick={() => setActiveSection('recommendation')}>Recommendation</button>
          <button className={`tab-btn ${activeSection === 'interview' ? 'active' : ''}`} onClick={() => setActiveSection('interview')}>AI Interview</button>
          <button className={`tab-btn ${activeSection === 'analytics' ? 'active' : ''}`} onClick={() => setActiveSection('analytics')}>Analytics</button>
          <button className={`tab-btn ${activeSection === 'roadmap' ? 'active' : ''}`} onClick={() => setActiveSection('roadmap')}>Roadmap</button>
          <button className={`tab-btn ${activeSection === 'settings' ? 'active' : ''}`} onClick={() => setActiveSection('settings')}>Settings</button>
        </nav>

        <div className="user-badge">
          {user && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <img src={user.user_avatar} alt="Avatar" style={{ width: '32px', height: '32px', borderRadius: '50%', border: '2px solid #8b5cf6' }} />
              <a href={`https://leetcode.com/u/${user.leetcode_handle}/`} target="_blank" rel="noreferrer" style={{ color: '#fff', textDecoration: 'none', fontWeight: 600, fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
                {user.leetcode_handle} <ExternalLink size={12} color="#94a3b8" />
              </a>
              <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                Rating: <strong style={{ color: '#f59e0b' }}>{user.contest_rating}</strong>
              </span>
            </div>
          )}
          <button className="sync-btn" onClick={handleSyncLeetCode} disabled={syncing}>
            <RefreshCw className={syncing ? 'animate-spin' : ''} size={16} />
            {syncing ? 'Syncing...' : 'Sync'}
          </button>
          <button className="tab-btn" onClick={handleLogout} title="Logout">
            <LogOut size={16} />
          </button>
        </div>
      </header>

      <main className="main-content">
        {/* SECTION A & DASHBOARD OVERVIEW */}
        {activeSection === 'overview' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            {/* SECTION A: PROFILE OVERVIEW */}
            <div className="card">
              <h3 style={{ fontSize: '1.2rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <UserIcon color="#10b981" size={20} /> Section A: Profile Overview
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '1rem' }}>
                <div style={{ background: '#0f172a', padding: '1rem', borderRadius: '0.5rem', textAlign: 'center' }}>
                  <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Total Solved</span>
                  <h2 style={{ fontSize: '1.8rem', color: '#f8fafc', marginTop: '0.25rem' }}>{user?.total_solved || 527}</h2>
                </div>
                <div style={{ background: '#0f172a', padding: '1rem', borderRadius: '0.5rem', textAlign: 'center' }}>
                  <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Easy Solved</span>
                  <h2 style={{ fontSize: '1.8rem', color: '#10b981', marginTop: '0.25rem' }}>{user?.easy_solved || 153}</h2>
                </div>
                <div style={{ background: '#0f172a', padding: '1rem', borderRadius: '0.5rem', textAlign: 'center' }}>
                  <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Medium Solved</span>
                  <h2 style={{ fontSize: '1.8rem', color: '#f59e0b', marginTop: '0.25rem' }}>{user?.medium_solved || 300}</h2>
                </div>
                <div style={{ background: '#0f172a', padding: '1rem', borderRadius: '0.5rem', textAlign: 'center' }}>
                  <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Hard Solved</span>
                  <h2 style={{ fontSize: '1.8rem', color: '#ef4444', marginTop: '0.25rem' }}>{user?.hard_solved || 74}</h2>
                </div>
                <div style={{ background: '#0f172a', padding: '1rem', borderRadius: '0.5rem', textAlign: 'center' }}>
                  <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Contest Rating</span>
                  <h2 style={{ fontSize: '1.8rem', color: '#8b5cf6', marginTop: '0.25rem' }}>{user?.contest_rating || 1521}</h2>
                </div>
              </div>
            </div>

            {/* QUICK GRID FOR RECOMMENDATION & RADAR */}
            <div className="dashboard-grid">
              <div className="card">
                <h3 style={{ fontSize: '1.2rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Sparkles color="#3b82f6" size={20} /> Next Problem Candidate
                </h3>
                {recommendation && (
                  <div>
                    <h2 style={{ fontSize: '1.3rem', color: '#f8fafc' }}>#{recommendation.problem_id}. {recommendation.title}</h2>
                    <p className="why-chosen" style={{ margin: '0.75rem 0' }}>{recommendation.why_chosen}</p>
                    <button className="sync-btn" onClick={() => setActiveSection('recommendation')}>View Candidate Details</button>
                  </div>
                )}
              </div>

              <div className="card">
                <h3 style={{ fontSize: '1.2rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Award color="#8b5cf6" size={20} /> Skill Matrix Radar
                </h3>
                {analytics && analytics.radar_data && (
                  <div style={{ width: '100%', height: '220px' }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <RadarChart data={analytics.radar_data}>
                        <PolarGrid stroke="#334155" />
                        <PolarAngleAxis dataKey="topic" stroke="#94a3b8" tick={{ fill: '#cbd5e1', fontSize: 11 }} />
                        <Radar name="Competency" dataKey="score" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.4} />
                      </RadarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* SECTION B: NEXT QUESTION RECOMMENDATION */}
        {activeSection === 'recommendation' && (
          <div className="card" style={{ maxWidth: '800px', margin: '0 auto' }}>
            <h3 style={{ fontSize: '1.3rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Sparkles color="#3b82f6" size={24} /> Section B: Next Question Recommendation (LinUCB)
            </h3>

            {loadingRec ? (
              <div style={{ padding: '2rem', textAlign: 'center', color: '#94a3b8' }}>Evaluating LinUCB matrix parameters...</div>
            ) : recommendation ? (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h2 style={{ fontSize: '1.5rem', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    #{recommendation.problem_id}. {recommendation.title}
                    <span style={{ background: '#065f46', color: '#34d399', padding: '0.2rem 0.6rem', borderRadius: '0.25rem', fontSize: '0.75rem', fontWeight: 600 }}>UNSOLVED</span>
                  </h2>
                  <span className={`badge badge-${recommendation.difficulty.toLowerCase()}`}>{recommendation.difficulty}</span>
                </div>

                <div className="why-chosen" style={{ marginTop: '1rem' }}>
                  <strong>Why Selected:</strong> {recommendation.why_chosen}
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', margin: '1rem 0' }}>
                  <div style={{ background: '#0f172a', padding: '0.75rem', borderRadius: '0.375rem' }}>
                    <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Theta Reward:</span>
                    <div style={{ fontWeight: 600, color: '#3b82f6' }}>{recommendation.theta_reward}</div>
                  </div>
                  <div style={{ background: '#0f172a', padding: '0.75rem', borderRadius: '0.375rem' }}>
                    <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Exploration Bonus:</span>
                    <div style={{ fontWeight: 600, color: '#8b5cf6' }}>{recommendation.exploration_bonus}</div>
                  </div>
                  <div style={{ background: '#0f172a', padding: '0.75rem', borderRadius: '0.375rem' }}>
                    <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Final UCB Score:</span>
                    <div style={{ fontWeight: 600, color: '#10b981' }}>{recommendation.ucb_score}</div>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
                  <a
                    href={`https://leetcode.com/problems/${recommendation.title_slug}/`}
                    target="_blank"
                    rel="noreferrer"
                    className="sync-btn"
                    style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
                  >
                    Solve on LeetCode <ExternalLink size={14} />
                  </a>
                  <button className="tab-btn active" onClick={() => handleFeedback('mark_solved')}>Mark Solved</button>
                  <button className="tab-btn" style={{ background: '#ef4444' }} onClick={() => handleFeedback('mark_failed')}>Mark Failed</button>
                  <button className="tab-btn" onClick={() => handleFeedback('skip')}>Skip</button>
                </div>
              </div>
            ) : null}
          </div>
        )}

        {/* SECTION C: AI INTERVIEW CENTER */}
        {activeSection === 'interview' && (
          <div className="split-layout">
            <div className="panel">
              <div className="panel-header">Setup AI Mock Interview</div>
              <div className="panel-body">
                <div style={{ marginBottom: '1rem' }}>
                  <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '0.25rem' }}>Interview Type</label>
                  <select value={interviewType} onChange={(e) => setInterviewType(e.target.value)} style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', color: '#fff', padding: '0.5rem', borderRadius: '0.25rem' }}>
                    <option value="DSA">DSA Interview</option>
                    <option value="System Design">System Design</option>
                    <option value="Behavioral">Behavioral</option>
                    <option value="Mixed">Mixed</option>
                  </select>
                </div>

                <div style={{ marginBottom: '1rem' }}>
                  <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '0.25rem' }}>Difficulty</label>
                  <select value={interviewDiff} onChange={(e) => setInterviewDiff(e.target.value)} style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', color: '#fff', padding: '0.5rem', borderRadius: '0.25rem' }}>
                    <option value="Easy">Easy</option>
                    <option value="Medium">Medium</option>
                    <option value="Hard">Hard</option>
                  </select>
                </div>

                <div style={{ marginBottom: '1.5rem' }}>
                  <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '0.25rem' }}>Duration</label>
                  <select value={interviewDuration} onChange={(e) => setInterviewDuration(parseInt(e.target.value))} style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', color: '#fff', padding: '0.5rem', borderRadius: '0.25rem' }}>
                    <option value={15}>15 Minutes</option>
                    <option value={30}>30 Minutes</option>
                    <option value={45}>45 Minutes</option>
                  </select>
                </div>

                <button className="sync-btn" style={{ width: '100%', justifyContent: 'center' }} onClick={startMockInterview}>
                  Start Mock Interview
                </button>
              </div>
            </div>

            <div className="panel">
              <div className="panel-header">Interactive IDE</div>
              <textarea className="code-editor" value={code} onChange={(e) => setCode(e.target.value)} />
              <div style={{ padding: '0.75rem', background: '#0f172a', borderTop: '1px solid #334155', textAlign: 'right' }}>
                <button className="sync-btn" onClick={finishMockInterview}>Finish Interview</button>
              </div>
            </div>

            <div className="panel">
              <div className="panel-header">AI Socratic Dialogue</div>
              <div className="panel-body">
                <div className="chat-stream">
                  {chatMessages.map((msg, idx) => (
                    <div key={idx} className={`chat-bubble ${msg.speaker === 'SYSTEM_AI' ? 'chat-bubble-ai' : 'chat-bubble-user'}`}>
                      <strong>{msg.speaker === 'SYSTEM_AI' ? 'AI Interviewer' : user?.username}:</strong>
                      <p style={{ marginTop: '0.25rem' }}>{msg.message_text}</p>
                    </div>
                  ))}
                </div>
              </div>
              <div style={{ padding: '0.75rem', background: '#0f172a', borderTop: '1px solid #334155' }}>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <input
                    type="text"
                    value={userInput}
                    onChange={(e) => setUserInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && sendChatMessage()}
                    placeholder="Type to AI Interviewer..."
                    style={{ flex: 1, background: '#1e293b', border: '1px solid #334155', color: '#fff', borderRadius: '0.25rem', padding: '0.5rem' }}
                  />
                  <button className="tab-btn active" onClick={() => sendChatMessage()}><Send size={16} /></button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* SECTION D: LEARNING ANALYTICS */}
        {activeSection === 'analytics' && analytics && (
          <div className="dashboard-grid">
            <div className="card">
              <h3 style={{ fontSize: '1.2rem', marginBottom: '1rem' }}>Section D: Topic Mastery Breakdown</h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', maxHeight: '350px', overflowY: 'auto' }}>
                {Object.entries(analytics.skills || {}).map(([topic, score]) => (
                  <div key={topic} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem', background: '#0f172a', borderRadius: '0.25rem' }}>
                    <span>{topic}</span>
                    <strong style={{ color: score > 0.7 ? '#10b981' : score > 0.5 ? '#f59e0b' : '#ef4444' }}>{(score * 100).toFixed(0)}%</strong>
                  </div>
                ))}
              </div>
            </div>

            <div className="card">
              <h3 style={{ fontSize: '1.2rem', marginBottom: '1rem' }}>Competency Radar</h3>
              <div style={{ width: '100%', height: '300px' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart data={analytics.radar_data}>
                    <PolarGrid stroke="#334155" />
                    <PolarAngleAxis dataKey="topic" stroke="#94a3b8" tick={{ fill: '#cbd5e1', fontSize: 11 }} />
                    <Radar name="Competency" dataKey="score" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.4} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        )}

        {/* SECTION E: PERSONALIZED ROADMAP */}
        {activeSection === 'roadmap' && roadmap && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div className="card">
              <h3 style={{ fontSize: '1.3rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Briefcase color="#10b981" size={24} /> Section E: Personalized Target Company Roadmap
              </h3>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '1rem' }}>
                {roadmap.target_companies.map((c) => (
                  <div key={c.company} style={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '0.5rem', padding: '1rem', textAlign: 'center' }}>
                    <h4 style={{ fontSize: '1.1rem', color: '#f8fafc' }}>{c.company}</h4>
                    <div style={{ fontSize: '1.6rem', fontWeight: 700, color: c.readiness_percentage > 70 ? '#10b981' : '#f59e0b', margin: '0.5rem 0' }}>
                      {c.readiness_percentage}%
                    </div>
                    <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Readiness Score</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="card">
              <h4 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>Skill Gap & Target Topics</h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                {roadmap.skill_gap.map((sg) => (
                  <div key={sg.topic} style={{ background: '#0f172a', padding: '0.75rem 1rem', borderRadius: '0.375rem', display: 'flex', justifyContent: 'space-between' }}>
                    <span>{sg.topic} (Current: {(sg.current_mastery * 100).toFixed(0)}%)</span>
                    <span style={{ color: '#ef4444', fontWeight: 600 }}>Gap: -{(sg.gap_score * 100).toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* SECTION G: SETTINGS */}
        {activeSection === 'settings' && (
          <div className="card" style={{ maxWidth: '550px', margin: '0 auto' }}>
            <h3 style={{ fontSize: '1.3rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Settings color="#8b5cf6" size={24} /> Section G: Account Settings
            </h3>

            {settingsSuccess && (
              <div style={{ background: 'rgba(16, 185, 129, 0.2)', color: '#10b981', padding: '0.75rem', borderRadius: '0.375rem', marginBottom: '1rem' }}>
                {settingsSuccess}
              </div>
            )}

            <div style={{ marginBottom: '1rem' }}>
              <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '0.25rem' }}>Update LeetCode Username</label>
              <input
                type="text"
                value={leetcodeHandle}
                onChange={(e) => setLeetcodeHandle(e.target.value)}
                style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', color: '#fff', padding: '0.6rem', borderRadius: '0.375rem' }}
              />
            </div>

            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'block', marginBottom: '0.25rem' }}>Preferred Language</label>
              <select
                value={preferredLanguage}
                onChange={(e) => setPreferredLanguage(e.target.value)}
                style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', color: '#fff', padding: '0.6rem', borderRadius: '0.375rem' }}
              >
                <option value="Java">Java</option>
                <option value="Python">Python</option>
                <option value="C++">C++</option>
                <option value="JavaScript">JavaScript</option>
              </select>
            </div>

            <button
              className="sync-btn"
              onClick={async () => {
                await handleCompleteOnboarding(new Event('click'));
                setSettingsSuccess('Settings updated successfully!');
              }}
            >
              Save Settings
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
