.PHONY: install lint run-backend run-frontend dev test

install:
	uvx pre-commit install
	cd backend && make install
	cd frontend && npm install
	touch .env

lint:
	cd backend && make lint
	cd frontend && npm run lint && npm run format

run-backend:
	cd backend && make run

run-frontend:
	cd frontend && npm run dev

dev:
	make -j2 run-backend run-frontend

test:
	cd backend && make test
