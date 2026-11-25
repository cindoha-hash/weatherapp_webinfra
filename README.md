# WeatherWatch

A lightweight weather dashboard for planning daily activities, travel and outdoor work. It uses live weather and city data from Open-Meteo and runs on two application servers behind HAProxy.

## Submission links and access

- **Live application:** [http://weather.indataflow.com](http://weather.indataflow.com)
- **GitHub repository:** TODO — insert public repository URL before submission.
- **Demo video (maximum 2 minutes):** TODO — insert publicly accessible or unlisted video URL before submission.
- **API key:** Not applicable. Open-Meteo's free non-commercial endpoints do not require an API key ([official terms](https://open-meteo.com/en/terms)).
- **Login credentials:** Not applicable. The application is public and does not require an account, username or password. Server administration credentials are not required for review and must remain private.

Deployment is reported working on both servers and the load balancer by the project owner. Public accessibility, TLS and recorded test evidence must be checked before final submission. Do not submit with the TODO links above.

## Features

- Worldwide city search with matching locations and coordinates.
- Current temperature, apparent temperature, humidity, wind and weather conditions.
- Seven-day forecast with precipitation probability, sorting and filtering.
- Celsius/Fahrenheit switching and temperature trend visualization.
- Responsive HTML/CSS interface, with Kigali as the initial city.
- Validated inputs, asynchronous external requests, timeouts and user-facing error messages.
- Health endpoint and cache-control headers for deployment.

## Architecture

```text
Browser -> weather.indataflow.com (DNS A record -> Lb01)
                   |
             HAProxy :80
             round robin
             /          \
      Web01 :8000     Web02 :8000
      Uvicorn         Uvicorn
      FastAPI         FastAPI
             \          /
              Open-Meteo HTTPS API
```

Both application servers run the same source code. HAProxy routes requests by hostname and checks `/health` on each server. Existing Nginx services on port 80 serve other sites; WeatherWatch traffic goes directly to port 8000. No Cloudflare proxy, database or authentication is needed. HTTPS and HAProxy caching are planned improvements unless independently verified.

## Run locally (Python 3.10+)

```bash
git clone https://github.com/cindoha-hash/weatherapp_webinfra
cd weatherwatch
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

If using the ZIP, extract it and start from `cd weatherwatch`. On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`. Open http://127.0.0.1:8000. Internet access is necessary for real forecasts. Search for a city, select a match, change units, and filter or sort the forecast. The chart always displays the chronological seven-day forecast.

## REST API

| Endpoint | Purpose |
|---|---|
| `GET /` | Dashboard |
| `GET /health` | Uncached process health check |
| `GET /api/search?city=Kigali` | City search |
| `GET /api/weather?lat=-1.95&lon=30.06` | Current weather and seven-day forecast |
| `GET /docs` | FastAPI interactive API documentation |

External endpoints: `https://geocoding-api.open-meteo.com/v1/search` and `https://api.open-meteo.com/v1/forecast`. Both use GET and JSON. Coordinates are validated; city input is length-limited. Requests have an eight-second HTTPX timeout configuration. Provider errors return 502, timeouts return 504, and invalid inputs return 422. Successful data responses advertise `public, max-age=300`; other responses use `no-store`. These headers do not by themselves prove that HAProxy caching is enabled.

## Deploy to Web01 and Web02

The following is a reproducible systemd deployment recipe for Ubuntu/Debian, based on the chosen architecture. Adjust paths and service names to match the actual installations.

On **each** web server:

```bash
sudo apt update
sudo apt install -y python3 python3-venv git
sudo useradd --system --home /opt/weatherwatch --shell /usr/sbin/nologin weatherwatch
sudo git clone YOUR_PUBLIC_REPOSITORY_URL /opt/weatherwatch
sudo python3 -m venv /opt/weatherwatch/.venv
sudo /opt/weatherwatch/.venv/bin/pip install -r /opt/weatherwatch/requirements.txt
sudo cp /opt/weatherwatch/deploy/weatherwatch.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now weatherwatch
curl -i http://127.0.0.1:8000/health
sudo ss -lntp | grep :8000
```

If the service user or directory already exists, skip its creation; do not overwrite an existing deployment blindly. Ensure the service user can read the application files. Uvicorn listens on `0.0.0.0:8000` so Lb01 can reach it. Restrict inbound TCP 8000 to Lb01 using the appropriate firewall and/or cloud security group; use private networking where available. Keep SSH restricted and do not expose admin sockets or secrets.

## Configure Lb01

Keep the existing HAProxy configuration and its other websites. Back up `/etc/haproxy/haproxy.cfg`. From Lb01 verify each backend first:

```bash
curl -i --connect-timeout 5 http://WEB01_IP:8000/health
curl -i --connect-timeout 5 http://WEB02_IP:8000/health
```

See [`deploy/haproxy-weather.cfg`](deploy/haproxy-weather.cfg) for the hostname routing and dedicated backend snippets. Replace placeholders with reachable server addresses. Insert the HTTP rules into the existing frontend before any broad redirects or backend selection. Preserve the existing `http_back` backend and other rules. For HTTPS, obtain a valid certificate for the weather hostname and add the hostname routing to the existing TLS frontend before enforcing HTTPS.

```bash
sudo haproxy -c -f /etc/haproxy/haproxy.cfg
sudo systemctl reload haproxy
sudo systemctl status haproxy
```

At the authoritative DNS provider, create an A record named `weather` pointing to Lb01's public IPv4 address (DNS only if a proxy option exists). Verify with `dig +short weather.indataflow.com`. No DNS records for the individual application servers are needed.

## Testing and evidence

### Local automated tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
node --check static/app.js  # optional, requires Node.js
```

The earlier implementation run reported 14 passing backend tests and a successful JavaScript syntax check. Tests cover mocked upstream data, invalid inputs, timeout/error handling, static files, health and caching headers. Live API and browser navigation were not verified in the original sandbox. Optional browser test: install Playwright, run `python -m playwright install chromium`, start Uvicorn, and run `python tests/browser_smoke.py`.

### Production tests (record actual results before submission)

```bash
curl -i http://weather.indataflow.com/health
curl -fsS 'http://weather.indataflow.com/api/search?city=Kigali'
curl -fsS 'http://weather.indataflow.com/api/weather?lat=-1.95&lon=30.06'
for i in $(seq 1 10); do
    curl -fsS -H 'Host: weather.indataflow.com' http://127.0.0.1/health
    echo
done
```

Run the loop on Lb01. Before and after the loop, inspect per-server session counters using the configured local admin socket (requires socat):

```bash
printf 'show stat\n' | sudo socat stdio /run/haproxy/admin.sock | awk -F, '$1=="weather_backend" {printf "%s status=%s sessions=%s\n",$2,$18,$8}'
```

Both server rows should be UP and their counters should increase. Save actual output in `docs/test-evidence.md`. Health responses are intentionally not cached. To verify failover, stop WeatherWatch on one server during a safe test window, wait for health checks to mark it down, verify the public endpoint still returns 200, then restart it and wait until it is UP before repeating for the other server. For rolling updates, update one server at a time, verify health, and only then update the other. Do not claim zero downtime without measuring requests during the rollout.

## Challenges and solutions

- **Older HAProxy syntax:** the installed version rejected `srv_name` in a response header. Removed the incompatible expression; use HAProxy session counters to demonstrate distribution.
- **Missing default backend:** the existing frontends referenced `http_back`. Restoring its definition for port 80 allowed the original websites and WeatherWatch's separate backend to coexist.
- **HTTP redirection:** the existing HTTPS redirect intercepted weather requests. A hostname-specific exception allowed HTTP testing pending a valid weather certificate.
- **Web01 connectivity:** one backend initially failed to respond from Lb01. Both servers were later reported working; the precise root cause and corrective action have not been recorded. Add them to the evidence file rather than guessing.
- **External API failures:** the application handles timeouts and malformed responses with explicit errors rather than displaying misleading data.

## Performance and security

The backend reuses an asynchronous HTTP client, sends cache-control headers, validates inputs, restricts upstream URLs, and sets content security and MIME-sniffing protection headers. The frontend uses text rendering for external strings. HAProxy health checks remove failing backends from normal rotation. Native caching, TLS hardening and load balancer upgrade are separate follow-up tasks; do not claim them as completed until tested. No secret keys are required. `.gitignore` excludes local environments, caches and `.env` files.

## Credits

Weather and geocoding data: [Open-Meteo](https://open-meteo.com/), [forecast API](https://open-meteo.com/en/docs), [geocoding API](https://open-meteo.com/en/docs/geocoding-api), [terms](https://open-meteo.com/en/terms), and [data licence](https://open-meteo.com/en/license) (CC BY 4.0). Data are transformed for presentation; forecasts are not guarantees. The free service is intended for non-commercial use and is rate limited.

Libraries and infrastructure: [FastAPI](https://fastapi.tiangolo.com/), [HTTPX](https://www.python-httpx.org/), [Uvicorn](https://www.uvicorn.org/), [pytest](https://docs.pytest.org/), [Playwright](https://playwright.dev/python/), [HAProxy](https://www.haproxy.org/), [systemd](https://systemd.io/).

Code drafted with AI assistance; review, understand and adapt it in accordance with the course's originality and AI-use policies before submission.

