"""Phase 2 validation: the algorithm stack, each item measured on the same
untouched test window as the baseline. Keep-or-kill rule - only items that
improve gated OOS win rate (or the theta -> frequency curve) are kept.

Items measured:
  B  baseline              XGB raw probabilities (Phase 1 feature set)
  1  hour-conditional       separate XGB for window (15-17 UTC) vs off-window
  2  multi-horizon          joint k=1,2,3 candle-horizon probability blend
  3  news features          high-impact event proximity features + veto value
  4  ensemble stack         soft-vote of XGB/LGBM/RF/CatBoost + logit stacker

Metric per theta: trades n, win%, CI, EV@90, signals/hour. Window 15-17 UTC
readout at theta 0.55 is printed for every item.

Run:  python phase2_validation.py
"""

import glob
import os
import sys
import warnings

warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier

CURR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CURR)

from phase1_validation import _raw_frame, build_dataset_v2, split_walk, wilson_ci, XGB_DEFAULTS

OUT = os.path.join(CURR, 'common', 'MachineLearningModel', 'output')

WINDOW_LO, WINDOW_HI = 15, 17
THETAS = [0.50, 0.55, 0.60, 0.65, 0.70]

HIGH_IMPACT_EVENTS = [
    ('2024-05-15', 12, 30), ('2024-05-22', 18, 0),
    ('2024-06-06', 12, 15), ('2024-06-07', 12, 30),
    ('2024-06-12', 12, 30), ('2024-06-12', 18, 0),
    ('2024-06-14', 3, 0),   ('2024-06-20', 11, 0),
    ('2024-07-05', 12, 30), ('2024-07-11', 12, 30),
    ('2024-07-17', 12, 30), ('2024-07-31', 18, 0),
]


def event_times():
    return pd.to_datetime([f'{d} {h:02d}:{m:02d}:00' for d, h, m in HIGH_IMPACT_EVENTS])


def news_features(meta):
    ev = event_times().values
    t = pd.to_datetime(meta['datetime']).values
    f = pd.DataFrame(index=meta.index)
    hours = np.full(len(meta), 999.0)
    in_ev = np.zeros(len(meta))
    for e in ev:
        delta_h = (e - t) / np.timedelta64(1, 'h')
        nearer = np.abs(delta_h) < np.abs(hours)
        hours = np.where(nearer, delta_h, hours)
        in_ev = np.where((delta_h >= -1) & (delta_h <= 1), 1.0, in_ev)
    f['hours_to_event'] = hours
    f['in_event_window'] = in_ev
    return f


def load():
    files = [f for f in glob.glob(os.path.join(OUT, 'five_mins', '*_5_Min*.csv'))]
    meta, feats = build_dataset_v2(files, 900, 300)
    full = meta.join(feats)
    full = full.dropna(subset=[c for c in feats.columns] + ['atr', 'fwd', 'entry', 'exit'])
    meta = full[['datetime', 'symbol', 'atr', 'entry', 'exit', 'fwd', 'label']]
    feats = full[feats.columns]
    raw = _raw_frame(files)
    return meta, feats, raw


def horizon_labels(meta, raw, k):
    """Certainty labels for horizon k: entry open_{i+1}, exit close_{i+k}."""
    close_shift = raw.groupby('symbol')['close'].shift(-k)
    exit_k = close_shift.reindex(meta.index)
    fwd_k = exit_k - meta['entry']
    atr = meta['atr']
    strong = fwd_k.abs() >= 0.5 * atr
    lab = pd.Series(0, index=meta.index, dtype=float)
    lab[strong & (fwd_k > 0)] = 1
    lab[strong & (fwd_k < 0)] = 2
    return lab


def predict_and_score(model, X):
    P = model.predict_proba(X)
    p_call, p_put = P[:, 1], P[:, 2]
    return np.maximum(p_call, p_put), np.where(p_call >= p_put, 1, 2)


def score_table(best, pred, meta, wins, tag):
    hour = pd.to_datetime(meta['datetime']).dt.hour.values
    days = meta['datetime'].dt.date.nunique()
    print(f'  -- {tag} --')
    print(f'  {"theta":>6} {"n":>7} {"win%":>7} {"CIlo":>6} {"CIhi":>6} {"EV@90":>7} {"per hour":>9}')
    for th in THETAS:
        m = best >= th
        n = int(m.sum())
        if n == 0:
            print(f'  {th:>6.2f} {0:>7} {"-":>7}')
            continue
        w = wins[m].mean()
        lo, hi = wilson_ci(n, w)
        ev = w * 1.88 - 1.0   # P*(payout-slippage) - (1-P), payout 0.90, slippage 0.02
        print(f'  {th:>6.2f} {n:>7} {w*100:>6.1f}% {lo*100:>6.1f} {hi*100:>6.1f} {ev:>+7.3f} {n/(days*8):>8.2f}')
    m = (best >= 0.55) & (hour >= WINDOW_LO) & (hour < WINDOW_HI)
    n = int(m.sum())
    if n:
        w = wins[m].mean()
        print(f'  WINDOW 15-17 UTC @0.55: n={n} win={w*100:.1f}% signals/hour={n/(days*2):.2f}')


def main():
    meta, feats, raw = load()
    print(f'rows={len(meta):,}  features={len(feats.columns)}  span={meta.datetime.min()} -> {meta.datetime.max()}')

    X_tr, y_tr, X_va, y_va, X_te, y_te, m_te = split_walk(feats, meta)
    actual = np.where(m_te['fwd'].values > 0, 1, np.where(m_te['fwd'].values < 0, 2, 0))
    actual_va = np.where(meta.loc[X_va.index, 'fwd'].values > 0, 1,
                         np.where(meta.loc[X_va.index, 'fwd'].values < 0, 2, 0))

    def wins_for(pred):
        return (pred == actual) & (actual != 0)

    # ---------------- B baseline ----------------
    print('\n' + '=' * 84)
    print('B  BASELINE (XGB, Phase-1 features)')
    base = XGBClassifier(**XGB_DEFAULTS)
    base.fit(X_tr, y_tr)
    best_b, pred_b = predict_and_score(base, X_te)
    wins_b = wins_for(pred_b)
    score_table(best_b, pred_b, m_te, wins_b, 'baseline')

    # ---------------- 1 hour-conditional ----------------
    print('\n' + '=' * 84)
    print('1  HOUR-CONDITIONAL (separate models for 15-17 UTC vs off-window)')
    tr_hour = pd.to_datetime(meta.loc[X_tr.index, 'datetime']).dt.hour.values
    win_tr = (tr_hour >= WINDOW_LO) & (tr_hour < WINDOW_HI)
    te_hour = pd.to_datetime(m_te['datetime']).dt.hour.values
    win_te = (te_hour >= WINDOW_LO) & (te_hour < WINDOW_HI)
    if win_tr.sum() > 500 and (~win_tr).sum() > 500:
        mw = XGBClassifier(**XGB_DEFAULTS)
        mw.fit(X_tr[win_tr], y_tr[win_tr])
        mo = XGBClassifier(**XGB_DEFAULTS)
        mo.fit(X_tr[~win_tr], y_tr[~win_tr])
        best1 = np.empty(len(X_te))
        pred1 = np.empty(len(X_te))
        b_w, p_w = predict_and_score(mw, X_te[win_te])
        b_o, p_o = predict_and_score(mo, X_te[~win_te])
        best1[win_te] = b_w
        pred1[win_te] = p_w
        best1[~win_te] = b_o
        pred1[~win_te] = p_o
        score_table(best1, pred1, m_te, wins_for(pred1), 'hour-conditional')
    else:
        print('  skipped: insufficient window rows in train')

    # ---------------- 2 multi-horizon ----------------
    print('\n' + '=' * 84)
    print('2  MULTI-HORIZON (blend k=1,2,3 horizon probabilities)')
    models_h = {}
    for k in [1, 2]:
        lab = horizon_labels(meta, raw, k)
        valid = lab.loc[X_tr.index].notna()
        mk = XGBClassifier(**XGB_DEFAULTS)
        mk.fit(X_tr[valid], lab.loc[X_tr.index][valid])
        models_h[k] = mk
    pc = np.zeros(len(X_te))
    pp = np.zeros(len(X_te))
    for k, mk in models_h.items():
        P = mk.predict_proba(X_te)
        pc += P[:, 1]
        pp += P[:, 2]
    base_P = base.predict_proba(X_te)
    pc = (pc + base_P[:, 1]) / 3.0
    pp = (pp + base_P[:, 2]) / 3.0
    best2 = np.maximum(pc, pp)
    pred2 = np.where(pc >= pp, 1, 2)
    score_table(best2, pred2, m_te, wins_for(pred2), 'multi-horizon blend (k1,k2,k3)')

    # ---------------- 3 news features ----------------
    print('\n' + '=' * 84)
    print('3  NEWS FEATURES (high-impact proximity) + veto value')
    nf = news_features(meta)
    feats_n = feats.join(nf[['hours_to_event', 'in_event_window']]).replace([np.inf, -np.inf], np.nan)
    X_tr_n = feats_n.loc[X_tr.index].fillna(0.0)
    X_te_n = feats_n.loc[X_te.index].fillna(0.0)
    mn = XGBClassifier(**XGB_DEFAULTS)
    mn.fit(X_tr_n, y_tr)
    best3, pred3 = predict_and_score(mn, X_te_n)
    score_table(best3, pred3, m_te, wins_for(pred3), 'xgb + news features')

    in_ev = nf.loc[X_te.index, 'in_event_window'].values == 1.0
    m = best_b >= 0.55
    if in_ev[m].sum() >= 20:
        w_ev = wins_b[m][in_ev[m]].mean()
        w_no = wins_b[m][~in_ev[m]].mean()
        print(f'  VETO VALUE @0.55: near-events n={int(in_ev[m].sum())} win={w_ev*100:.1f}%  '
              f'vs away-from-events win={w_no*100:.1f}%  (n={int((~in_ev)[m].sum())})')

    # ---------------- 4 ensemble stack ----------------
    print('\n' + '=' * 84)
    print('4  ENSEMBLE STACK (XGB + LGBM + RF + CatBoost)')
    from lightgbm import LGBMClassifier
    from catboost import CatBoostClassifier
    models = [
        ('xgb', base),
        ('lgbm', LGBMClassifier(n_estimators=300, max_depth=6, learning_rate=0.05,
                                subsample=0.8, colsample_bytree=0.8, verbose=-1)),
        ('rf', RandomForestClassifier(n_estimators=200, max_depth=8, n_jobs=-1)),
        ('cat', CatBoostClassifier(iterations=300, depth=6, learning_rate=0.05,
                                   verbose=0, allow_writing_files=False)),
    ]
    for name, mk in models[1:]:
        mk.fit(X_tr, y_tr)

    soft_pc = np.zeros(len(X_te))
    soft_pp = np.zeros(len(X_te))
    for _, mk in models:
        P = mk.predict_proba(X_te)
        soft_pc += P[:, 1]
        soft_pp += P[:, 2]
    soft_pc /= len(models)
    soft_pp /= len(models)
    best4 = np.maximum(soft_pc, soft_pp)
    pred4 = np.where(soft_pc >= soft_pp, 1, 2)
    score_table(best4, pred4, m_te, wins_for(pred4), 'soft-vote stack')

    # logit stacker: predicts 'is the XGB direction correct' from model probs
    stack_va = np.column_stack([mk.predict_proba(X_va)[:, 1] for _, mk in models])
    stack_te = np.column_stack([mk.predict_proba(X_te)[:, 1] for _, mk in models])
    dirs_va = np.where(base.predict(X_va) == 2, 2, np.where(base.predict(X_va) == 1, 1, 0))
    y_stack = ((dirs_va == actual_va) & (actual_va != 0)).astype(int)
    logit = LogisticRegression()
    logit.fit(stack_va, y_stack)
    p_stack = logit.predict_proba(stack_te)[:, 1]
    m5 = p_stack >= 0.55
    if m5.sum():
        print(f'  LOGIT STACKER (P>=0.55 on baseline gate): n={int(m5.sum())} '
              f'win={wins_b[m5].mean()*100:.1f}%  (baseline @0.55 reference above)')
    else:
        print('  LOGIT STACKER: no trades at P>=0.55')

    # ---------------- 5 news features + stack combined ----------------
    print('\n' + '=' * 84)
    print('5  NEWS FEATURES + SOFT-VOTE STACK (best candidates combined)')
    mn5 = XGBClassifier(**XGB_DEFAULTS)
    mn5.fit(X_tr_n, y_tr)
    lgb_n = LGBMClassifier(n_estimators=300, max_depth=6, learning_rate=0.05,
                           subsample=0.8, colsample_bytree=0.8, verbose=-1)
    rf_n = RandomForestClassifier(n_estimators=200, max_depth=8, n_jobs=-1)
    cat_n = CatBoostClassifier(iterations=300, depth=6, learning_rate=0.05,
                               verbose=0, allow_writing_files=False)
    for mk in [lgb_n, rf_n, cat_n]:
        mk.fit(X_tr_n, y_tr)
    combo_pc = np.zeros(len(X_te))
    combo_pp = np.zeros(len(X_te))
    for mk in [mn5, lgb_n, rf_n, cat_n]:
        P = mk.predict_proba(X_te_n)
        combo_pc += P[:, 1]
        combo_pp += P[:, 2]
    combo_pc /= 4.0
    combo_pp /= 4.0
    best5 = np.maximum(combo_pc, combo_pp)
    pred5 = np.where(combo_pc >= combo_pp, 1, 2)
    score_table(best5, pred5, m_te, wins_for(pred5), 'news + soft-vote stack')

    print('\n' + '=' * 84)
    print('DONE - compare each item against B at the same theta.')


if __name__ == '__main__':
    main()
