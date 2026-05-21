"""Parse TradingView FQ earnings markdown files: extract reported + estimate raw figures + compute YoY block."""
import os, re, json, csv, sys

DIR = os.environ.get('SIPS_DIR') or os.path.dirname(os.path.abspath(__file__))

# Strip invisible/bidi unicode chars
BIDI_RE = re.compile(r'[​-‏‪-‮⁦-⁩﻿]')

def parse_num(v):
    if v == '—' or v == '-' or v == '–' or not v: return None
    c = v.replace(',', '').replace('−', '-')
    try: return float(c)
    except: return None

def parse_rev(v):
    """Revenue in millions (M)"""
    if v == '—' or not v: return None
    c = v.replace(',', '').replace('−', '-').replace(' ', '').strip()
    m = re.match(r'^(-?[\d.]+)([MBK])?$', c)
    if not m: return None
    n = float(m.group(1)); u = m.group(2)
    if u == 'B': return n * 1000.0
    elif u == 'M' or u is None: return n
    elif u == 'K': return n * 0.001

def yoy(curr, prior):
    if curr is None or prior is None: return 'N/M'
    if prior == 0: return 'N/M'
    # Universal "improvement = positive %, deterioration = negative %" formula.
    # Works for all sign combinations:
    #   both positive (5 → 8):         (8-5)/|5|     = +60%
    #   both negative (-0.41 → -0.77): (-0.77+0.41)/0.41 = -87.80%   (loss widened)
    #   loss → profit (-0.40 → 0.50):  (0.50+0.40)/0.40  = +225%     (improvement)
    #   profit → loss (0.50 → -0.40):  (-0.40-0.50)/0.50 = -180%     (deterioration)
    pct = (curr - prior) / abs(prior) * 100.0
    sign = '+' if pct >= 0 else ''
    return f'{sign}{pct:.2f}%'

def fmt_eps(v):
    if v is None: return '—'
    return f'{v:+.2f}' if v < 0 else f'{v:.2f}'

def fmt_rev(v):
    """Format revenue: B if >=1000, M otherwise"""
    if v is None: return '—'
    if abs(v) >= 1000: return f'{v/1000:.2f}B'
    return f'{v:.1f}M' if abs(v) >= 1 else f'{v*1000:.0f}K'

def parse_latest_report_date(content):
    """Extract 'Latest report date' from TV markdown. Returns ISO YYYY-MM-DD or None."""
    import datetime
    m = re.search(r'Latest report date\s*\n\s*([A-Z][a-z]+\s+\d{1,2},\s+\d{4})', content)
    if not m: return None
    raw = m.group(1)
    for fmt in ('%b %d, %Y', '%B %d, %Y'):
        try:
            return datetime.datetime.strptime(raw, fmt).strftime('%Y-%m-%d')
        except Exception:
            pass
    return None

def parse_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    content = BIDI_RE.sub('', content)
    content = content.replace('−', '-').replace('–', '—')
    # Normalize all unicode whitespace variants (NNBSP, NBSP, etc.) to regular space
    content = re.sub(r'[  -   　]', ' ', content)
    lines = [L for L in content.split('\n')]

    # Find Reported and Estimate positions where they're followed by numeric data
    rep_idx, est_idx = [], []
    for i, line in enumerate(lines):
        t = line.strip()
        # Look ahead: find next non-empty line
        nxt = ''
        for j in range(i+1, min(i+6, len(lines))):
            if lines[j].strip():
                nxt = lines[j].strip(); break
        is_data = bool(re.match(r'^-?[\d,.]+\s*[MBK]?$', nxt)) or nxt == '—'
        if t == 'Reported' and is_data: rep_idx.append(i)
        if t == 'Estimate' and is_data: est_idx.append(i)

    if len(rep_idx) < 2 or len(est_idx) < 2:
        return None

    def extract(start):
        vals = []
        for i in range(start+1, len(lines)):
            L = lines[i].strip()
            if not L: continue
            # Allow space between number and B/M/K suffix (e.g. "3.81 B")
            if re.match(r'^-?[\d,.]+\s*[MBK]?$', L) or L == '—':
                vals.append(L)
            else:
                break
        return vals

    eps_rep_raw = extract(rep_idx[0])
    eps_est_raw = extract(est_idx[0])
    rev_rep_raw = extract(rep_idx[1])
    rev_est_raw = extract(est_idx[1])

    eps_rep = [parse_num(v) for v in eps_rep_raw]
    eps_est = [parse_num(v) for v in eps_est_raw]
    rev_rep = [parse_rev(v) for v in rev_rep_raw]
    rev_est = [parse_rev(v) for v in rev_est_raw]

    # latest reported (last non-None in eps_rep)
    latest = -1
    for k in range(len(eps_rep)-1, -1, -1):
        if eps_rep[k] is not None:
            latest = k; break
    if latest < 0: return None

    # YoY block
    prior_eps = eps_rep[latest-4] if latest >= 4 else None
    prior_rev = rev_rep[latest-4] if latest >= 4 else None
    cur_eps_y = yoy(eps_rep[latest], prior_eps)
    cur_rev_y = yoy(rev_rep[latest], prior_rev)
    block = [f'{cur_eps_y} / {cur_rev_y}', '-'*20]
    for fwd in range(1, 5):
        fi = latest + fwd
        if fi < len(eps_est) and eps_est[fi] is not None:
            pe = eps_rep[fi-4] if fi >= 4 and (fi-4) < len(eps_rep) else None
            pr = rev_rep[fi-4] if fi >= 4 and (fi-4) < len(rev_rep) else None
            fE = yoy(eps_est[fi], pe)
            re_val = rev_est[fi] if fi < len(rev_est) else None
            fR = yoy(re_val, pr)
            block.append(f'{fE} / {fR}')

    # Raw figures section
    raw = {
        'Reported': {
            'EPS': fmt_eps(eps_rep[latest]),
            'Revenue': fmt_rev(rev_rep[latest]),
        },
        'PriorYearReported': {
            'EPS': fmt_eps(prior_eps),
            'Revenue': fmt_rev(prior_rev),
        },
        'Next4Estimates_EPS': [fmt_eps(eps_est[latest+i]) if (latest+i) < len(eps_est) else '—' for i in range(1, 5)],
        'Next4Estimates_Rev': [fmt_rev(rev_est[latest+i]) if (latest+i) < len(rev_est) else '—' for i in range(1, 5)],
    }

    # Extract Surprise row values (parallel to Reported row).
    # The TV markdown has TWO Surprise blocks (one for EPS, one for Revenue).
    def find_surprise_blocks():
        """Return (eps_surprise_list, rev_surprise_list) of raw strings."""
        surprise_idxs = []
        for i, line in enumerate(lines):
            if line.strip() == 'Surprise':
                # Confirm next non-empty is a % value
                for j in range(i+1, min(i+5, len(lines))):
                    s = lines[j].strip()
                    if s:
                        if re.match(r'^[+\-]\d+\.\d+%$', s) or s == '—':
                            surprise_idxs.append(i)
                        break
        # Extract values from each
        def extract_surp(start):
            vals = []
            for i in range(start+1, len(lines)):
                L = lines[i].strip()
                if not L: continue
                if re.match(r'^[+\-]?\d+\.\d+%$', L) or L == '—':
                    vals.append(L)
                else:
                    break
            return vals
        if len(surprise_idxs) >= 2:
            return extract_surp(surprise_idxs[0]), extract_surp(surprise_idxs[1])
        elif len(surprise_idxs) == 1:
            return extract_surp(surprise_idxs[0]), []
        return [], []

    eps_surp, rev_surp = find_surprise_blocks()
    def parse_pct(s):
        if not s or s == '—': return None
        try: return float(s.replace('%','').replace('+',''))
        except: return None

    # Latest quarter's surprise = value at same index as latest reported
    latest_eps_surprise = parse_pct(eps_surp[latest]) if latest < len(eps_surp) else None
    latest_rev_surprise = parse_pct(rev_surp[latest]) if latest < len(rev_surp) else None

    # Consensus = Estimate value at same index as latest reported
    latest_eps_consensus = eps_est[latest] if latest < len(eps_est) else None
    latest_rev_consensus = rev_est[latest] if latest < len(rev_est) else None

    # Try to extract quarter labels for the detail page chart
    # Quarters appear like "Q1 '24" — we want the last N quarters that align with the data
    # The Reported row has ~12 values (8 reported + 4 dashes). We want the N quarter labels
    # that come right before the second "Reported" marker (which is EPS data).
    quarter_re = re.compile(r"Q[1-4]\s+'\d{2}")
    # Find quarter labels just before rep_idx[0] (first data block — EPS)
    quarters = []
    look_start = max(0, rep_idx[0] - 60)
    for i in range(look_start, rep_idx[0]):
        m = quarter_re.search(lines[i] or '')
        if m:
            q = m.group(0)
            if q not in quarters:
                quarters.append(q)
    # We want the last N matching the data length
    n_quarters = max(len(eps_rep), len(eps_est))
    quarters = quarters[-n_quarters:] if len(quarters) >= n_quarters else quarters

    latest_report_date = parse_latest_report_date(content)
    ticker = os.path.basename(path).replace('-earnings-fq.md', '')
    return {
        'Ticker': ticker,
        'LatestEPS': eps_rep[latest],
        'LatestEPSConsensus': latest_eps_consensus,
        'LatestEPSSurprise_pct': latest_eps_surprise,
        'PriorYrEPS': prior_eps,
        'LatestRev_M': rev_rep[latest],
        'LatestRevConsensus_M': latest_rev_consensus,
        'LatestRevSurprise_pct': latest_rev_surprise,
        'PriorYrRev_M': prior_rev,
        'EpsEst_Next4': [eps_est[latest+i] if (latest+i) < len(eps_est) else None for i in range(1,5)],
        'RevEst_Next4': [rev_est[latest+i] if (latest+i) < len(rev_est) else None for i in range(1,5)],
        'YoYBlock': '\n'.join(block),
        'Raw': raw,
        'LatestReportDate': latest_report_date,   # ISO YYYY-MM-DD, parsed from TV's "Latest report date" line
        # Full arrays for the detail-page chart
        'Chart': {
            'quarters': quarters,
            'eps_reported': eps_rep,
            'eps_estimate': eps_est,
            'rev_reported_M': rev_rep,
            'rev_estimate_M': rev_est,
            'latest_idx': latest,
        },
    }

results = []
for fn in sorted(os.listdir(DIR)):
    if not fn.endswith('-earnings-fq.md'): continue
    if fn.startswith('amd'): continue
    path = os.path.join(DIR, fn)
    if os.path.getsize(path) < 1000: continue
    r = parse_file(path)
    if r:
        results.append(r)
    else:
        print(f'FAIL: {fn}')

print(f'Parsed {len(results)} tickers')

# Save JSON
with open(os.path.join(DIR, 'tv-summary.json'), 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

# Print compact table
print(f'\n{"Ticker":<6} {"LatestEPS":>10} {"PYrEPS":>10} {"LatestRev":>12} {"PYrRev":>12}  YoY (cur/Q1/Q2/Q3/Q4)')
print('-' * 110)
for r in results:
    yb = r['YoYBlock'].split('\n')
    yoy_line = ' | '.join([yb[0]] + (yb[2:] if len(yb) > 2 else []))
    le = f'{r["LatestEPS"]:.2f}' if r['LatestEPS'] is not None else '—'
    pe = f'{r["PriorYrEPS"]:.2f}' if r['PriorYrEPS'] is not None else '—'
    lr = fmt_rev(r['LatestRev_M'])
    pr = fmt_rev(r['PriorYrRev_M'])
    print(f'{r["Ticker"]:<6} {le:>10} {pe:>10} {lr:>12} {pr:>12}  {yoy_line}')
