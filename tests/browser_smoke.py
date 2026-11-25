"""Optional browser smoke test; run with a local Uvicorn server and Chromium."""
import os
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH') or None, args=['--no-sandbox'])
    page = browser.new_page(viewport={'width': 1280, 'height': 900})
    page.route('**/api/search?*', lambda route: route.fulfill(json={'results':[{'name':'Kigali','country':'Rwanda','latitude':-1.95,'longitude':30.06}]}))
    forecast = {'timezone':'Africa/Kigali','current':{'time':'2026-11-24T12:00','temperature_2m':24,'relative_humidity_2m':68,'apparent_temperature':25,'weather_code':2,'wind_speed_10m':12},'daily':{'time':[f'2026-11-{i}' for i in range(24,31)],'weather_code':[2,61,0,2,61,0,2],'temperature_2m_max':[24,22,27,25,23,28,26],'temperature_2m_min':[16,15,17,16,15,17,16],'precipitation_probability_max':[10,80,0,20,70,5,30]}}
    page.route('**/api/weather?*',lambda route: route.fulfill(json=forecast))
    page.goto('http://127.0.0.1:8000')
    expect(page.locator('#temperature')).to_have_text('24°C')
    expect(page.locator('.day')).to_have_count(7)
    page.locator('#unit').click()
    expect(page.locator('#temperature')).to_have_text('75°F')
    page.locator('#filter').select_option('wet')
    expect(page.locator('.day')).to_have_count(2)
    page.locator('#sort').select_option('hot')
    expect(page.locator('.day').first).to_contain_text('73°F')
    page.locator('#filter').select_option('all')
    page.locator('#unit').click()
    page.locator('#sort').select_option('date')
    page.screenshot(path=os.getenv('SCREENSHOT_PATH','/tmp/weatherwatch-preview.png'),full_page=True)
    page.set_viewport_size({'width':375,'height':812})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.unroute('**/api/weather?*')
    page.route('**/api/weather?*',lambda route: route.fulfill(status=502,json={'detail':'Provider unavailable'}))
    page.locator('#results button').first.click()
    expect(page.locator('#status')).to_contain_text('Previous forecast remains visible')
    browser.close()
    print('Browser smoke test passed: initial load, units, filter, sort, mobile layout, provider error.')
