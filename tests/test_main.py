import httpx
import pytest
from fastapi.testclient import TestClient
from main import app, CURRENT, DAILY

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def mock(handler):
    async def get(url, **kwargs):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream:
            return await upstream.get(url, **kwargs)
    app.state.client.get = get

def test_home_health(client):
    assert 'WeatherWatch' in client.get('/').text
    assert client.get('/static/app.js').status_code == 200
    r = client.get('/health')
    assert r.json() == {'status':'ok'}
    assert r.headers['cache-control'] == 'no-store'

@pytest.mark.parametrize('url', ['/api/search?city=x','/api/search?city=%20%20','/api/weather?lat=91&lon=0','/api/weather?lat=0&lon=181','/api/weather?lat=abc&lon=0'])
def test_validation(client,url):
    r = client.get(url)
    assert r.status_code == 422
    assert r.headers['cache-control'] == 'no-store'

def test_search(client):
    def handler(req):
        assert req.url.params['name'] == 'Kigali'
        return httpx.Response(200,json={'results':[{'name':'Kigali','country':'Rwanda','latitude':-1.95,'longitude':30.06}]})
    mock(handler)
    r = client.get('/api/search?city=Kigali')
    assert r.json()['results'][0]['country'] == 'Rwanda'
    assert r.headers['cache-control'] == 'public, max-age=300'

def test_no_results(client):
    mock(lambda r: httpx.Response(200,json={}))
    assert client.get('/api/search?city=unknown').json() == {'results':[]}

def test_forecast(client):
    current = dict.fromkeys(CURRENT, 20); current['time']='2026-11-24T12:00'
    daily = {k:[20]*7 for k in DAILY}; daily['time']=[f'2026-11-{i}' for i in range(24,31)]
    def handler(req):
        assert req.url.params['forecast_days'] == '7'
        assert req.url.params['timezone'] == 'auto'
        return httpx.Response(200,json={'current':current,'daily':daily,'timezone':'Africa/Kigali'})
    mock(handler)
    r = client.get('/api/weather?lat=-1.95&lon=30.06')
    assert r.status_code == 200 and len(r.json()['daily']['time']) == 7

@pytest.mark.parametrize('response',[httpx.Response(503),httpx.Response(200,text='not json'),httpx.Response(200,json={'error':True}),httpx.Response(200,json={'current':{}})])
def test_provider_errors(client,response):
    mock(lambda req: response)
    r = client.get('/api/weather?lat=0&lon=0')
    assert r.status_code == 502 and r.headers['cache-control'] == 'no-store'

def test_timeout(client):
    def handler(req): raise httpx.ReadTimeout('timeout',request=req)
    mock(handler)
    assert client.get('/api/search?city=Kigali').status_code == 504
