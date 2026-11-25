'use strict';
const $ = id => document.getElementById(id);
let weather, locationName, fahrenheit = false, sequence = 0;
const status = message => { $('status').textContent = message; };
const node = (tag, text, cls) => { const e = document.createElement(tag); e.textContent = text; if(cls) e.className = cls; return e; };
const temp = n => n == null ? '—' : `${Math.round(fahrenheit ? n * 9 / 5 + 32 : n)}°${fahrenheit ? 'F' : 'C'}`;
const number = (n, unit) => n == null ? '—' : `${n}${unit}`;
function conditions(code) {
  if (code === 0) return ['Clear sky','☀️'];
  if ([1,2].includes(code)) return ['Partly cloudy','⛅'];
  if (code === 3) return ['Overcast','☁️'];
  if ([45,48].includes(code)) return ['Fog','🌫️'];
  if ([71,73,75,77,85,86].includes(code)) return ['Snow','❄️'];
  if ([95,96,99].includes(code)) return ['Thunderstorm','⛈️'];
  if ([51,53,55,56,57,61,63,65,66,67,80,81,82].includes(code)) return ['Rain or drizzle','🌧️'];
  return ['Unknown conditions','—'];
}
async function get(path, params) {
  const response = await fetch(`${path}?${new URLSearchParams(params)}`, {signal: AbortSignal.timeout(12000)});
  if (!response.ok) { const error = await response.json().catch(() => ({})); throw new Error(typeof error.detail === 'string' ? error.detail : 'Request failed. Please retry.'); }
  return response.json();
}
async function search(city, auto = false) {
  const id = ++sequence;
  $('results').replaceChildren(); status('Searching cities…');
  try {
    const data = await get('/api/search', {city});
    if(id !== sequence) return;
    if (!data.results.length) { status('No matching cities. Try another spelling.'); return; }
    status('Choose a city from the results.');
    for(const place of data.results) {
      const label = [...new Set([place.name,place.region,place.country].filter(Boolean))].join(', ');
      const button = node('button', label); button.type = 'button'; button.addEventListener('click', () => load(place,label)); $('results').append(button);
    }
    if(auto) $('results').firstElementChild.click();
  } catch(e) { if(id === sequence) status(e.message); }
}
async function load(place,label) {
  const id = ++sequence; status(`Loading ${label}…`);
  try {
    const data = await get('/api/weather', {lat:place.latitude,lon:place.longitude});
    if(id !== sequence) return;
    weather = data; locationName = label; render(); $('weather').hidden = false; status('Forecast loaded.');
  } catch(e) { if(id === sequence) status(`${e.message}${weather ? ' Previous forecast remains visible.' : ''}`); }
}
function render() {
  if(!weather) return;
  const c = weather.current; const [desc,symbol] = conditions(c.weather_code);
  $('place').textContent = locationName; $('temperature').textContent = temp(c.temperature_2m); $('condition').textContent = desc; $('symbol').textContent = symbol;
  $('updated').textContent = `Data time: ${c.time.replace('T',' ')} (${weather.timezone})`;
  $('metrics').replaceChildren();
  for(const [label,value] of [['Humidity',number(c.relative_humidity_2m,'%')],['Wind',number(c.wind_speed_10m,' km/h')],['Feels like',temp(c.apparent_temperature)]]) { const item = node('div','','metric'); item.append(node('span',label),node('strong',value)); $('metrics').append(item); }
  renderDays();
}
function renderDays() {
  if(!weather) return;
  const d = weather.daily;
  const all = d.time.map((date,i) => ({date, high:d.temperature_2m_max[i], low:d.temperature_2m_min[i], rain:d.precipitation_probability_max[i], code:d.weather_code[i]}));
  const filter = $('filter').value, sort = $('sort').value;
  const days = all.filter(x => filter === 'all' || (x.rain != null && (filter === 'wet' ? x.rain >= 50 : x.rain < 50)));
  const key = {hot:'high',cold:'low',rain:'rain'}[sort];
  if(key) days.sort((a,b) => a[key] == null ? (b[key] == null ? 0 : 1) : b[key] == null ? -1 : sort === 'cold' ? a[key]-b[key] : b[key]-a[key]);
  $('days').replaceChildren();
  if(!days.length) $('days').append(node('p','No days match this filter.'));
  for(const day of days) { const card = node('article','','day'); const [desc,icon] = conditions(day.code); card.append(node('strong',new Date(day.date+'T12:00:00Z').toLocaleDateString('en',{weekday:'short',month:'short',day:'numeric',timeZone:'UTC'})),node('span',icon,'emoji'),node('small',desc),node('strong',temp(day.high)),node('small',`Low ${temp(day.low)}`),node('small',`Rain ${number(day.rain,'%')}`)); $('days').append(card); }
  drawTrend(all);
}
function drawTrend(days) {
  const ns = 'http://www.w3.org/2000/svg'; const svg = document.createElementNS(ns,'svg'); svg.setAttribute('viewBox','0 0 420 145'); svg.setAttribute('role','img'); svg.setAttribute('aria-label','Seven-day high temperature trend');
  const values = days.map(d=>d.high).filter(v=>v != null); $('trend').replaceChildren(); if(!values.length) { $('trend').textContent='No temperature trend available.'; return; }
  const min = Math.min(...values)-2, max = Math.max(...values)+2;
  const add = (tag,attrs,text) => {const el=document.createElementNS(ns,tag); for(const [k,v] of Object.entries(attrs)) el.setAttribute(k,v); if(text) el.textContent=text; svg.append(el);};
  let prev=null; days.forEach((d,i)=>{const x=32+i*59; if(d.high != null){const y=105-(d.high-min)/(max-min)*80; if(prev) add('line',{x1:prev.x,y1:prev.y,x2:x,y2:y,stroke:'#77b5ff','stroke-width':2}); add('circle',{cx:x,cy:y,r:4,fill:'#77b5ff'}); add('text',{x,y:y-10,fill:'#eaf1ff','text-anchor':'middle','font-size':10},temp(d.high)); prev={x,y};} else prev=null; add('text',{x,y:132,fill:'#bacbe3','text-anchor':'middle','font-size':10},d.date.slice(5));}); $('trend').append(svg);
}
$('search').addEventListener('submit',e=>{e.preventDefault();search($('city').value.trim());});
$('unit').addEventListener('click',()=>{fahrenheit=!fahrenheit; $('unit').textContent=fahrenheit?'°F / °C':'°C / °F'; $('unit').setAttribute('aria-label',fahrenheit?'Switch to Celsius':'Switch to Fahrenheit');render();});
$('sort').addEventListener('change',renderDays); $('filter').addEventListener('change',renderDays);
search('Kigali',true);
