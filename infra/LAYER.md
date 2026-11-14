# Layer 6: Deployment

**Owner:** _TBD_ · **Stack:** Docker, Vultr

## You own
Hosting the FastAPI backend, the arq workers, Redis, and the Playwright browser environment on Vultr. Also secrets and the public demo URL.

## Plan
- One Vultr Cloud Compute instance (Ubuntu, 2–4 GB RAM; Chromium needs headroom) running `docker-compose.prod.yml`:
  `api` (Dockerfile.api), `worker` (Dockerfile.worker, includes Chromium), `redis`
- Databases stay managed: **Tiger Cloud** + **MongoDB Atlas** (allow the Vultr IP)
- Frontend: Vercel (fastest) or a third container on the same box
- Caddy or nginx in front for HTTPS (optional for the demo)

## Deploy
```bash
# on the Vultr box
git clone https://github.com/ishaan-j/Dropshot.git && cd Dropshot
cp .env.example .env   # fill in production values
docker compose -f infra/docker-compose.prod.yml up -d --build
curl localhost:8000/health
```

## First tasks
- [ ] Spin up the Vultr instance and install Docker
- [ ] Get `api` + `redis` running with `MOCK_MODE=true` and share the public URL with L1
- [ ] Add `worker` and check that Playwright can launch Chromium in the container
- [ ] Write the "how to redeploy" steps into this file
- [ ] Stretch: GitHub Action that redeploys on push to `main`
