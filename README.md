# DLP Advisor Platform — Defect Liability Period Management Powered by AI & 3D Visualisation

## Overview

The DLP Advisor Platform addresses the critical **"Three-Party Silo Problem"** in Malaysian property defect management by creating a unified ecosystem that connects Homeowners, Developers, and Legal Professionals. Traditionally, these stakeholders operate in isolated workflows, leading to communication gaps, delayed resolutions, and increased litigation costs during the Defect Liability Period (DLP).

Our platform breaks down these silos through:

- **Integrated 3D Visualisation**: Homeowners and developers collaboratively inspect properties using LiDAR-scanned GLB 3D models
- **AI-Powered Legal Guidance**: Instant access to SPA/DLP clause interpretations and legal precedents via Groq/Llama
- **Automated Tribunal Documentation**: One-click generation of court-admissible defect reports with SHA-256 data integrity
- **Role-Based Workflows**: Tailored dashboards ensuring each party accesses relevant information while maintaining data privacy
- **Geospatial Context**: Google Maps Places API integration for accurate property location tagging

This holistic approach transforms adversarial defect resolution into a collaborative, transparent process benefiting all stakeholders.

---

## Key Features

### Three-Party Collaboration System
| Role | Capabilities |
|------|-------------|
| **Homeowner** | Defect reporting with photographic evidence, progress tracking, LiDAR scan viewing, tribunal report generation |
| **Developer** | Defect assignment, resolution workflow management, completion date tracking, compliance report generation |
| **Lawyer** | Case assignment, evidence verification, tribunal documentation preparation, compliance auditing |

### 3D LiDAR Inspection (Three.js)
- Upload and visualise `.glb` format 3D scans via an interactive WebGL viewer
- Precise defect localisation through coordinate-based pinpointing on the 3D model
- Automated snapshot extraction from GLB models during upload
- Side-by-side defect annotation overlaid on the scanned mesh

### Premium AI Legal Advisor (Groq / Llama)
- Real-time interpretation of Sale & Purchase Agreement (SPA) clauses
- Defect Liability Period (DLP) regulation guidance through a dedicated chatbot
- Automated legal precedent retrieval for defect classification
- Multilingual support (English / Bahasa Malaysia) for the Malaysian legal context

### Module 3: AI-Powered Automated Compliance Report Generation
- **Multi-language PDF Reports**: One-click generation of Borang 1 TTPM-formatted reports in Bahasa Malaysia or English
- **Groq AI Narrative Summaries**: AI-generated defect severity analysis and compliance narratives embedded in every report
- **SHA-256 Data Integrity**: Every generated PDF includes a cryptographic hash of the report data for tamper evidence
- **Certificate of Compliance Page**: Automatically appended compliance certificate with signature IDs
- **Appendix A — Closed Cases**: Auto-closed defects are excluded from the main body and listed in a structured appendix
- **HDA 30-Day Compliance Tracking**: Each defect is automatically assessed against the Housing Development Act requirement
- **Role-Aware Reports**: Homeowner, Developer, and Legal reports each present tailored views of the same underlying data
- **Evidence Annexure**: Photographic evidence images are embedded directly into the PDF for each defect

### Google Maps Location Autocomplete
- Google Places API integration on all registration and property forms
- Address autocomplete with structured validation (street, state, postcode)
- Jurisdictional boundary awareness for tribunal venue selection

### Role-Based Access Control (RBAC)
- Strict data isolation — Homeowners see only their defects; Developers see only their assigned projects; Lawyers see only their assigned cases
- Context-aware dashboards tailored to each role's workflow
- Comprehensive audit trail logging every state change across all roles
- Session-based authentication with HTTP-only, Secure, SameSite cookies

---

## Technology Stack

### Backend Infrastructure
| Component | Technology |
|-----------|-----------|
| Web Framework | Flask (Python 3.12) with Blueprint architecture |
| Database | PostgreSQL 15 with SQLAlchemy ORM |
| Authentication | Flask-Login + Google OAuth 2.0 SSO (Authlib) |
| Containerisation | Docker & Docker Compose |
| Cloud Platform | DigitalOcean App Platform |
| Object Storage | DigitalOcean Spaces (S3-compatible) with local fallback |

### Frontend Experience
| Component | Technology |
|-----------|-----------|
| Styling | Tailwind CSS 3.x (responsive, utility-first) |
| 3D Rendering | Three.js / Babylon.js for WebGL GLB viewing |
| Maps | Google Maps JavaScript API + Places Library |
| Interactivity | Vanilla JavaScript with modular component architecture |

### AI & Intelligence Layer
| Component | Technology |
|-----------|-----------|
| LLM Provider | Groq API (Llama 3 8B / 70B) |
| Chatbot Engine | Custom context-aware agent with DLP knowledge base |
| Report Generation | Domain-specific prompt templates with AI narrative generation |
| Translation | AI-assisted Malay ↔ English legal translation with caching |
| PDF Engine | ReportLab with custom layout, image embedding, and SHA-256 signing |

### DevOps & Security
| Component | Implementation |
|-----------|---------------|
| Secrets Management | Environment variable isolation (`.env` + DigitalOcean App Platform secrets) |
| Reverse Proxy | Werkzeug ProxyFix for X-Forwarded-Proto trust |
| Static Serving | WhiteNoise for Gunicorn-compatible static asset delivery |
| CI/CD | GitHub Actions (configured pipeline) |

---

## Security Implementations

The platform implements enterprise-grade security measures suitable for handling sensitive legal and property data:

- **Authentication**: Google OAuth 2.0 SSO with cryptographically random state parameters preventing CSRF on the OAuth callback
- **Session Management**: Flask-Login with `HTTPOnly`, `Secure`, and `SameSite=Lax` cookies; session cleared on logout
- **Secret Isolation**: All API keys (Groq, Google, DigitalOcean Spaces) loaded from environment variables only — zero hardcoded secrets
- **Input Validation**: Server-side validation on all registration fields (password special-character requirement, phone digit-only enforcement, email domain checks)
- **File Upload Security**:
  - 50 MB maximum content length enforced at the Flask layer
  - Extension whitelisting (`.glb`, `.pdf`, `.jpg`, `.jpeg`, `.png`)
  - Magic-byte verification for GLB (`b'glTF'`) and PDF (`b'%PDF'`)
  - Image integrity verification via Pillow (`img.verify()`)
  - Path traversal protection via `os.path.realpath` comparison
- **Database Protection**: SQLAlchemy parameterised queries throughout — no raw SQL concatenation
- **PDF Data Integrity**: SHA-256 hash of serialised report data embedded in every generated PDF
- **Error Handling**: Generic error pages (404, 500) that avoid leaking stack traces to end users

---

## Local Setup & Installation

### Prerequisites
- Docker Engine 24.0+
- Docker Compose V2+
- Git 2.0+
- 4 GB+ available RAM

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/dlp-advisor-platform.git
   cd dlp-advisor-platform
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys (see Environment Variables section below)
   ```

3. **Build and launch all services**
   ```bash
   docker compose up --build
   ```

4. **Initialise the database** (first run only)
   ```bash
   # In a separate terminal:
   docker compose exec flask flask init-db
   ```

5. **Access the platform**
   ```
   http://localhost:5100
   ```

6. **Stop the services**
   ```bash
   docker compose down
   ```

> **Note for macOS / Windows**: The `host.docker.internal` extra host is configured for host gateway access. If your Docker version does not support it, you may remove the `extra_hosts` block from `docker-compose.yml`.

---

## Environment Variables

Create a `.env` file in the project root using the template below. **Never commit actual values to version control.**

### Authentication & Secrets

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Flask session encryption key (min 32 chars) | `a3f8b2c1d4e5...` |
| `GOOGLE_CLIENT_ID` | Google OAuth 2.0 Client ID | `1234567890-abc.apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Google OAuth 2.0 Client Secret | `GOCSPX-xxxxxxxxxxxx` |

### AI API Keys (Groq)

> [!IMPORTANT]
> `GROQ_API_KEY` is **required** to enable AI-powered features including the legal chatbot (Module 1) and the AI narrative report generation (Module 3). Without it, the app will start but AI features will be disabled and PDF reports will be generated without the AI summary section. Register at [console.groq.com](https://console.groq.com/) to obtain a free API key.

| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Primary Groq API key (fallback for all AI features) |
| `GROQ_API_KEY_REPORT` | Groq key for Module 3 report generation (overrides primary) |
| `GROQ_API_KEY_CHATBOT` | Groq key for Module 1 chatbot (overrides primary) |

### Google Maps

| Variable | Description |
|----------|-------------|
| `GOOGLE_MAPS_API_KEY` | Google Maps JavaScript API key with Places API enabled |

### Database

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:password@flask_db:5432/flaskdb` |

### DigitalOcean Spaces (Production Only)

| Variable | Description |
|----------|-------------|
| `DO_SPACES_KEY` | Spaces Access Key ID |
| `DO_SPACES_SECRET` | Spaces Secret Access Key |
| `DO_SPACES_BUCKET` | Space bucket name |
| `DO_SPACES_REGION` | Space region (e.g. `sgp1`) |
| `DO_SPACES_ENDPOINT` | Space endpoint URL |

### Flask Environment

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_APP` | Application entry point | `app:app` |
| `FLASK_ENV` | Environment mode | `development` |
| `APP_TIMEZONE` | Timezone for report timestamps | `Asia/Kuala_Lumpur` |
| `AUTO_CLOSE_DAYS` | Days after completion before a case auto-closes | `14` |

> **Google Cloud Setup**: Obtain OAuth credentials from the [Google Cloud Console](https://console.cloud.google.com/). Configure the authorised redirect URI as `http://localhost:5100/google/callback` (development) or `https://your-domain.com/google/callback` (production).
>
> **Maps Setup**: Restrict your Google Maps API key to HTTP referrers matching your domain and enable only the Maps JavaScript API and Places API.

---

## Project Structure

```
dlp-advisor-platform/
├── app/                          # Flask application package
│   ├── __init__.py               # Application factory, extensions init, blueprints
│   ├── models.py                 # SQLAlchemy ORM models (User, Defect, Scan, Evidence, etc.)
│   ├── auth/
│   │   └── routes.py             # Login/logout, OAuth, registration, role dashboards
│   ├── module1/
│   │   └── routes.py             # JSON API for chatbot and document analysis
│   ├── module2/
│   │   ├── routes.py             # 3D scan upload, visualisation, defect CRUD, evidence review
│   │   ├── storage.py            # DO Spaces / local file abstraction
│   │   ├── glb_snapshot.py       # GLB snapshot extraction
│   │   └── pdf_utils.py          # PDF image extraction
│   ├── module3/
│   │   ├── routes.py             # Defect dashboards, report generation, compliance workflows
│   │   ├── report_generator.py   # AI-powered tribunal report generation (Groq integration)
│   │   ├── report_data.py        # Report metadata assembly and claim number generation
│   │   ├── ai_translate.py       # Legal translation helpers (EN ↔ MS)
│   │   ├── ai_translate_cached.py# Cached translation layer for performance
│   │   ├── groqai_client.py      # Groq API client factory
│   │   ├── prompts.py            # Domain-specific prompt templates (HDA, SPA, DLP)
│   │   ├── config_pdf_labels.py  # Bilingual PDF label definitions
│   │   ├── config_mappings.py    # Status/priority normalisation maps
│   │   └── services/
│   │       └── pdf_service.py    # ReportLab PDF engine (Borang 1 TTPM layout, SHA-256, appendix)
│   ├── module4/
│   │   └── routes.py             # User feedback submission
│   ├── chatbot_component/
│   │   ├── chatbot_core.py       # LLM-backed chatbot engine
│   │   ├── dlp_knowledge_base.py # Embedded SPA/DLP legal rules
│   │   └── conversation_logger.py
│   ├── extensions.py             # db, login_manager, oauth instances
│   └── utils/auth_helper.py      # Shared authorization helpers
├── scripts/                      # Data seeding and migration utilities
│   └── db/seed_module3.py        # Module 3 demo data seeder
├── Dockerfile                    # Production container build
├── docker-compose.yml            # Multi-service orchestration
├── requirements.txt              # Python dependencies
└── .env.example                  # Environment variable template
```

---

## Docker Services

| Service | Container Name | Port (Host:Container) | Purpose |
|---------|---------------|----------------------|---------|
| `flask` | `flask_app` | `5100:5000` | Flask application server |
| `flask_db` | `flask_db` | `5432:5432` | PostgreSQL database |

Data persistence is managed through the `flask_db_data` Docker volume, ensuring database state survives container restarts.

---

## Database Seeding

The platform includes seed data for demonstration and evaluation:

```bash
# Run during first deployment:
docker compose exec flask flask init-db

# Seed additional Module 3 demo data (optional):
docker compose exec flask python scripts/db/seed_module3.py
```

Seeded accounts include pre-configured Homeowner, Developer, and Lawyer profiles with sample defect data for immediate exploration of all role workflows.

---

## Academic & Professional Value

This Final Year Project demonstrates:

- **Legal Innovation**: AI-assisted interpretation of complex Malaysian property law (SPA, DLP, Tribunal for Consumer Claims)
- **Technical Excellence**: Production-grade full-stack implementation with modern tooling
- **User-Centered Design**: Role-specific interfaces addressing genuine stakeholder needs in the property ecosystem
- **Security Maturity**: Environment-isolated secrets, role-based access control, input validation, safe file handling, and cryptographic report integrity
- **Cloud Readiness**: Containerised deployment targeting DigitalOcean App Platform

The system exhibits mastery of:
- Microservices architecture and API design
- Secure full-stack development practices
- LLM integration in domain-specific applications (Groq / Llama 3)
- Relational database design for complex multi-role workflows
- PDF generation with structured layout, evidence embedding, and data integrity hashing
- Containerisation and DevOps best practices
- User experience design for professional cross-organisational workflows

---

*Ready for university FYP evaluation and stakeholder review — combining academic rigour with practical utility to solve a genuine problem in the Malaysian property ecosystem.*
