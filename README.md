# DLP Advisor - Legal Document Processing & Defect Tracking Platform

## Overview
A comprehensive multi-role system (Homeowner, Developer, Legal) designed for streamlined property defect management. The platform utilizes 3D Lidar scans for precise defect localization and incorporates an AI engine for Tribunal Report generation and specialized legal chat assistance.

## Tech Stack
- **Backend:** Python, Flask
- **Database:** PostgreSQL, SQLAlchemy
- **Frontend:** Tailwind CSS, Three.js (for 3D Lidar visualization)
- **AI Integration:** Groq/LLM (Llama models) for document analysis and report generation

## Setup Instructions
1. Clone the repository to your local machine.
2. Make sure you have Docker and Docker Compose installed.
3. Create a `.env` file based on `.env.example` in the root directory.
4. Run the following command to build and start the containers:
   ```bash
   docker compose up --build
   ```
5. The application will be available at `http://localhost:5100` (or `http://localhost:5000` depending on configuration).
6. To initialize the database, you may need to run `flask init-db` within the application container.

## Environment Variables (.env.example)

```env
# Application Settings
FLASK_APP=app
FLASK_ENV=development
SECRET_KEY=your_secret_key_here
SESSION_IDLE_TIMEOUT_MINUTES=120

# Database Configuration
DATABASE_URL=postgresql://user:password@db:5432/dlp_db

# AI API Keys (Separated by role)
LLM_API_KEY_CHATBOT=your_chatbot_api_key_here
LLM_API_KEY_REPORT=your_report_api_key_here
LLM_API_KEY=your_fallback_api_key_here
```
