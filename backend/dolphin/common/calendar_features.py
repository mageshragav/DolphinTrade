"""Economic calendar features for live trading (news veto + direction bias).

Live-only module: fetches the current week's high-impact events from the
free ForexFactory JSON endpoint, aligned to the broker's timezone. When the
feed is unavailable (or offline/backtest), all features return neutral so
the pipeline degrades gracefully to "no news information".

Wired into the live decision flow as:
  - hard veto: no trade if a HIGH-impact event fires within VETO_MINUTES
  - ML features: time_to_next_event, next_impact, event_direction (1/2/0)
"""

from datetime import datetime, timedelta
import json
import logging
import urllib.request

LOGGER = logging.getLogger('dolphin')

FF_JSON_URL = 'https://nfs.faireconomy.media/ff_calendar_thisweek.json'
VETO_MINUTES = 15
IMPACT_ORDER = {'low': 0, 'medium': 1, 'high': 2}


class EconomicCalendar:
    def __init__(self, url=FF_JSON_URL, tz_offset_hours=0):
        self.url = url
        self.tz_offset_hours = tz_offset_hours  # broker server UTC offset
        self.events = []                        # list of event dicts
        self._loaded_at = None

    # -- data loading -----------------------------------------------------

    def refresh(self):
        """Fetch the current week's calendar. Never raises (degrade to empty)."""
        try:
            with urllib.request.urlopen(self.url, timeout=10) as r:
                payload = json.loads(r.read().decode('utf-8'))
            self.events = self._parse(payload)
            self._loaded_at = datetime.now()
            LOGGER.info(f'calendar loaded: {len(self.events)} events')
        except Exception as e:
            LOGGER.warning(f'calendar fetch failed: {e}')
            self.events = []
        return len(self.events)

    @staticmethod
    def _parse(payload):
        events = []
        for e in payload or []:
            impact = (e.get('impact') or 'low').lower()
            if impact not in IMPACT_ORDER:
                impact = 'low'
            events.append({
                'time': e.get('date'),              # '2024-07-05T12:30:00-04:00'
                'currency': e.get('country', ''),
                'title': e.get('title', ''),
                'impact': impact,
                'forecast': e.get('forecast'),
                'previous': e.get('previous'),
            })
        return events

    # -- queries ----------------------------------------------------------

    def next_event(self, now=None):
        now = now or datetime.now()
        upcoming = [e for e in self.events if e['time']]
        upcoming = [e for e in upcoming
                    if self._parse_time(e['time']) > now - timedelta(minutes=2)]
        if not upcoming:
            return None
        upcoming.sort(key=lambda e: self._parse_time(e['time']))
        return upcoming[0]

    def _parse_time(self, s):
        try:
            return datetime.fromisoformat(s)
        except Exception:
            return datetime.max

    def veto(self, now=None):
        """True if a HIGH-impact event fires within VETO_MINUTES."""
        nxt = self.next_event(now)
        if not nxt:
            return False, None
        delta = (self._parse_time(nxt['time']) - (now or datetime.now())).total_seconds()
        if nxt['impact'] == 'high' and 0 <= delta <= VETO_MINUTES * 60:
            return True, nxt
        return False, nxt

    def features(self, symbol='EURUSD', now=None):
        """Feature vector for the ML model (neutral when no data)."""
        nxt = self.next_event(now)
        if nxt is None:
            return {'time_to_next_event': 99999.0, 'next_impact': 0.0,
                    'event_direction': 0.0}
        delta_min = (self._parse_time(nxt['time']) - (now or datetime.now())).total_seconds() / 60.0
        currency = symbol[:3]
        relevant = (nxt['currency'] == currency) or (nxt['currency'] == 'USD' and symbol.endswith('USD'))
        direction = 0.0
        if relevant and nxt['forecast'] and nxt['previous']:
            try:
                f, p = float(nxt['forecast']), float(nxt['previous'])
                direction = 1.0 if f > p else (2.0 if f < p else 0.0)
            except (TypeError, ValueError):
                direction = 0.0
        return {'time_to_next_event': max(delta_min, 0.0),
                'next_impact': float(IMPACT_ORDER[nxt['impact']]),
                'event_direction': direction}
