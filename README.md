# 🤖 Compy — Multi-Agent Competitive Intelligence Engine

Compy is a sophisticated, multi-agent platform designed to provide businesses with deep competitive intelligence. It leverages advanced AI agents to crawl, analyze, and monitor market trends, competitor moves, and strategic opportunities.

Built with a high-performance **FastAPI** backend and a modern **React** frontend, Compy empowers teams to stay ahead of the curve through data-driven strategic insights.

---

## ✨ Key Features

- 🏢 **Company Profiling**: Deep-dive analysis of your own company's market position and core strengths.
- ⚔️ **Competitor Intelligence**: Automated tracking and benchmarking against key industry competitors.
- 🗺️ **Strategic Roadmaps**: Generate tactical 4-week roadmaps and long-term strategic plans.
- 📡 **Real-time Monitoring**: Integrated scheduler to track competitor updates and news in real-time.
- 💬 **AI Agent Chat**: Interact directly with specialized intelligence agents for customized research.
- 📈 **Visual Dashboards**: Interactive data visualization using Chart.js to identify trends at a glance.
- 📞 **Voice Intelligence**: Automated voice call integration via Twilio for intelligence gathering.
- 📧 **Automated Alerts**: Email dispatch system for critical market shifts and competitive milestones.
- 📄 **Insight Export**: Generate and download comprehensive PDF reports of your strategic findings.

---

## 🛠️ Tech Stack

### Backend
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.10+)
- **AI Engine**: [Google Gemini Pro](https://ai.google.dev/)
- **ORM/DB**: SQLAlchemy with aiosqlite (SQLite)
- **Scheduling**: APScheduler
- **Communications**: Twilio API (Voice), SMTP (Email)
- **Data Gathering**: HTTPX, BeautifulSoup4, Readability

### Frontend
- **Framework**: [React](https://reactjs.org/) + [Vite](https://vitejs.dev/)
- **Routing**: React Router DOM (v6)
- **Visualization**: Chart.js & React-Chartjs-2
- **Styling**: Modern CSS with Neon/Glassmorphism design
- **Auth**: Google OAuth Integration

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10 or higher
- Node.js 18 or higher
- [Gemini API Key](https://aistudio.google.com/app/apikey)

### 1. Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment variables (Create a `.env` file in the `backend` folder):
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=your_email@gmail.com
   SMTP_PASSWORD=your_app_password
   TWILIO_ACCOUNT_SID=your_twilio_sid
   TWILIO_AUTH_TOKEN=your_twilio_token
   TWILIO_PHONE_NUMBER=your_twilio_number
   ```
5. Run the server:
   ```bash
   python main.py
   ```
   *The backend will be available at http://localhost:8000*

### 2. Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Run the development server:
   ```bash
   npm run dev
   ```
   *The frontend will be available at http://localhost:5173* (or as shown in your terminal).

---

## 📂 Project Structure

```text
Compy/
├── backend/            # FastAPI Application
│   ├── agents/         # specialized AI agent logic
│   ├── routers/        # API endpoints (analysis, chat, voice, etc.)
│   ├── services/       # Core business logic & scheduler
│   ├── models.py       # Database schemas
│   └── main.py         # Entry point
├── frontend/           # React + Vite Application
│   ├── src/
│   │   ├── pages/      # Dashboard, Analysis, Intelligence pages
│   │   ├── components/ # Reusable UI components
│   │   └── App.jsx     # Main routing and layout
└── README.md           # You are here!
```

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
