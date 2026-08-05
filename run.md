# How to Run the Project

This guide provides step-by-step instructions to get the complete project running locally.

## 1. Start Infrastructure (Postgres & Redis)
Ensure Docker is installed and running, then start the required databases:
```bash
docker compose -f infra/docker-compose.yml up -d
```

## 2. Environment Configuration
Copy the example environment file:
```bash
cp .env.example .env
```
Next, you need to generate three secrets and add them to your `.env` file. You can generate them by running the following Python commands:
```bash
python -c "import os,base64;print('MASTER_KEY=' + base64.b64encode(os.urandom(32)).decode())"
python -c "import secrets;print('SESSION_SECRET=' + secrets.token_urlsafe(48))"
python -c "import secrets;print('RECIPIENT_GUARD_SECRET=' + secrets.token_urlsafe(48))"
```
Paste the outputs into your `.env` file. Fill in any other required variables (like Google OAuth credentials).

## 3. Python Environment Setup
Activate your virtual environment first (this example is for Windows PowerShell):
```bash
.venv/Scripts/Activate.ps1
```
*(On Linux/macOS, you would typically use `source .venv/bin/activate`)*

Install the required Python packages:
```bash
pip install -e packages/core
pip install -e apps/api
```

## 4. Database Migrations
Apply the database migrations to set up your schema:
```bash
cd apps/api
alembic upgrade head
cd ../..
```

## 5. Start the Services
You need to run three separate processes to have the whole system working. Open a new terminal for each of the following (remember to activate your virtual environment in the terminals where you run the Python services):

### 5a. Start the API Server
```bash
cd apps/api
python run_api.py --reload
```
*Note: Do not use the uvicorn CLI directly on Windows due to asyncio event loop specifics. Start the API with `python run_api.py`.*

### 5b. Start the Background Worker
```bash
cd apps/api
arq app.worker.WorkerSettings
```

### 5c. Start the Web App
In a new terminal:
```bash
cd apps/web
npm install
npm run dev
```

## 6. Verification
Once everything is running, you can verify the API and database connection by checking the `readyz` endpoint (typically at http://localhost:8000/readyz if the API is running on port 8000).
