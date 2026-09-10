# mychores

Simple weekly chore board for kids. Track who does what, on which day and time,
and check items off when they’re done.

## Features

- Add multiple kids
- Add chores with a title, weekday, and time
- Check chores done / not done
- Reset a kid’s checkmarks for a new week
- Remove kids or individual chores
- Health endpoint: `GET /up` returns `200 OK`
- Packaged with Docker and docker compose
- SQLite data stored in a volume so it survives restarts

## Project layout

```
mychores/
  app.py
  requirements.txt
  Dockerfile
  docker-compose.yml
  .dockerignore
  .gitignore
  templates/
    index.html
  README.md
```

## Quick start with Docker

```bash
cd mychores
docker compose up --build
```

Then open:

- App: [Context: http://localhost:5000]
- Health: [Context: http://localhost:5000/up]

You should see `OK` and HTTP 200 from `/up`.

Stop it with `Ctrl+C`, or in the background:

```bash
docker compose up -d --build
docker compose down
```

## Run without Docker (optional)

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export DB_PATH=./mychores.db
python app.py
```

App listens on `0.0.0.0:5000`.

## How to use

1. Add a kid.
2. Select that kid.
3. Add chores (name, day, time).
4. Click the circle to mark a chore done. Click again to undo.
5. Use **Reset this kid's checks** at the start of a new week.
6. Remove a chore with ×, or remove the kid entirely.

## Environment

| Variable | Default | Meaning |
| -        | -       | -       | 
| `DB_PATH` | `/data/mychores.db` | SQLite file path |
| `PORT` | `5000` | HTTP port |

## Docker image only

```bash
docker build -t mychores:latest .
docker run -d --name mychores -p 5000:5000 -v mychores-data:/data mychores:latest
```

## Push this project to GitHub

Create an empty GitHub repo named `mychores`, then:

```bash
cd mychores
git init
git add .
git commit -m "Initial commit: mychores web app"
git branch -M main
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/mychores.git
git push -u origin main
```

SSH:

```bash
git remote add origin git@github.com:YOUR_GITHUB_USERNAME/mychores.git
git push -u origin main
```

## Push the image to Docker Hub

```bash
docker login
docker build -t YOUR_DOCKERHUB_USERNAME/mychores:latest .
docker push YOUR_DOCKERHUB_USERNAME/mychores:latest
```

If you already built with compose:

```bash
docker tag mychores:latest YOUR_DOCKERHUB_USERNAME/mychores:latest
docker push YOUR_DOCKERHUB_USERNAME/mychores:latest
```

Run from Docker Hub:

```bash
docker run -d --name mychores -p 5000:5000 -v mychores-data:/data YOUR_DOCKERHUB_USERNAME/mychores:latest
```

Replace `YOUR_GITHUB_USERNAME` and `YOUR_DOCKERHUB_USERNAME` with your accounts.

## License
Use it however you like at home.
