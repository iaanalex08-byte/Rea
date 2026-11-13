"""Descarga velas de ES=F (Yahoo Finance): 1 minuto (últimos ~30 días, en tramos de 7) y 5 minutos (60 días)."""
import sys, json, time, urllib.request
import pandas as pd

def get(interval, p1=None, p2=None, rng=None):
    q = f'interval={interval}&includePrePost=true' + (f'&range={rng}' if rng else f'&period1={p1}&period2={p2}')
    r = urllib.request.Request(f'https://query2.finance.yahoo.com/v8/finance/chart/ES=F?{q}', headers={'User-Agent': 'Mozilla/5.0'})
    j = json.load(urllib.request.urlopen(r))['chart']['result'][0]
    qt = j['indicators']['quote'][0]
    df = pd.DataFrame(dict(o=qt['open'], h=qt['high'], l=qt['low'], c=qt['close'], v=qt['volume']),
                      index=pd.to_datetime(j['timestamp'], unit='s', utc=True))
    return df.dropna()

out = sys.argv[1]
now = int(time.time()) - 60
parts = [get('1m', now - k * 7 * 86400, now - (k - 1) * 7 * 86400) for k in range(4, 0, -1)]
m1 = pd.concat(parts).sort_index(); m1 = m1[~m1.index.duplicated()]
m5 = get('5m', rng='60d')
m1.to_pickle(f'{out}/es_1m.pkl'); m5.to_pickle(f'{out}/es_5m.pkl')
print('1m', m1.index[0], m1.index[-1], len(m1)); print('5m', m5.index[0], m5.index[-1], len(m5))
