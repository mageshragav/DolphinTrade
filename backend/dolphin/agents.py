"""Multi-agent decision framework - real-time news + market analysis.

Agents (each analyzes its domain before the orchestration decision):

  MarketAgent      wraps DecisionService: per-combo ML probabilities
  NewsAgent        real-time economic calendar (ForexFactory JSON, live feed)
  HeadlineAgent    real-time Google News RSS headlines + sentiment per pair
  RiskAgent        market microstructure: fakeout wicks, spread anomalies,
                   volatility regime
  OrchestratorAgent combines all agents: veto logic, sentiment context,
                   event-momentum channel, final decision + rationale

Sentiment is lexicon-based by default; when OPENAI_API_KEY or
ANTHROPIC_API_KEY is set, headlines are scored by the LLM instead.
Every network call is wrapped - a feed failure degrades to neutral and
never crashes the loop.
"""

import json
import logging
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import ta

LOGGER = logging.getLogger('dolphin')

FF_URL = 'https://nfs.faireconomy.media/ff_calendar_thisweek.json'
GNEWS_URL = 'https://news.google.com/rss/search?q={}&hl=en-US&gl=US&ceid=US:en'
UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/151.0.0.0 Safari/537.36',
      'Accept': 'application/json,text/plain,*/*', 'Accept-Language': 'en-US,en;q=0.9'}

NEWS_VETO_MIN = (-5, 20)      # minutes around a High release where no ML trade
EVENT_FIRE_WINDOW = (2, 7)    # minutes after a release when event-momentum fires
SPIKE_ATR = 0.5

IMPACT_ORDER = {'low': 0, 'medium': 1, 'high': 2}

BULLISH = {'rally', 'rallying', 'gains', 'rises', 'rising', 'surge', 'jumps', 'jump', 'strength',
           'bullish', 'boost', 'climbs', 'soar', 'higher', 'hawkish', 'taper', 'outperform',
           'strong', 'grows', 'growth', 'rebound', 'recovery', 'buy'}
BEARISH = {'fall', 'falls', 'falling', 'drops', 'drop', 'decline', 'slump', 'weakness', 'weak',
           'bearish', 'selloff', 'plunge', 'losses', 'lower', 'dovish', 'recession', 'cut',
           'cuts', 'underperform', 'pressured', 'pressure', 'sell', 'slide'}

PAIR_CURRENCY = {'EURUSD': 'USD', 'EURCAD': 'EUR', 'EURJPY': 'EUR', 'EURGBP': 'EUR',
                 'EURAUD': 'EUR', 'GBPUSD': 'GBP', 'USDCAD': 'USD', 'USDJPY': 'USD',
                 'AUDUSD': 'USD'}


def _http_json(url, data=None, timeout=12):
    req = urllib.request.Request(url, headers=UA, data=data)
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def _http_text(url, timeout=12):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8', 'ignore')


def normalize_candles(candles):
    """Convert olymp wire format (t/o/h/l/c/v) to datetime/open/high/low/close."""
    df = candles.copy()
    if 'o' in df.columns and 'open' not in df.columns:
        df = df.rename(columns={'o': 'open', 'h': 'high', 'l': 'low',
                                'c': 'close', 'v': 'volume'})
    if 'datetime' not in df.columns and 't' in df.columns:
        df['datetime'] = pd.to_datetime(df['t'], unit='s', utc=True)
    df['datetime'] = pd.to_datetime(df['datetime'])
    if df['datetime'].dt.tz is not None:
        df['datetime'] = df['datetime'].dt.tz_localize(None)
    return df


# ---------------------------------------------------------------------------
# Agent 1: market (wraps the ML service)
# ---------------------------------------------------------------------------

class MarketAgent:
    def __init__(self, service):
        self.service = service

    def analyze(self, candles, combos, equity=1000.0, now=None):
        return self.service.decide_all(candles, combos=combos, equity=equity, now=now)


# ---------------------------------------------------------------------------
# Agent 2: real-time economic calendar
# ---------------------------------------------------------------------------

class NewsAgent:
    def __init__(self, refresh_sec=300):
        self.refresh_sec = refresh_sec
        self.events = []
        self._last_fetch = 0

    def refresh(self, force=False):
        if not force and time.time() - self._last_fetch < self.refresh_sec:
            return
        self._last_fetch = time.time()
        try:
            payload = _http_json(FF_URL)
            events = []
            for e in payload or []:
                impact = (e.get('impact') or 'low').lower()
                if impact not in IMPACT_ORDER:
                    continue
                try:
                    t = pd.Timestamp(e['date'])
                    if t.tzinfo is not None:
                        t = t.tz_localize(None)
                except Exception:
                    continue
                events.append({'time': t.to_pydatetime(), 'currency': str(e.get('country', '')),
                               'impact': impact, 'title': str(e.get('title', '')),
                               'forecast': e.get('forecast'), 'previous': e.get('previous')})
            if events:
                self.events = events
            LOGGER.info(f'news agent: {len(events)} events loaded from live feed')
        except Exception as e:
            LOGGER.warning(f'news agent feed failed (keeping {len(self.events)} cached events): {e}')

    def relevant(self, symbol, now):
        cur = PAIR_CURRENCY.get(symbol.split(':')[-1], 'USD')
        return [e for e in self.events if e['currency'] in (cur, 'ALL')]

    def veto(self, now=None, symbol=None, blackout_min=0):
        """High-impact release inside NEWS_VETO_MIN -> (veto, event).

        With blackout_min > 0, medium+high impact events for the pair's
        currencies inside +/-blackout_min also veto (FFCal-style news
        blackout; 0 = off, keeping the validated default behavior).
        """
        now = now or datetime.now()
        cur = PAIR_CURRENCY.get(symbol.split(':')[-1], 'USD') if symbol else None
        for e in self.events:
            if symbol and e['currency'] not in (cur, 'ALL'):
                continue
            delta_min = (e['time'] - now).total_seconds() / 60.0
            if e['impact'] == 'high' and NEWS_VETO_MIN[0] <= delta_min <= NEWS_VETO_MIN[1]:
                return True, e
            if blackout_min and e['impact'] in ('high', 'medium') \
                    and abs(delta_min) <= blackout_min:
                return True, e
        return False, None

    def fired_events(self, now=None, symbol=None, window_min=30):
        """High-impact releases inside the last `window_min` minutes."""
        now = now or datetime.now()
        out = []
        for e in self.events:
            if e['impact'] != 'high':
                continue
            if symbol and e['currency'] not in (PAIR_CURRENCY.get(symbol.split(':')[-1], 'USD'),):
                continue
            age_min = (now - e['time']).total_seconds() / 60.0
            if 0 <= age_min <= window_min:
                out.append(e)
        return out

    def upcoming(self, now=None, symbol=None):
        now = now or datetime.now()
        out = []
        for e in self.events:
            if symbol and e['currency'] not in (PAIR_CURRENCY.get(symbol.split(':')[-1], 'USD'),):
                continue
            if e['time'] > now:
                out.append(e)
        out.sort(key=lambda e: e['time'])
        return out

    def event_features(self, symbol, now=None):
        nxt = self.upcoming(now, symbol)
        if not nxt:
            return {'hours_to_event': 999.0, 'in_event_window': 0.0, 'next_impact': 0.0,
                    'event_direction': 0.0}
        e = nxt[0]
        delta_h = (e['time'] - (now or datetime.now())).total_seconds() / 3600.0
        direction = 0.0
        if e['forecast'] and e['previous']:
            try:
                f = float(str(e['forecast']).replace('%', '').replace('K', 'e3'))
                p = float(str(e['previous']).replace('%', '').replace('K', 'e3'))
                direction = 1.0 if f > p else (2.0 if f < p else 0.0)
            except (TypeError, ValueError):
                direction = 0.0
        return {'hours_to_event': max(delta_h, 0.0), 'in_event_window': 1.0 if delta_h <= 1.0 else 0.0,
                'next_impact': float(IMPACT_ORDER[e['impact']]), 'event_direction': direction}


# ---------------------------------------------------------------------------
# Agent 3: real-time headlines + sentiment
# ---------------------------------------------------------------------------

class HeadlineAgent:
    def __init__(self, refresh_sec=600, use_llm=None):
        self.refresh_sec = refresh_sec
        self.headlines = {}
        self.sentiment = {}
        self._last_fetch = 0
        self.llm = self._init_llm() if (use_llm is None and self._has_key()) or use_llm else None

    @staticmethod
    def _has_key():
        return bool(os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
                    or os.environ.get('OPENAI_API_KEY') or os.environ.get('ANTHROPIC_API_KEY'))

    def _init_llm(self):
        try:
            if os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY'):
                from google import genai
                client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY')
                                      or os.environ.get('GOOGLE_API_KEY'))
                LOGGER.info('headline agent: Gemini LLM active '
                            f'(model={os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")})')
                return ('gemini', client)
            if os.environ.get('ANTHROPIC_API_KEY'):
                import anthropic
                return ('anthropic', anthropic.Anthropic())
            if os.environ.get('OPENAI_API_KEY'):
                import openai
                return ('openai', openai.OpenAI())
        except Exception as e:
            LOGGER.warning(f'LLM headline agent unavailable: {e}')
        return None

    def refresh(self, pairs=None, force=False):
        if not force and time.time() - self._last_fetch < self.refresh_sec:
            return
        self._last_fetch = time.time()
        for pair in (pairs or []):
            query = urllib.parse.quote(f'{pair.replace("FX:", "")} forex')
            try:
                xml = _http_text(GNEWS_URL.format(query))
                titles = re.findall(r'<item>.*?<title>(.*?)</title>', xml, re.S)[:8]
                titles = [re.sub(r'<!\[CDATA\[|\]\]>', '', t).strip() for t in titles]
                self.headlines[pair] = titles
                self.sentiment[pair] = self._score(titles, pair)
            except Exception as e:
                LOGGER.warning(f'headline agent failed for {pair}: {e}')
                self.headlines.setdefault(pair, [])
                self.sentiment.setdefault(pair, 0.0)

    def _score(self, titles, pair):
        if self.llm:
            try:
                return self._llm_score(titles, pair)
            except Exception as e:
                LOGGER.warning(f'llm sentiment failed: {e}')
        text = ' '.join(titles).lower()
        cur = PAIR_CURRENCY.get(pair.split(':')[-1], 'USD').lower()
        bullish = sum(1 for w in BULLISH if w in text)
        bearish = sum(1 for w in BEARISH if w in text)
        total = bullish + bearish
        return (bullish - bearish) / max(total, 1) if total else 0.0

    def _llm_score(self, titles, pair):
        joined = '\n'.join(titles)
        if self.llm[0] == 'gemini':
            r = self.llm[1].models.generate_content(
                model=os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash-lite'),
                contents='Classify the sentiment of these forex headlines for the pair '
                         f'{pair} as 1 (bullish), -1 (bearish), or 0 (neutral). '
                         'Reply with ONLY the single number.\n\n' + joined)
            return float(r.text.strip() or 0)
        if self.llm[0] == 'anthropic':
            r = self.llm[1].messages.create(
                model='claude-sonnet-4-20250514', max_tokens=10,
                system='You classify forex headline sentiment. Reply with ONE number: '
                       '1 bullish, -1 bearish, 0 neutral.',
                messages=[{'role': 'user', 'content': joined}])
            return float(r.content[0].text.strip() or 0)
        r = self.llm[1].chat.completions.create(
            model='gpt-4o-mini', max_tokens=10,
            messages=[{'role': 'system', 'content': 'Reply with ONE number: 1 bullish, '
                                                    '-1 bearish, 0 neutral.'},
                      {'role': 'user', 'content': joined}])
        return float(r.choices[0].message.content.strip() or 0)

    def bias(self, symbol):
        s = self.sentiment.get(symbol.replace('FX:', ''), 0.0)
        return 'bullish' if s > 0.2 else ('bearish' if s < -0.2 else 'neutral')

    def top(self, symbol):
        hs = self.headlines.get(symbol.replace('FX:', ''), [])
        return hs[0] if hs else None


# ---------------------------------------------------------------------------
# Agent 4: market microstructure risk
# ---------------------------------------------------------------------------

class RiskAgent:
    def __init__(self, wick_mult=2.5, atr_mult=2.0):
        self.wick_mult = wick_mult
        self.atr_mult = atr_mult

    def analyze(self, candles, now=None):
        """Per-symbol risk flags from the last completed candles."""
        candles = normalize_candles(candles)
        out = {}
        for symbol, grp in candles.groupby('symbol'):
            df = grp.sort_values('datetime').reset_index(drop=True)
            if len(df) < 30:
                continue
            tail = df.tail(6)
            atr = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14)
            a = atr.iloc[-2] if len(atr) > 1 else np.nan
            flags = []
            fakeouts = 0
            for i in range(len(tail) - 1):
                row = tail.iloc[i]
                body = abs(row['close'] - row['open'])
                wick = max(row['high'] - max(row['open'], row['close']),
                           min(row['open'], row['close']) - row['low'])
                if body > 0 and wick > self.wick_mult * body and not np.isnan(a) and wick > self.atr_mult * a:
                    fakeouts += 1
            if fakeouts >= 2:
                flags.append('fakeout_wicks')
            regime = 'high' if not np.isnan(a) and a > atr.tail(100).quantile(0.8) else \
                ('low' if not np.isnan(a) and a < atr.tail(100).quantile(0.2) else 'normal')
            out[symbol] = {'manipulation_risk': 'high' if flags else 'low',
                           'flags': flags, 'volatility_regime': regime}
        return out


# ---------------------------------------------------------------------------
# Orchestrator: combines all agents
# ---------------------------------------------------------------------------

class OrchestratorAgent:
    def __init__(self, market, news, headlines, risk, theta=0.65, sentiment_lift=0.0):
        self.market = market
        self.news = news
        self.headlines = headlines
        self.risk = risk
        self.theta = theta
        self.sentiment_lift = sentiment_lift

    def decide(self, candles, combos, equity=1000.0, now=None):
        now = now or datetime.now()
        market_decisions = self.market.analyze(candles, combos, equity=equity, now=now)
        risk_map = self.risk.analyze(candles, now=now)
        news_ctx = {}

        for d in market_decisions:
            sym = d['symbol']
            veto, evt = self.news.veto(now, sym)
            bias = self.headlines.bias(sym)
            risk = risk_map.get(sym, {})
            ctx = news_ctx.setdefault(sym, {'veto': veto, 'event': evt,
                                            'bias': bias, 'risk': risk,
                                            'headline': self.headlines.top(sym)})
            d['news_veto'] = veto
            d['news_next'] = (evt or {}).get('title') if veto else None
            d['sentiment_bias'] = bias
            d['manipulation_risk'] = risk.get('manipulation_risk', 'low')
            d['headline'] = ctx['headline']
            if veto or risk.get('manipulation_risk') == 'high':
                d['action'] = 'NEUTRAL'
                d['rationale'] = (f'veto:{evt.get("title")}' if veto else 'risk:high') + \
                                 ' | ' + d['rationale']
            elif self.sentiment_lift and bias != 'neutral':
                if (bias == 'bullish' and d['action'] == 'CALL') or \
                   (bias == 'bearish' and d['action'] == 'PUT'):
                    d['best_prob'] = min(0.99, d['best_prob'] + self.sentiment_lift)

        event_decisions = self._event_channel(candles, now)
        return market_decisions + event_decisions

    def _event_channel(self, candles, now):
        """Event-momentum: strong spike right after a High release (cont mode)."""
        candles = normalize_candles(candles)
        out = []
        for symbol, grp in candles.groupby('symbol'):
            fired = self.news.fired_events(now, symbol)
            if not fired:
                continue
            df = grp.sort_values('datetime').reset_index(drop=True)
            for e in fired:
                age_min = (now - e['time']).total_seconds() / 60.0
                if not (EVENT_FIRE_WINDOW[0] <= age_min <= EVENT_FIRE_WINDOW[1]):
                    continue
                cand = df[df['datetime'] >= e['time']]
                if cand.empty:
                    continue
                i0 = cand.index[0]
                if (df['datetime'].iloc[i0] - e['time']).total_seconds() > 900:
                    continue
                if i0 < 15 or i0 + 1 >= len(df):
                    continue
                atr = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14)
                a = atr.iloc[i0 - 1]
                body = df['close'].iloc[i0] - df['open'].iloc[i0]
                if np.isnan(a) or a <= 0 or abs(body) < SPIKE_ATR * a:
                    continue
                direction = 'CALL' if body > 0 else 'PUT'
                out.append({
                    'symbol': symbol, 'tf': '5m', 'expiry': '15m', 'action': direction,
                    'best_prob': min(0.65, 0.5 + abs(body) / a * 0.15), 'ev_score': 0.0,
                    'stake': 0.0, 'news_veto': False, 'model': 'EVENT-cont',
                    'strategy': 'event', 'event_title': e['title'],
                    'spike_atr': round(abs(body) / a, 2),
                    'entry_price': round(float(df['close'].iloc[i0]), 5),
                    'candle_close': str(df['datetime'].iloc[i0]),
                    'rationale': f'EVENT {e["title"]} spike {abs(body)/a:.2f}x ATR -> {direction}',
                })
        return out
