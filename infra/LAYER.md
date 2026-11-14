# Layer 6: Deployment

**Owner:** _TBD_ · **Stack:** Docker, Vultr

## You own
Hosting the FastAPI backend, the arq workers, Redis, the Playwright browser environment and the
frontend on Vultr. Also secrets and the public demo URL.

## What's here
| File | What it builds |
|---|---|
| `Dockerfile.backend` | One image for the API and the worker, with Chromium. The API needs the browser too: while state is in memory it runs the background jobs itself, including the claim bot. |
| `Dockerfile.frontend` | The Next.js dashboard and the demo store page the bot files on. The public API URL is baked in at build time. |
| `docker-compose.prod.yml` | `api`, `frontend`, `redis`, and an opt-in `worker` (profile `worker`). A shared volume carries claim-bot screenshots; `solana/` is mounted read-only for the devnet wallet. |
| `../.dockerignore` | Keeps `.env`, keypairs, `node_modules` and build output out of the images. |

**Not yet run anywhere.** These files were written on a machine without Docker, so no image has been
built from them. Expect to fix small things on the first build.

## Deploy
One Vultr Cloud Compute instance (Ubuntu, 4 GB RAM: Chromium and the Next build need headroom).
```bash
# on the Vultr box, with Docker installed
git clone https://github.com/ishaan-j/Dropshop.git && cd Dropshop
cp .env.example .env
#   fill in the keys, then set how browsers reach this box:
#   PUBLIC_API_URL=http://<server-ip>:8000
#   PUBLIC_WEB_URL=http://<server-ip>:3000
docker compose --env-file .env -f infra/docker-compose.prod.yml up -d --build
curl localhost:8000/health        # shows which backends are live or simulated
```
Open ports 3000 and 8000 in the Vultr firewall. The app is then at `PUBLIC_WEB_URL`.

To redeploy after a push: `git pull`, then the same `docker compose ... up -d --build`.
Changing `PUBLIC_API_URL` needs a rebuild of `frontend` (the URL is compiled into it).

## Things to know
- **State resets on restart** until Layer 4 lands: the API keeps demo data in memory, and
  `POST /demo/reset` reseeds it. That's also why the API must stay a single process.
- **The worker is off by default.** It only has work once state is in the database. Then start it
  with `--profile worker` and set `MONGODB_URI` / `TIMESCALE_URL` (allow the Vultr IP in Atlas and Tiger Cloud).
- **Devnet wallet:** copy `solana/dev-keypair.json` to the box (it's gitignored) or run
  `docker compose ... exec api python -m finance.solana_setup` and fund the printed address.
  Without it, vault records fall back to simulated entries.
- **HTTPS:** not set up. For a public demo put Caddy or nginx in front and use `https://` URLs for
  `PUBLIC_API_URL` / `PUBLIC_WEB_URL`. Alternatively host the frontend on Vercel with
  `NEXT_PUBLIC_API_URL` set, and add its origin to `PUBLIC_WEB_URL`.

## Status
- [x] Dockerfiles, compose file and `.dockerignore` written for the current architecture
- [x] Frontend production build passes locally (`npm run build`)
- [ ] Spin up the Vultr instance and install Docker
- [ ] First build and run of the images (never done); check that Chromium launches in the container
- [ ] Share the public URL with the team
- [ ] Stretch: GitHub Action that redeploys on push to `main`
