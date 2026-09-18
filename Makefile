.PHONY: up up-fake down logs test test-backend test-web e2e talk

up:            ## real providers (needs .env with LLM_API_KEY)
	docker compose up --build -d
up-fake:       ## whole stack with fake STT/LLM/TTS
	docker compose -f docker-compose.yml -f docker-compose.test.yml up --build -d
down:
	docker compose down
logs:
	docker compose logs -f backend

test: test-backend test-web

test-backend:
	cd backend && uv venv -q .venv && uv pip install -q --python .venv/bin/python -r requirements-dev.txt && .venv/bin/python -m pytest -q

test-web:
	docker run --rm -v "$(PWD)/web":/app -w /app -u "$$(id -u):$$(id -g)" -e HOME=/tmp node:22-alpine sh -c "npm install --no-audit --no-fund --loglevel=error && npm run build && npx vitest run"

PW_IMAGE=mcr.microsoft.com/playwright:v1.63.0-noble
e2e:           ## browser e2e against the running fake stack (make up-fake first); E2E_MOCK=1 for no-backend mode
	docker run --rm --network host -v "$(PWD)/web":/app -w /app -u "$$(id -u):$$(id -g)" -e HOME=/tmp \
	  -e E2E_BASE_URL=http://localhost:8080 -e E2E_MOCK=$(E2E_MOCK) $(PW_IMAGE) npx playwright test

talk:          ## send a prerecorded file through the running backend: make talk FILE=clip.wav
	python3 backend/scripts/talk_file.py $(FILE) --url http://localhost:8080
