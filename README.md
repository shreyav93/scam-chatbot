# scam-chatbot

# Scam Chatbot

The frontend uses React and Vite. The backend uses Django. Run both locally to test the connection.

## 1. Install the tools and clone the repo

Install Git, Python 3.13, and Node.js 24 LTS, which includes npm. Then run:

```bash
git clone https://github.com/YOUR-GITHUB-USERNAME/scam-chatbot.git
cd scam-chatbot
```

## 2. Start Django

From the project folder, run these commands in your first Terminal tab:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
python backend/manage.py migrate
python backend/manage.py runserver 127.0.0.1:8001
```

Leave this tab running. Open [the Django health endpoint](http://127.0.0.1:8001/api/health/) and check that it returns a JSON message.

## 3. Start React

Open a second Terminal tab. From the `scam-chatbot` folder, run:

```bash
cd frontend
npm ci
npm run dev
```

Open the **Local** address Vite prints, usually [http://localhost:5173](http://localhost:5173). Add `/api/health/` to that address. If you see the same JSON message as in step 2, Vite is forwarding requests to Django correctly. This setup check uses a local SQLite database and needs no AI API key.

## 4. Start working on a feature

Create a branch for your task from the project folder:

```bash
git switch main
git pull
git switch -c feature/your-task
```

Push your branch and open a pull request when your changes are ready for review.
