"""DolphinTrade Monitor UI - start/stop the live monitor and watch
real-time updates in the browser (no extra dependencies, stdlib only).

Run:   python monitor_ui.py [--port 8765]
Open:  http://localhost:8765

The UI spawns live_loop.py as a subprocess, tails its output, parses
decisions/signals/agent status and streams them to the page via
Server-Sent Events. Start/Stop manage the subprocess.
"""

import argparse
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

CURR = os.path.dirname(os.path.abspath(__file__))
LOOP_CMD = [sys.executable, os.path.join(CURR, 'live_loop.py')]
SIGNALS_CSV = os.path.join(CURR, 'signals.csv')

EVENTS = queue.Queue()
STATE = {'proc': None, 'start_args': [], 'log': [], 'running': False}
SIGNAL_BUF = []


def emit(event):
    EVENTS.put(event)


def parse_signal_block():
    """Emit a parsed signal from the collected KEY: VALUE lines."""
    sig = {}
    for line in SIGNAL_BUF:
        m = re.match(r'^\s*(.+?)\s*:\s*(.*)$', line)
        if m:
            sig[m.group(1).strip()] = m.group(2).strip()
    if sig:
        emit({'type': 'signal', 'signal': sig})


def tail(proc):
    try:
        for line in proc.stdout:
            line = line.rstrip()
            STATE['log'].append(line)
            STATE['log'] = STATE['log'][-600:]
            emit({'type': 'log', 'line': line, 'ts': time.time()})
            if 'DOLPHIN TRADE SIGNAL' in line:
                SIGNAL_BUF.clear()
            elif SIGNAL_BUF is not None:
                if re.match(r'^\s*.+?\s*:\s*', line):
                    SIGNAL_BUF.append(line)
                elif SIGNAL_BUF:
                    parse_signal_block()
                    SIGNAL_BUF.clear()
            m = re.match(
                r'^(\S+)\s+TF\s+(\S+)\s+EXP\s+(\S+):\s+(CALL|PUT|NEUTRAL)\s+'
                r'P=([\d.]+)\s+ev=([-\d.]+)\s+\((.*)\)$', line)
            if m:
                # the DECISION-JSON line carries the full price context; the
                # plain-text line is skipped for table purposes but kept in log
                pass
            if 'DECISION-JSON ' in line:
                try:
                    d = json.loads(line.split('DECISION-JSON ', 1)[1])
                    emit({'type': 'decision',
                          'symbol': d.get('symbol', ''),
                          'tf': d.get('tf', ''),
                          'expiry': d.get('expiry', ''),
                          'action': d.get('action', 'NEUTRAL'),
                          'p': d.get('best_prob', 0.0),
                          'open': d.get('candle_open', '-'),
                          'close': d.get('candle_close_price', '-'),
                          'entry': d.get('entry_price', '-'),
                          'tp': d.get('target_price', '-'),
                          'sl': d.get('stop_loss', '-'),
                          'ts': time.time()})
                except Exception:
                    pass
                continue
            if 'news agent:' in line or 'ORCHESTRATOR READY' in line or \
               'headline agent' in line or 'outside trading window' in line or \
               'no signal this cycle' in line or 'live loop started' in line or \
               'AGENT-CONTEXT' in line or 'llm_sentiment' in line:
                emit({'type': 'agent', 'line': line, 'ts': time.time()})
    finally:
        STATE['running'] = False
        emit({'type': 'status', 'running': False})


def start_monitor(args):
    if STATE['proc'] and STATE['proc'].poll() is None:
        return False, 'already running'
    cmd = LOOP_CMD + args
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, bufsize=1, cwd=CURR)
    STATE['proc'] = p
    STATE['start_args'] = args
    STATE['running'] = True
    threading.Thread(target=tail, args=(p,), daemon=True).start()
    return True, 'started'


def stop_monitor():
    p = STATE['proc']
    if p and p.poll() is None:
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
        STATE['running'] = False
        emit({'type': 'status', 'running': False})
        return True
    return False


def recent_signals(n=25):
    if not os.path.exists(SIGNALS_CSV):
        return []
    import csv
    with open(SIGNALS_CSV) as f:
        rows = list(csv.DictReader(f))
    return rows[-n:]


def recent_trades(n=30):
    try:
        import csv as _csv
        path = os.path.join(CURR, 'trades.csv')
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return list(_csv.DictReader(f))[-n:]
    except Exception:
        return []


PAGE = r"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>DolphinTrade Monitor</title>
<style>
:root{--bg:#0b0f14;--panel:#131a23;--panel2:#0f151d;--border:#223042;--text:#dbe4ee;
--dim:#7d8ea3;--green:#2ecc71;--red:#ff5c5c;--blue:#4da3ff;--amber:#ffb84d;--purple:#b08cff}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font:14px/1.5 'Segoe UI',system-ui,sans-serif}
.wrap{max-width:1300px;margin:0 auto;padding:16px}

/* top bar */
.top{display:flex;align-items:center;gap:16px;background:var(--panel);
border:1px solid var(--border);border-radius:12px;padding:12px 18px;margin-bottom:14px}
.logo{font-size:19px;font-weight:700;color:var(--blue)}
.logo span{color:var(--dim);font-weight:400;font-size:13px;margin-left:8px}
.pill{padding:5px 14px;border-radius:20px;font-weight:700;font-size:12.5px;letter-spacing:.4px}
.pill.run{background:#0e2a1c;color:var(--green);border:1px solid var(--green);animation:pulse 1.6s infinite}
.pill.stop{background:#2a1212;color:var(--red);border:1px solid var(--red)}
@keyframes pulse{50%{opacity:.55}}
.meta{margin-left:auto;color:var(--dim);font-size:12.5px;text-align:right}
.meta b{color:var(--text)}
button{background:var(--blue);color:#05101f;border:0;padding:9px 20px;border-radius:8px;
font-weight:700;font-size:13.5px;cursor:pointer}
button.stop{background:var(--red);color:#fff}
button:disabled{opacity:.35;cursor:default}

/* config */
.cfg{background:var(--panel);border:1px solid var(--border);border-radius:12px;
padding:12px 18px;margin-bottom:14px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.cfg label{color:var(--dim);font-size:12px}
.cfg input,.cfg select{background:var(--panel2);color:var(--text);border:1px solid var(--border);
border-radius:6px;padding:6px 8px;font-size:13px}
.cfg .grp{display:flex;align-items:center;gap:6px}

/* layout */
.grid{display:grid;grid-template-columns:1.55fr 1fr;gap:14px}
@media(max-width:1000px){.grid{grid-template-columns:1fr}}
.card{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:14px 16px;margin-bottom:14px}
.card h2{font-size:12px;color:var(--dim);text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;
display:flex;align-items:center;gap:8px}
.card h2 .n{background:#1b2a3d;color:var(--blue);border-radius:10px;padding:0 8px;font-size:11px}

/* signal cards */
.sig{background:var(--panel2);border:1px solid var(--green);border-left:5px solid var(--green);
border-radius:10px;padding:12px 14px;margin-bottom:10px}
.sig.put{border-color:var(--red);border-left-color:var(--red)}
.sig .row1{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.badge{font-weight:800;font-size:16px;padding:4px 12px;border-radius:8px}
.badge.CALL{background:#0e2a1c;color:var(--green)}
.badge.PUT{background:#2a1212;color:var(--red)}
.sig .sym{font-weight:700;font-size:15px}
.sig .tag{color:var(--dim);font-size:12px}
.sig .big{font-size:15px;font-weight:700}
.sig .big .up{color:var(--green)}.sig .big .dn{color:var(--red)}
.sig .pips{color:var(--amber);font-size:12.5px;margin-top:4px}
.sig .why{color:var(--dim);font-size:12px;margin-top:5px}
.sig.new{animation:flash 1.2s}
@keyframes flash{0%{background:#173118}100%{background:var(--panel2)}}

/* table */
table{width:100%;border-collapse:collapse;font-size:13px}
th{color:var(--dim);text-align:left;padding:6px 8px;border-bottom:1px solid var(--border);font-size:11.5px;text-transform:uppercase;letter-spacing:.5px}
td{padding:6px 8px;border-bottom:1px solid #1a2533;font-variant-numeric:tabular-nums}
tr:hover td{background:#16202d}
.a-CALL{color:var(--green);font-weight:700}.a-PUT{color:var(--red);font-weight:700}.a-NEUTRAL{color:var(--dim)}
.scroll{max-height:380px;overflow:auto}

/* agents */
.ag{display:flex;justify-content:space-between;align-items:center;padding:8px 2px;border-bottom:1px solid #1a2533;font-size:13px}
.ag:last-child{border-bottom:0}
.chip{font-size:12px;font-weight:700;padding:2px 10px;border-radius:12px}
.chip.bullish{background:#0e2a1c;color:var(--green)}
.chip.bearish{background:#2a1212;color:var(--red)}
.chip.neutral{background:#1b2530;color:var(--dim)}
.count{font-size:13px;color:var(--text)}
.count b{font-size:17px;color:var(--blue)}
#nextEvent{font-size:13px}
#cd{font-weight:800;color:var(--amber);font-variant-numeric:tabular-nums}
.hint{color:var(--dim);font-size:12px;margin-top:8px}

/* log */
details{margin-top:6px}
summary{cursor:pointer;color:var(--dim);font-size:12.5px;user-select:none}
#log{max-height:300px;overflow:auto;background:var(--panel2);border:1px solid var(--border);
border-radius:8px;padding:10px;font-family:ui-monospace,Menlo,monospace;font-size:11.5px;margin-top:8px;white-space:pre-wrap}
.empty{color:var(--dim);text-align:center;padding:18px;font-size:13px}
</style></head><body><div class="wrap">

<div class="top">
  <div class="logo">&#128044; DolphinTrade <span>multi-agent monitor</span></div>
  <span id="pill" class="pill stop">STOPPED</span>
  <div class="meta">
    <div>Uptime: <b id="uptime">--</b> &nbsp;|&nbsp; Last cycle: <b id="lastCycle">--</b></div>
    <div>Signals today: <b id="sigCount">0</b> &nbsp;|&nbsp; Decisions: <b id="decCount">0</b></div>
  </div>
  <button id="btnStart">&#9654; Start Monitor</button>
  <button id="btnStop" class="stop" disabled>&#9632; Stop</button>
</div>

<div class="cfg">
  <div class="grp"><label>Feed</label><select id="feed"><option value="olymp">olymp (live)</option><option value="csv">csv (sim)</option></select></div>
  <div class="grp"><label>Pairs</label><input id="pairs" value="EURUSD,EURJPY,GBPUSD,USDCAD,USDJPY" style="width:230px"></div>
  <div class="grp"><label>Combos</label><input id="combos" value="5m:15m,5m:30m,5m:1h,15m:1h,30m:1h" style="width:210px"></div>
  <div class="grp"><label>P gate</label><input id="theta" value="0.65" style="width:56px"></div>
  <div class="grp"><label>Hours (UTC)</label><input id="hours" value="all" style="width:56px" title="e.g. 15-17 = window mode"></div>
  <div class="grp"><label>Equity</label><input id="equity" value="1000" style="width:64px"></div>
</div>

<div class="grid">
<div>
  <div class="card"><h2><span>&#128200;</span> Live signals (CALL / PUT) <span class="n" id="sigLiveN">0</span></h2>
    <div class="scroll"><table>
      <thead><tr><th>Time</th><th>Symbol</th><th>TF</th><th>Exp</th><th>Signal</th><th>P</th><th>Open</th><th>Close</th><th>Entry</th><th>Exit</th><th>Take Profit</th><th>Stop Loss</th><th>Expiry Time</th><th>Result</th></tr></thead>
      <tbody id="signalsBody"></tbody></table></div>
  </div>
  <div class="card"><h2><span>&#9899;</span> Neutral checks <span class="n" id="neuN">0</span></h2>
    <div class="scroll"><table>
      <thead><tr><th>Time</th><th>Symbol</th><th>TF</th><th>Exp</th><th>Signal</th><th>P</th><th>Open</th><th>Close</th><th>Entry</th><th>Exit</th><th>Take Profit</th><th>Stop Loss</th><th>Expiry Time</th><th>Result</th></tr></thead>
      <tbody id="neutralBody"></tbody></table></div>
  </div>
  <div class="card"><h2><span>&#128227;</span> Trading signals <span class="n" id="sigN">0</span></h2>
    <div class="scroll"><table>
      <thead><tr><th>Time</th><th>Symbol</th><th>TF</th><th>Exp</th><th>Signal</th><th>P</th><th>Open</th><th>Close</th><th>Entry</th><th>Exit</th><th>Take Profit</th><th>Stop Loss</th><th>Expiry Time</th><th>Result</th></tr></thead>
      <tbody id="signals"></tbody></table></div>
  </div>
</div>
<div>
  <div class="card"><h2><span>&#129504;</span> Market agents</h2>
    <div id="agents">
      <div class="ag"><span>News feed</span><span class="count" id="evCount">-- events</span></div>
      <div class="ag"><span>Next high-impact event</span><span id="nextEvent">--</span></div>
      <div class="ag"><span>Countdown</span><span id="cd">--</span></div>
      <div class="ag"><span>LLM sentiment</span><span id="llm">off</span></div>
    </div>
    <div class="hint">Headline sentiment per pair (Gemini when key is set):</div>
    <div id="senti"></div>
    <div id="riskLines"></div>
  </div>
  <div class="card"><h2><span>&#128241;</span> Latest activity</h2><div id="act"></div></div>
  <div class="card"><h2><span>&#128268;</span> Console</h2>
    <details><summary>show raw log</summary><pre id="log"></pre></details>
  </div>
</div>
</div>
</div>

<script>
const $=id=>document.getElementById(id);
let running=false,startedAt=0,lastDec=0,sigToday=0,decCount=0;

function setRunning(r){running=r;
 $('pill').className='pill '+(r?'run':'stop');
 $('pill').textContent=r?'RUNNING':'STOPPED';
 $('btnStart').disabled=r;$('btnStop').disabled=!r;
 if(r&&!startedAt)startedAt=Date.now();}
function fmtT(ts){const d=new Date(ts*1000);return d.toUTCString().slice(17,25);}
function uptime(){if(!startedAt){$('uptime').textContent='--';return}
 const s=Math.floor((Date.now()-startedAt)/1000);
 $('uptime').textContent=Math.floor(s/3600)+'h '+Math.floor(s%3600/60)+'m '+s%60+'s';}
setInterval(uptime,1000);

function addDecision(d){decCount++;$('decCount').textContent=decCount;
 const expMin=parseInt(d.expiry)||15;
 const expTs=new Date(new Date(d.ts*1000).getTime()+expMin*60000);
 const isSig=(d.action==='CALL'||d.action==='PUT');
 if(isSig)$('sigLiveN').textContent=parseInt($('sigLiveN').textContent)+1;
 else $('neuN').textContent=parseInt($('neuN').textContent)+1;
 const tr=document.createElement('tr');
 if(!isSig)tr.style.color='var(--dim)';
 tr.innerHTML=`<td>${fmtT(d.ts)}</td><td>${d.symbol}</td><td>${d.tf}</td><td>${d.expiry}</td>
  <td class="a-${d.action}">${d.action==='CALL'?'BUY':d.action==='PUT'?'SELL':d.action}</td><td>${(+d.p).toFixed(3)}</td>
  <td>${d.open||'-'}</td><td>${d.close||'-'}</td><td>${d.entry||'-'}</td><td>-</td>
  <td>${d.tp||'-'}</td><td>${d.sl||'-'}</td><td>${expTs.toUTCString().slice(17,25)}</td><td>-</td>`;
 const body=isSig?$('signalsBody'):$('neutralBody');
 body.prepend(tr);
 while(body.children.length>40)body.removeChild(body.lastChild);
 lastDec=Date.now();}

function tradeRow(t){const tr=document.createElement('tr');
 const isBuy=(String(t.action||'').toUpperCase()==='CALL');
 const res=String(t.result||'').toUpperCase();
 const resColor=res==='WIN'?'var(--green)':res==='LOSS'?'var(--red)':'var(--dim)';
 const expTime=t.expiry_time||'';
 tr.innerHTML=`<td>${String(t.ts||'').slice(11,19)}</td><td>${t.symbol||''}</td><td>${t.tf||''}</td><td>${t.expiry||''}</td>
  <td class="a-${isBuy?'CALL':'PUT'}">${isBuy?'BUY':'SELL'}</td><td>-</td>
  <td>${t.candle_open||'-'}</td><td>${t.candle_close||'-'}</td><td>${t.entry||'-'}</td>
  <td>${t.exit_price||'-'}</td><td>${t.take_profit||'-'}</td><td>${t.stop_loss||'-'}</td>
  <td>${expTime}</td><td style="color:${resColor};font-weight:700">${t.result||(t.status==='open'?'OPEN':'')}</td>`;
 return tr;}

function addSignal(d){sigToday++;$('sigCount').textContent=sigToday;$('sigN').textContent=sigToday;
 const expMin=parseInt(d.expiry)||15;
 const expTs=new Date(new Date().getTime()+expMin*60000);
 const tr=document.createElement('tr');
 tr.innerHTML=`<td>${new Date().toUTCString().slice(17,25)}</td><td>${d.symbol||''}</td><td>${d.tf||''}</td><td>${d.expiry||''}</td>
  <td class="a-${String(d.action).toUpperCase()==='PUT'?'PUT':'CALL'}">${String(d.action).toUpperCase()==='PUT'?'SELL':'BUY'}</td><td>${d.P||'-'}</td>
  <td>${d['CANDLE O']?d['CANDLE O'].split(' ')[0]:'-'}</td><td>${d['CANDLE L']?d['CANDLE L'].split(' ')[1]||d['CANDLE L']:'-'}</td>
  <td>${d.ENTRY||'-'}</td><td>-</td><td>${d.TARGET||'-'}</td><td>${d.STOP||'-'}</td>
  <td>${expTs.toUTCString().slice(17,25)}</td><td>OPEN</td>`;
 $('signals').prepend(tr);
 while($('signals').children.length>40)$('signals').removeChild($('signals').lastChild);}

function refreshTrades(){fetch('/trades').then(r=>r.json()).then(list=>{
  $('signals').innerHTML='';
  if(!list||!list.length){
    const tr=document.createElement('tr');
    tr.innerHTML='<td colspan="14" class="empty">No trades yet - signals will appear here when the gate fires.</td>';
    $('signals').appendChild(tr);
    return;
  }
  list.slice().reverse().forEach(t=>$('signals').appendChild(tradeRow(t)));
  $('sigN').textContent=list.length;$('sigCount').textContent=list.length;
  // merge settled results into live CALL/PUT rows by symbol+entry
  const rows=$('signalsBody').children;
  for(let i=0;i<rows.length;i++){const cells=rows[i].cells;
   if(!cells.length)continue;
   const sym=cells[1].textContent, entry=cells[8].textContent;
   const hit=list.find(t=>t.symbol===sym&&String(t.entry)===entry&&t.result);
   if(hit&&cells[13])cells[13].textContent=hit.result;
   if(hit&&cells[13])cells[13].style.color=hit.result==='WIN'?'var(--green)':hit.result==='LOSS'?'var(--red)':'var(--dim)';}
 }).catch(()=>{});}
refreshTrades();
setInterval(refreshTrades,8000);

function addActivity(line){const d=document.createElement('div');
 d.style.cssText='padding:4px 0;border-bottom:1px solid #1a2533;font-size:12.5px;color:var(--dim)';
 d.textContent=line; $('act').prepend(d);
 while($('act').children.length>12)$('act').removeChild($('act').lastChild);}

function agentContext(m){
 try{m=JSON.parse(m)}catch(e){return}
 $('evCount').textContent=m.events_total+' events';
 $('nextEvent').textContent=m.next_event||'--';
 $('cd').textContent='--';
 if(m.next_event_time){
  const t=new Date(m.next_event_time.replace(' ','T')+'Z').getTime();
  const tick=()=>{const s=Math.max(0,Math.floor((t-Date.now())/1000));
   $('cd').textContent=Math.floor(s/3600)+'h '+Math.floor(s%3600/60)+'m';
   if(s<=0)$('cd').textContent='now';};
  tick();setInterval(tick,1000);}
 if(m.sentiment){$('senti').innerHTML='';
  Object.entries(m.sentiment).forEach(([p,s])=>{
   const c=document.createElement('div');c.className='ag';
   c.innerHTML=`<span>${p}</span><span class="chip ${s}">${s}</span>`;
   $('senti').appendChild(c);});}}

function addLog(line){$('log').textContent+=line+'\n';
 $('log').scrollTop=$('log').scrollHeight;}

$('btnStart').onclick=()=>fetch('/start',{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify({feed:$('feed').value,pairs:$('pairs').value,combos:$('combos').value,
  theta:parseFloat($('theta').value),hours:$('hours').value,equity:parseFloat($('equity').value)})})
 .then(r=>r.json()).then(m=>{if(m.running)setRunning(true);});
$('btnStop').onclick=()=>fetch('/stop',{method:'POST'}).then(()=>setRunning(false));

// sync button state with the real monitor on page load
fetch('/status').then(r=>r.json()).then(s=>setRunning(s.running));

const es=new EventSource('/events');
es.onmessage=e=>{const m=JSON.parse(e.data);
 if(m.type==='status')setRunning(m.running);
 else if(m.type==='decision')addDecision(m);
 else if(m.type==='signal')addSignal(m.signal);
 else if(m.type==='agent'){addActivity(m.line);
   if(m.line.includes('AGENT-CONTEXT'))agentContext(m.line.split('AGENT-CONTEXT ')[1]);
   if(m.line.includes('news agent:')){const mm=m.line.match(/(\d+) events/);if(mm)$('evCount').textContent=mm[1]+' events';}
   if(m.line.includes('llm_sentiment=True'))$('llm').textContent='gemini on';}
  else if(m.type==='log')addLog(m.line);};
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/':
            body = PAGE.encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == '/events':
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            try:
                # snapshot the current state to this client on connect
                self.wfile.write(('data: ' + json.dumps(
                    {'type': 'status', 'running': STATE['running']}) + '\n\n').encode())
                self.wfile.flush()
                while True:
                    try:
                        ev = EVENTS.get(timeout=2)
                    except queue.Empty:
                        continue
                    data = json.dumps(ev)
                    self.wfile.write(f'data: {data}\n\n'.encode())
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
        elif path == '/status':
            self._send_json({'running': STATE['running'],
                             'args': STATE['start_args'],
                             'log_tail': STATE['log'][-20:]})
        elif path == '/signals':
            self._send_json(recent_signals())
        elif path == '/trades':
            self._send_json(recent_trades())
        else:
            self._send_json({'error': 'not found'}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        if path == '/start':
            args = []
            if body.get('feed') and body['feed'] != 'olymp':
                args += ['--feed', body['feed']]
            if body.get('pairs'):
                args += ['--pairs', body['pairs']]
            if body.get('combos'):
                args += ['--combos', body['combos']]
            if body.get('theta'):
                args += ['--theta', str(body['theta'])]
            if body.get('hours') and body['hours'] not in ('', 'all'):
                args += ['--hours', body['hours']]
            if body.get('equity'):
                args += ['--equity', str(body['equity'])]
            ok, msg = start_monitor(args)
            self._send_json({'ok': ok, 'msg': msg, 'running': STATE['running']})
        elif path == '/stop':
            ok = stop_monitor()
            self._send_json({'ok': ok, 'running': False})
        else:
            self._send_json({'error': 'not found'}, 404)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--host', default='127.0.0.1')
    args = ap.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f'DolphinTrade Monitor UI: http://{args.host}:{args.port}')
    print('Start the monitor from the page, or pre-configure by editing the config fields.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        stop_monitor()
        print('\nstopped')


if __name__ == '__main__':
    main()
