# Kairon Flow

Command-aware productivity assistant (LLM integration roadmapped in Phase 3).

## Live Demo
[Coming soon — deploying to Railway](https://railway.app/)

## Screenshots
*(Screenshots coming soon)*

## Tech Stack
| Component | Technology |
| :--- | :--- |
| **Backend** | Django 6, Django REST Framework (DRF) |
| **Frontend** | Vanilla CSS, HTML, Tailwind CSS, Google Fonts, Material Symbols |
| **Database** | SQLite (development), PostgreSQL (production) |
| **AI** | Command-aware deterministic parsing, AI scoring |
| **DevOps** | Docker, docker-compose, GitHub Actions CI, WhiteNoise |

## Features
- **Smart Command Parsing**: Direct command interpreter mapping text input to task creation, completion, status checks, and habit updates.
- **Deadline-Aware AI Scoring**: Tasks get automated urgency scoring based on priority choices and relative due dates.
- **Interactive Habit Matrix**: Multi-day tracking grid updates streaks in real-time.
- **OAuth Integrations Simulators**: Connected third-party integrations with simulation setup.
- **Comprehensive Help Center**: Live search accordions, custom support ticket form with glassmorphic toast notification.

## Local Setup
1. **Clone the repository**
   ```bash
   git clone https://github.com/sabhya1290/Kairon-Flow.git
   cd Kairon-Flow
   ```
2. **Create environment configuration**
   ```bash
   cp .env.example .env
   ```
3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
4. **Run migrations**
   ```bash
   python manage.py migrate
   ```
5. **Start development server**
   ```bash
   python manage.py runserver
   ```
   Open [http://localhost:8000/](http://localhost:8000/) in your web browser.

## Docker Setup
Build and run the stack using docker-compose:
```bash
docker-compose up --build
```

## Running Tests
Run the entire comprehensive test suite with verbose reporting:
```bash
python manage.py test productivity --verbosity=2
```

## API Documentation
Interactive OpenAPI schema documentation:
- Swagger UI: [http://localhost:8000/api/docs/](http://localhost:8000/api/docs/)
- Raw JSON Schema: [http://localhost:8000/api/schema/](http://localhost:8000/api/schema/)

## Roadmap
1. Phase 1: Onboarding flow, UI improvements, functional components.
2. Phase 2: Security hardening, env config, password complexity, API rate limiting.
3. Phase 3: Codebase restructuring, constants extraction, model schema migration, legacy migrations.
4. Phase 4: Performance optimization, N+1 query resolutions, WhiteNoise production setup.
5. Phase 5: Accessibility tagging, dialog focus trapping, GitHub Actions, Docker integration, Swagger API docs.

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.
