#!make

DOWNTIFY_VERSION := 3.0.0
TARGET := henriquesebastiao/downtify

all: build up

build:
	docker buildx build . --no-cache

clean:
	find downloads -type f -name "*.mp3" -exec rm -f {} \;

up:
	docker compose up --build -d

down:
	docker compose down
	docker rmi downtify:latest

run:
	uv run python main.py web

desktop:
	uv run --extra desktop python desktop.py

desktop-build:
	@test "$$(uname -s)" = Darwin || (echo 'Build the macOS app on macOS'; exit 1)
	npm ci --prefix frontend
	npm run build --prefix frontend
	mkdir -p build/Downtify.iconset
	sips -z 512 512 frontend/public/1024.png --out build/Downtify.iconset/icon_512x512.png
	cp frontend/public/1024.png build/Downtify.iconset/icon_512x512@2x.png
	iconutil -c icns build/Downtify.iconset -o build/Downtify.icns
	uv run --frozen --extra desktop pyinstaller --noconfirm Downtify.spec

format:
	uv run ruff format .; ruff check . --fix
	prettier --write frontend/src/. docs/.vitepress/.

lint:
	prettier --check frontend/src/. docs/.vitepress/.
	uv run ruff check .; ruff check . --diff

export:
	uv export --no-hashes --no-dev -o requirements.txt

changelog:
	github_changelog_generator -u henriquesebastiao -p downtify -o CHANGELOG --no-verbose
	@echo "Changelog generated at CHANGELOG"

test:
	npm run test --prefix frontend
	npm run test --prefix docs
	uv run pytest -x -s -v

version:
	@VERSION=$(word 2,$(MAKECMDGOALS)); \
	echo "Downtify version: $$VERSION"; \
	./version.sh $$VERSION
	npm install --prefix frontend
	uv run ruff format .; ruff check . --fix
	prettier --write frontend/src/.

doc:
	npm install --prefix docs
	npm run dev --prefix docs

doc-build:
	npm ci --prefix docs
	npm run build --prefix docs

rm:
	sudo rm -rf docker/downloads/*
	sudo rm -rf docker/data/*

%:
	@:

.PHONY: all build clean up down run desktop desktop-build format lint export changelog version doc doc-build rm
