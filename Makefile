.PHONY: help deps runserver migrate superuser format lint test all docker-up docker-down

help:
	@echo "deps        Install dev dependencies into the active virtualenv"
	@echo "runserver   Run the Django dev server"
	@echo "migrate     Apply database migrations"
	@echo "superuser   Create a Django admin superuser"
	@echo "format      Run isort + black"
	@echo "lint        Run flake8"
	@echo "test        Run the test suite with coverage"
	@echo "all         format + lint + test"
	@echo "docker-up   Build and run the API + Redis via docker-compose"
	@echo "docker-down Stop the docker-compose stack"

deps:
	pip install -r requirements/dev.txt

runserver:
	python manage.py runserver

migrate:
	python manage.py migrate

superuser:
	python manage.py createsuperuser

format:
	isort .
	black .

lint:
	flake8 .

test:
	pytest

all: format lint test

docker-up:
	docker compose up --build

docker-down:
	docker compose down
