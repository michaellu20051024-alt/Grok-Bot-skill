#!/usr/bin/env python3
"""DSC 外推起始温度（两切线相交法）+ 首次偏离基线温度 + 敏感性分析。

外推起始 T_e = 峰前外推基线 ∩ 峰前沿最大斜率点（拐点）切线。
吸热峰需朝上；若仪器导出为吸热向下（如 EXO=+1），加 --flip。

例：
  python tangent_onset.py data.csv --temp-col "Temp" --signal-col "DSC" \
      --baseline 1338 1388 --outdir out --title "某样品 DSC"
"""
import argparse, csv, json, os, sys
import numpy as np


def read_table(path, temp_col, signal_col, sheet=None):
    """读 CSV/TXT/XLSX。列名可写名称片段（不分大小写）或 0 起的列号。
    CSV 中以单个 '#' 开头的行视为注释；以 '##' 开头的行视为表头（NETZSCH 导出格式）。"""
    ext = os.path.splitext(path)[1].lower()
    if ext in ('.xlsx', '.xls'):
        import pandas as pd
        df = pd.read_excel(path, sheet_name=sheet or 0)
        header = [str(c) for c in df.columns]
        data = df.apply(lambda s: s.astype(str)).values.tolist()
    else:
        header, data = None, []
        with open(path, encoding='utf-8', errors='ignore') as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                if s.startswith('##'):
                    header = [c.strip() for c in s[2:].split(',')]
                    continue
                if s.startswith('#'):
                    continue
                parts = [c.strip() for c in s.replace('\t', ',').replace(';', ',').split(',')]
                if header is None and not _isnum(parts[0]):
                    header = parts
                    continue
                data.append(parts)

    def col_index(c):
        if c is None:
            return None
        if str(c).lstrip('-').isdigit():
            return int(c)
        if header is None:
            sys.exit(f'文件没有表头，列 "{c}" 只能用列号指定')
        hits = [i for i, h in enumerate(header) if str(c).lower() in h.lower()]
        if len(hits) != 1:
            sys.exit(f'列 "{c}" 匹配到 {len(hits)} 列：{[header[i] for i in hits] or header}')
        return hits[0]

    it, iq = col_index(temp_col), col_index(signal_col)
    T, q = [], []
    for r in data:
        try:
            T.append(float(r[it])); q.append(float(r[iq]))
        except (ValueError, IndexError):
            pass
    T, q = np.array(T), np.array(q)
    ok = np.isfinite(T) & np.isfinite(q)
    return T[ok], q[ok], (header[it] if header else str(it)), (header[iq] if header else str(iq))


def _isnum(x):
    try:
        float(x); return True
    except ValueError:
        return False


def onset(T, q, bl, edge, win, poly):
    from scipy.signal import savgol_filter
    sb = (T >= bl[0]) & (T <= bl[1])
    if sb.sum() < 5:
        raise ValueError(f'基线区间 {bl} 内点数不足')
    kb, bb = np.polyfit(T[sb], q[sb], 1)
    sw = (T >= edge[0]) & (T <= edge[1])
    if sw.sum() < 3:
        raise ValueError(f'前沿区间 {edge} 内点数不足')
    dT = np.mean(np.diff(T))
    qs = savgol_filter(q, win, poly)
    dq = savgol_filter(q, win, poly, deriv=1, delta=dT)
    i = np.where(sw)[0][np.argmax(dq[sw])]
    Ti, qi, ki = T[i], qs[i], dq[i]
    Te = (qi - ki * Ti - bb) / (kb - ki)
    return dict(bl=bl, win=win, kb=kb, bb=bb, Ti=Ti, qi=qi, ki=ki, Te=Te, qe=kb * Te + bb,
                resid=float(np.std(q[sb] - (kb * T[sb] + bb))), dq=dq)


def parse_ranges(s):
    out = []
    for p in s.split(','):
        a, b = p.split(':'); out.append((float(a), float(b)))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input', help='CSV/TXT/XLSX 数据文件')
    ap.add_argument('--temp-col', required=True, help='温度列名片段或列号（0 起）')
    ap.add_argument('--signal-col', required=True, help='DSC 信号列名片段或列号（0 起）')
    ap.add_argument('--sheet', help='xlsx 工作表名')
    ap.add_argument('--flip', action='store_true', help='信号乘 -1（吸热向下的数据用）')
    ap.add_argument('--baseline', nargs=2, type=float, required=True, metavar=('LO', 'HI'), help='峰前基线拟合区间/℃')
    ap.add_argument('--edge', nargs=2, type=float, metavar=('LO', 'HI'), help='峰前沿搜索区间/℃；默认基线上限→峰顶')
    ap.add_argument('--peak-search', nargs=2, type=float, metavar=('LO', 'HI'), help='峰顶搜索区间；默认基线上限→数据末端')
    ap.add_argument('--sg-window', type=int, default=31, help='Savitzky-Golay 窗口点数（奇数）')
    ap.add_argument('--sg-poly', type=int, default=3)
    ap.add_argument('--raw-halfwidth', type=float, default=1.5, help='原始点核对：拐点 ± 该宽度/℃ 内直线拟合')
    ap.add_argument('--sigma', type=float, default=5.0, help='首次偏离判据：残差 > n·σ')
    ap.add_argument('--consecutive', type=int, default=20, help='首次偏离判据：连续点数')
    ap.add_argument('--sens-baselines', help='敏感性基线区间，如 "1300:1388,1350:1395"；默认围绕主区间自动生成')
    ap.add_argument('--sens-windows', default='11,21,31,51', help='敏感性 SG 窗口，逗号分隔')
    ap.add_argument('--plot-range', nargs=2, type=float, metavar=('LO', 'HI'), help='局部作图/导出区间；默认基线下限-40→数据末端')
    ap.add_argument('--title', default='DSC 切线法外推起始温度作图过程')
    ap.add_argument('--unit', default='mW/mg', help='信号单位（仅用于图注）')
    ap.add_argument('--outdir', default='.')
    ap.add_argument('--no-plot', action='store_true')
    a = ap.parse_args()

    T, q, tname, qname = read_table(a.input, a.temp_col, a.signal_col, a.sheet)
    if a.flip:
        q = -q
    o = np.argsort(T, kind='stable')
    if not np.all(np.diff(T) > 0):
        print('警告：温度非严格单调（可能含降温段或重复点），已按温度排序；请确认只用了升温段', file=sys.stderr)
        T, q = T[o], q[o]
    bl = tuple(a.baseline)
    ps = a.peak_search or (bl[1], T.max())
    m = (T >= ps[0]) & (T <= ps[1])
    T_peak = float(T[m][np.argmax(q[m])])
    edge = tuple(a.edge) if a.edge else (bl[1], T_peak)
    R = onset(T, q, bl, edge, a.sg_window, a.sg_poly)

    # 原始点核对（不平滑）
    sr = (T >= R['Ti'] - a.raw_halfwidth) & (T <= R['Ti'] + a.raw_halfwidth)
    kr, br = np.polyfit(T[sr], q[sr], 1)
    Te_raw = (br - R['bb']) / (R['kb'] - kr)

    # 首次偏离基线：残差连续 consecutive 点 > sigma·σ
    res = q - (R['kb'] * T + R['bb'])
    thr = a.sigma * R['resid']
    idx = np.where((T > bl[1]) & (res > thr))[0]
    first = next((i for i in idx if i + a.consecutive <= len(T) and np.all(res[i:i + a.consecutive] > thr)), None)
    T_first = float(T[first]) if first is not None else None

    # 敏感性
    if a.sens_baselines:
        bls = parse_ranges(a.sens_baselines)
    else:
        w = bl[1] - bl[0]
        bls = [bl, (bl[0] - w, bl[1]), (bl[0] + w * 0.25, bl[1]), (bl[0], bl[1] - w * 0.25)]
    wins = [int(x) for x in a.sens_windows.split(',')]
    sens = []
    for b in bls:
        for wn in wins:
            try:
                r = onset(T, q, b, edge, wn, a.sg_poly)
                sens.append([f'{b[0]:g}–{b[1]:g}', wn, round(r['Ti'], 2), round(r['ki'], 5), round(r['Te'], 2)])
            except ValueError as e:
                print(f'敏感性跳过 {b}/{wn}: {e}', file=sys.stderr)
    Tes = [x[4] for x in sens]

    os.makedirs(a.outdir, exist_ok=True)
    out = dict(input=os.path.basename(a.input), temp_col=tname, signal_col=qname, flipped=a.flip,
               n=int(len(T)), T_range=[float(T.min()), float(T.max())],
               baseline_fit=f'{bl[0]:g}–{bl[1]:g} ℃ 线性', baseline_k=R['kb'], baseline_b=R['bb'],
               baseline_resid_sigma=R['resid'], edge_window=list(edge), SG=f'{a.sg_window} 点 {a.sg_poly} 阶',
               T_inflection=R['Ti'], q_inflection=R['qi'], slope_inflection=R['ki'],
               T_onset_extrap=R['Te'], T_onset_raw_fit=Te_raw, raw_fit_slope=kr,
               first_deviation_rule=f'残差连续 {a.consecutive} 点 > {a.sigma:g}σ',
               T_first_deviation=T_first, T_peak=T_peak,
               sens_min=min(Tes) if Tes else None, sens_max=max(Tes) if Tes else None)
    with open(os.path.join(a.outdir, 'result.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=float)
    with open(os.path.join(a.outdir, 'sensitivity.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['基线拟合区间/℃', 'SG窗口点数', '拐点温度/℃', f'拐点斜率/({a.unit}/℃)', '外推起始/℃'])
        w.writerows(sens)
    pr = a.plot_range or (bl[0] - 40, T.max())
    sp = (T >= pr[0]) & (T <= pr[1])
    with open(os.path.join(a.outdir, 'construction_lines.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f); w.writerow(['T/℃', '实测DSC', '外推基线', '拐点切线'])
        for x, y in zip(T[sp], q[sp]):
            w.writerow([x, y, R['kb'] * x + R['bb'], R['ki'] * (x - R['Ti']) + R['qi']])

    if not a.no_plot:
        plot(T, q, R, bl, edge, pr, T_first, T_peak, a)
    print(json.dumps(out, ensure_ascii=False, default=float, indent=1))


def plot(T, q, R, bl, edge, pr, T_first, T_peak, a):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', 'WenQuanYi Zen Hei', 'SimHei', 'Microsoft YaHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    kb, bb, Ti, qi, ki, Te, dq = R['kb'], R['bb'], R['Ti'], R['qi'], R['ki'], R['Te'], R['dq']
    fig, ax = plt.subplots(2, 2, figsize=(11, 8), dpi=180)
    x0 = ax[0, 0]; x0.plot(T, q, 'k', lw=1); x0.axvspan(*pr, color='0.9')
    x0.set_title('① 全程 DSC 曲线（灰区为分析段）'); x0.set_xlabel('温度 / ℃'); x0.set_ylabel(f'DSC / ({a.unit})，吸热向上')
    x1 = ax[0, 1]; s1 = (T >= pr[0]) & (T <= pr[1]); x1.plot(T[s1], q[s1], 'k', lw=1, label='实测')
    sb = (T >= bl[0]) & (T <= bl[1]); x1.plot(T[sb], q[sb], c='tab:blue', lw=3, alpha=.5, label=f'基线拟合段 {bl[0]:g}–{bl[1]:g} ℃')
    x = np.linspace(*pr, 5); x1.plot(x, kb * x + bb, '--', c='tab:blue', label=f'切线1：外推基线 y={kb:.6f}T{bb:+.4f}')
    x1.set_title('② 第一条线：峰前基线线性拟合并外延'); x1.legend(fontsize=7); x1.set_xlabel('温度 / ℃')
    x2 = ax[1, 0]; s2 = (T >= edge[0] - 10) & (T <= min(T.max(), T_peak + 20)); x2.plot(T[s2], dq[s2], 'k', lw=1); x2.plot(Ti, ki, 'ro')
    x2.annotate(f'前沿最大斜率\nT={Ti:.2f} ℃\nk={ki:.4f}', (Ti, ki), (Ti + 4, ki * 0.8), fontsize=8, arrowprops=dict(arrowstyle='->'))
    x2.axhline(0, c='0.6', lw=.6); x2.set_title(f'③ 求导找前沿拐点（SG {a.sg_window} 点 {a.sg_poly} 阶）'); x2.set_xlabel('温度 / ℃'); x2.set_ylabel('dDSC/dT')
    x3 = ax[1, 1]; lo = min(Te, T_first or Te) - 15; hi = min(T.max(), T_peak + 15); s3 = (T >= lo) & (T <= hi)
    x3.plot(T[s3], q[s3], 'k', lw=1.2, label='实测')
    x = np.linspace(lo, hi, 5); x3.plot(x, kb * x + bb, '--', c='tab:blue', label='切线1：外推基线')
    xx = np.linspace(Te - 3, Ti + 5, 5); x3.plot(xx, ki * (xx - Ti) + qi, '--', c='tab:red', label='切线2：前沿拐点切线')
    x3.plot(Ti, qi, 'ro', ms=4); x3.plot(Te, R['qe'], 'ks', ms=6)
    x3.annotate(f'交点 = 外推起始温度\n{Te:.1f} ℃', (Te, R['qe']), xytext=(0.05, 0.55), textcoords='axes fraction', fontsize=9, arrowprops=dict(arrowstyle='->'))
    if T_first is not None:
        x3.axvline(T_first, c='tab:green', ls=':', lw=.8)
        x3.text(T_first, 0.02, f'首次偏离基线 {T_first:.1f} ℃', rotation=90, fontsize=7, color='tab:green', va='bottom', ha='right', transform=x3.get_xaxis_transform())
    yv = q[s3]; x3.set_ylim(yv.min() - 0.1 * np.ptp(yv), yv.max() + 0.1 * np.ptp(yv))
    x3.set_title('④ 两切线相交'); x3.legend(fontsize=7, loc='upper right'); x3.set_xlabel('温度 / ℃')
    fig.suptitle(a.title, fontsize=11); fig.tight_layout()
    for ext in ('png', 'pdf'):
        fig.savefig(os.path.join(a.outdir, f'切线法作图过程.{ext}'))


if __name__ == '__main__':
    main()
