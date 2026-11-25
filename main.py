from pathlib import Path
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, HTTPException, Query, Response, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

ROOT = Path(__file__).parent
GEO = 'https://geocoding-api.open-meteo.com/v1/search'
FORECAST = 'https://api.open-meteo.com/v1/forecast'

@asynccontextmanager
async def lifespan(app):
    async with httpx.AsyncClient(timeout=8.0) as client:
        app.state.client = client
        yield

app = FastAPI(title='WeatherWatch', lifespan=lifespan)

@app.middleware('http')
async def cache_policy(request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = ('public, max-age=300' if request.url.path in ('/api/search', '/api/weather') and response.status_code == 200 else 'no-store')
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Content-Security-Policy'] = "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    return response

async def fetch(url, params):
    try:
        result = await app.state.client.get(url, params=params)
        result.raise_for_status()
        data = result.json()
        if not isinstance(data, dict) or data.get('error'):
            raise ValueError('Invalid API response')
        return data
    except httpx.TimeoutException as exc:
        raise HTTPException(504, 'Weather provider timed out. Try again shortly.') from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, 'Weather provider unavailable. Try again shortly.') from exc

@app.get('/health')
async def health():
    return {'status': 'ok'}

@app.get('/api/search')
async def search(city: str = Query(min_length=2, max_length=100)):
    city = city.strip()
    if len(city) < 2:
        raise HTTPException(422, 'Enter at least two characters.')
    data = await fetch(GEO, {'name': city, 'count': 8, 'language': 'en', 'format': 'json'})
    try:
        return {'results': [{'name': r['name'], 'country': r.get('country', ''), 'region': r.get('admin1', ''), 'latitude': float(r['latitude']), 'longitude': float(r['longitude'])} for r in data.get('results', [])]}
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(502, 'Invalid city data from provider.') from exc

CURRENT = ['temperature_2m', 'relative_humidity_2m', 'apparent_temperature', 'weather_code', 'wind_speed_10m']
DAILY = ['weather_code', 'temperature_2m_max', 'temperature_2m_min', 'precipitation_probability_max']

@app.get('/api/weather')
async def weather(lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180)):
    data = await fetch(FORECAST, {'latitude': lat, 'longitude': lon, 'current': ','.join(CURRENT), 'daily': ','.join(DAILY), 'timezone': 'auto', 'forecast_days': 7})
    try:
        current, daily = data['current'], data['daily']
        if not isinstance(current['time'], str) or any(k not in current for k in CURRENT):
            raise ValueError('Missing current fields')
        if len(daily['time']) != 7 or any(len(daily[k]) != 7 for k in DAILY):
            raise ValueError('Incomplete forecast')
        return {'current': current, 'daily': daily, 'timezone': data['timezone']}
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(502, 'Incomplete weather data from provider.') from exc

@app.get('/')
async def home():
    return FileResponse(ROOT / 'static/index.html')

app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')
