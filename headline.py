#!/usr/bin/env python
"""headline.py — today's top headline + link for a ticker.

WHY (2026-07-20): bignames-scan printed GOOG +2.86% with nothing else, and the
run shipped without ever hunting a catalyst for it. A mover with no headline is
a lead nobody chased. Every scan row now carries its own headline + URL so the
"why" travels with the "what" instead of waiting for a separate fan-out.

Source: Yahoo Finance search news feed (free, no key, has publish timestamps).
This is a LEAD, not a verified catalyst — /SIPs §2.1 still confirms against a
primary source before anything goes in the brief.
"""
import json, urllib.request, datetime, re

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo('America/New_York')          # SIPs talks in ET, not Taipei local
except Exception:
    ET = None

UA = {'User-Agent': 'Mozilla/5.0'}

# generic market-wrap noise: real per-name catalysts beat these
NOISE = ('futures', 'stocks making the biggest', 'market chatter: us', 'wall street',
         'stock market today', 'premarket movers', 'what to watch', 'movers:',
         'stocks to watch', 'trading desk', 'sector update', 'market close',
         'than broader market', 'than the broader market', 'is a trending stock',
         'earnings roundup', 's&p 500', 'dow jones industrial', 'nasdaq composite',
         'end lower', 'end higher', 'close lower', 'close higher', 'market wrap', 'equity indexes', 'equity futures')
STOP = {'inc', 'inc.', 'corp', 'corp.', 'ltd', 'plc', 'the', 'company', 'holdings',
        'group', 'technologies', 'international', 'com'}

# 2026-07-20: the raw feed is dominated by SEO filler ("Dell Fell More Than the
# Broader Market", "Claude AI Sells Broadcom") that says nothing about WHY the
# stock moved. Weight wires + press releases up, content mills down.
PREFER = ('reuters', 'bloomberg', 'wall street journal', 'wsj', 'cnbc', 'barron',
          'mt newswires', 'investor\'s business daily', 'financial times',
          'globenewswire', 'business wire', 'pr newswire', 'associated press',
          'dow jones', 'marketwatch', 'stockstory')
# tickers whose legal name never appears in headlines — the press uses the brand
ALIAS = {'GOOGL': {'google'}, 'GOOG': {'google'}, 'META': {'facebook', 'instagram'},
         'BRK-B': {'berkshire'}, 'TSM': {'tsmc'}, 'BABA': {'alibaba'},
         'NVO': {'novo'}, 'RTX': {'raytheon'}, 'GEV': {'vernova'}}
WEAK = ('zacks', 'trefis', 'insider monkey', 'simply wall st', '24/7 wall st',
        'motley fool', 'gurufocus', 'investorshub', 'fx empire', 'benzinga',
        'the street', 'thestreet', 'stocktwits')


def top_headline(sym, max_age_h=36, timeout=12):
    """-> dict(title, url, publisher, published) or None."""
    u = (f'https://query1.finance.yahoo.com/v1/finance/search?q={sym}'
         f'&newsCount=8&quotesCount=1')
    try:
        d = json.load(urllib.request.urlopen(
            urllib.request.Request(u, headers=UA), timeout=timeout))
    except Exception:
        return None

    quotes = d.get('quotes') or []
    name = (quotes[0].get('shortname') or '') if quotes else ''
    tokens = {sym.lower()} | {w for w in (x.lower().strip('.,') for x in name.split()[:3])
                              if len(w) > 2 and w not in STOP} | ALIAS.get(sym, set())

    now = datetime.datetime.now(datetime.timezone.utc)
    best = None
    for n in d.get('news') or []:
        ts = n.get('providerPublishTime')
        title = n.get('title')
        link = n.get('link')
        if not (ts and title and link):
            continue
        pub = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)
        age = (now - pub).total_seconds() / 3600
        if age > max_age_h:
            continue
        low = title.lower()
        publisher = n.get('publisher') or ''
        # A headline that never names the company is a market wrap, not this
        # stock's catalyst — it only wins if literally nothing else is on offer.
        # word-boundary match: "Elevance Health" must not be satisfied by
        # "UnitedHealth" appearing in someone else's headline
        if any(t in low for t in NOISE):
            continue                 # index/market wrap is never a stock's catalyst
        # ...and the company must be the SUBJECT, not a ticker tacked on the end
        score = 4 if any(re.search(rf'\b{re.escape(t)}\b', low[:70]) for t in tokens) else -4
        pl = publisher.lower()
        if any(p in pl for p in PREFER):
            score += 2               # wire / press release: closest to a primary source
        if any(p in pl for p in WEAK):
            score -= 2               # SEO filler, not a catalyst
        if 'video' in pl:
            score -= 1               # a video segment is a weak lead vs a wire story
        score -= age / 24.0          # fresher wins ties
        if best is None or score > best[0]:
            best = (score, {'title': title, 'url': link, 'publisher': publisher,
                            'published': pub.astimezone(ET).strftime('%m-%d %H:%M ET')
                                         if ET else pub.strftime('%m-%d %H:%M UTC')})
    # score < 0 means nothing in the feed actually names this company. Returning
    # an unrelated article is worse than returning nothing: the scan prints
    # "NO HEADLINE FOUND" and the operator knows to hunt the catalyst by hand.
    return best[1] if best and best[0] > 0 else None
