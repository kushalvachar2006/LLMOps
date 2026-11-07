# 🚀 LLMOps Platform

**Build • Manage • Experiment • Evaluate • Monitor • Deploy LLM Applications**

An end-to-end LLMOps platform designed to simplify the lifecycle management of Large Language Model (LLM) applications. It provides a centralized environment for managing LLM projects, experimenting with prompts, interacting with Google Gemini, tracking inference telemetry, and gaining insights into application performance.

The platform aims to bridge the gap between LLM experimentation and production-ready AI systems.

---

## ✨ Key Features

### 1. Project Management
- Create and manage multiple LLM projects.
- View project information in a centralized workspace.
- Paginated project listing.
- Organize LLM application development.

### 2. Prompt Playground
- Experiment with different prompts.
- Configure system instructions.
- Select the Gemini model.
- Adjust generation parameters:
  - Temperature
  - Top-P
  - Maximum output tokens
- Generate and experiment with LLM responses.

### 3. LLM Integration
- Google Gemini integration using `google-genai`.
- Backend-managed model interactions.
- Secure API key handling.
- Centralized LLM generation through FastAPI.

### 4. Observability & Telemetry
Track important information associated with LLM requests:

- Request IDs
- Response latency
- Token usage
- Persisted request telemetry
- Request-level performance information

### 5. Analytics Dashboard
- Centralized platform overview.
- Statistics calculated from stored records.
- Visibility into LLM request activity.
- Performance insights based on available telemetry.

### 6. Backend API
- REST API powered by FastAPI.
- MongoDB integration using PyMongo.
- Health-check capabilities.
- Structured backend architecture.

---

## 🛠️ Technology Stack

| Layer | Technologies |
|---|---|
| Backend | Python, FastAPI |
| Frontend | React.js |
| Interactive UI | Streamlit |
| Database | MongoDB, PyMongo |
| LLM Provider | Google Gemini |
| LLM SDK | google-genai |
| Containerization | Docker, Docker Compose |
| CI/CD | GitHub Actions |
| Testing | Pytest |
| API Server | Uvicorn |

---

## 🏗️ Architecture

The platform follows a frontend-backend architecture where user interactions are handled by the presentation layer, while LLM requests and database operations are managed by the backend.

```text
                 USER
                   |
          +--------+--------+
          |                 |
     React.js UI        Streamlit UI
          |                 |
          +--------+--------+
                   |
              FastAPI
               Backend
                   |
          +--------+--------+
          |                 |
       MongoDB          Google Gemini
          |                 |
    Project Data       LLM Generation
          |
    Request Telemetry
          |
     Analytics / Overview
```

**Core workflow:**

1. User creates or selects an LLM project.
2. User configures prompts and model parameters.
3. Frontend sends the request to the FastAPI backend.
4. Backend communicates with Google Gemini.
5. The generated response is returned to the client.
6. Request telemetry is persisted in MongoDB.
7. The overview dashboard presents insights from stored records.

---

## 📂 Project Structure

```text
LLMOps/
│
├── backend/
│   └── app/
│       └── main.py
│       └── ...                 # Backend modules
│
├── frontend/
│   └── ...                     # React.js frontend
│
├── web/
│   └── ...                     # Web application components
│
├── .gitignore
├── ci.yml                      # CI configuration
├── docker-compose.yml          # Docker orchestration
└── README.md
```

---

## ⚙️ Getting Started

### Prerequisites

Make sure you have the following installed:

- Python 3.10+
- Node.js and npm
- MongoDB
- Google Gemini API key
- Git
- Docker (optional)

### 1. Clone the Repository

```bash
git clone https://github.com/kushalvachar2006/LLMOps.git

cd LLMOps
```

### 2. Backend Setup

Navigate to the backend directory:

```bash
cd backend
```

Create a virtual environment:

```bash
python -m venv venv
```

Activate it:

**Windows:**
```bash
venv\Scripts\activate
```

**Linux / macOS:**
```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Configure the required backend environment variables, including your Gemini API credentials and MongoDB connection settings.

Start the FastAPI server:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend API documentation:

```text
http://localhost:8000/docs
```

### 3. Frontend Setup

Open another terminal:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Start the development server using the script configured in `package.json`:

```bash
npm run dev
```

### 4. Streamlit Setup

Run the Streamlit application using its configured entry-point file:

```bash
streamlit run <streamlit-entry-file>
```

---

## 🐳 Docker Deployment

The repository includes Docker Compose configuration for containerized execution.

Build and start the services:

```bash
docker compose up --build
```

Stop the services:

```bash
docker compose down
```

Configure the required environment variables before starting the containers.

---

## 🔐 Security

Security is an important part of the platform.

- Gemini API credentials are stored in backend environment variables.
- API keys are never returned by the backend API.
- Environment files are excluded from version control.
- Docker images exclude `.env` files.
- CORS is restricted through the `CORS_ORIGINS` configuration.
- Prompt text is not persisted by default.

**Never commit API keys, database credentials, or other sensitive configuration to GitHub.**

---

## 🗺️ Development Roadmap

The platform is being developed incrementally.

| Phase | Features | Status |
|---|---|---|
| Phase 1 | Foundation, project management, Gemini integration, prompt playground, telemetry | ✅ Completed |
| Phase 2 | Prompt versioning and dataset management | 🔜 Planned |
| Phase 3 | Experiment management and LLM evaluation | 🔜 Planned |
| Phase 4 | Authentication and access management | 🔜 Planned |
| Phase 5 | Advanced monitoring, retries, fallback and deployment workflows | 🔜 Planned |

Future development aims to introduce a more complete LLM application lifecycle management experience.

---

## ⚠️ Current Limitations

- Authentication and per-project access control are not implemented yet.
- Advanced retry and fallback mechanisms are planned.
- Overview statistics currently cover the latest 100 requests.
- Advanced monitoring and full analytics are planned.
- Live Gemini, MongoDB and Docker integration require further end-to-end validation.

---

## 🎯 Project Objective

The primary objective is to understand and implement the operational side of Generative AI.

Rather than focusing only on building applications powered by LLMs, this project explores the infrastructure and engineering practices required to manage them effectively throughout their lifecycle.

It aims to provide hands-on exposure to:

- LLM application lifecycle management.
- Prompt engineering and experimentation.
- Model integration and inference.
- Request tracking and observability.
- Performance analytics.
- Scalable AI application architecture.
- Deployment and operational workflows.

---

## 🤝 Contributing

Contributions, suggestions, and feature improvements are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Implement your changes.
4. Submit a pull request.

---

## 👨‍💻 Author

**Kushal V Achar**

Computer Science & Engineering | AI & Generative AI Enthusiast

GitHub: [@kushalvachar2006](https://github.com/kushalvachar2006)

---

⭐ If you find this project interesting, consider giving the repository a star!
