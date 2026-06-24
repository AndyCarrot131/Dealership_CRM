#!/bin/bash

docker compose up -d
docker compose exec backend alembic upgrade head