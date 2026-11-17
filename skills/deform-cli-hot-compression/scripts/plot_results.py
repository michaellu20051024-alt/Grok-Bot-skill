# -*- coding: utf-8 -*-
"""画载荷-行程曲线和终态等效应变/温度场，并写场统计。需要 Python 3 + numpy + matplotlib。

  python plot_results.py --curve load_stroke_curve.csv --fields final_fields_sNN.txt \
      --wp-obj 2 --label "φ10×15 mm 某材料 1000 °C 0.1 s⁻¹ 压下 50%" --outdir figs

--fields 是 DEF_PST 对工件提取的文本（含 RZ / ELMCON / STRAIN / NDTMP 段）。
图由提取的文本场绘制，不是 DEFORM 原生色带截图，交付时要说明。
"""
import argparse, os, re
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection

plt.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "WenQuanYi Zen Hei", "Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def parse_section(text, name, obj):
    pat = re.compile(r"(?m)^\s*\*?" + re.escape(name) + r"\s+" + str(obj) + r"\s+(\d+)\s*$")
    m = pat.search(text)
    if not m:
        raise RuntimeError("section %s obj %s not found" % (name, obj))
    rest = text[m.end():]
    nxt = re.search(r"(?m)^\s*\*?[A-Za-z*]", rest)
    block = rest[:nxt.start()] if nxt else rest
    rows = []
    for line in block.splitlines():
        parts = line.split()
        if parts:
            try:
                rows.append([float(x.replace("D", "E")) for x in parts])
            except ValueError:
                pass
    return int(m.group(1)), rows


def save(fig, outdir, names, **kw):
    for n in names:
        fig.savefig(os.path.join(outdir, n), dpi=150, **kw)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--curve", required=True)
    ap.add_argument("--fields", required=True)
    ap.add_argument("--wp-obj", type=int, default=2)
    ap.add_argument("--label", default="轴对称热压缩")
    ap.add_argument("--step-label", default="终态")
    ap.add_argument("--outdir", default=".")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    c = np.genfromtxt(a.curve, delimiter=",", names=True)
    x, y = np.atleast_1d(c["compression_stroke_mm"]), np.atleast_1d(c["compression_load_N"])
    fig, ax = plt.subplots(figsize=(7.2, 5.0), dpi=150)
    ax.plot(x, y, "o-", color="#1f4e79", ms=4.5, lw=1.6, label="上模载荷（OBJECT_DATA Fy）")
    ax.set_xlabel("压缩行程 / mm"); ax.set_ylabel("压缩载荷 / N（整周回转）"); ax.set_title(a.label, fontsize=11)
    ax.grid(True, alpha=0.3); ax.set_xlim(0, x.max() * 1.07); ax.legend(loc="upper left", fontsize=9)
    ax.annotate("终点: %.2f mm, %.0f N" % (x[-1], y[-1]), xy=(x[-1], y[-1]), xytext=(0.55, 0.75),
                textcoords="axes fraction", arrowprops=dict(arrowstyle="->", color="0.3"), fontsize=9)
    fig.tight_layout(); save(fig, a.outdir, ["载荷行程曲线.png", "load_stroke.png"]); plt.close(fig)

    text = open(a.fields, encoding="latin-1").read()
    o = a.wp_obj
    _, rz = parse_section(text, "RZ", o)
    r = np.array([v[1] for v in rz]); z = np.array([v[2] for v in rz])
    nid = {int(v[0]): i for i, v in enumerate(rz)}
    _, els = parse_section(text, "ELMCON", o)
    quads = [[nid[int(k)] for k in v[1:5]] for v in els]
    _, st = parse_section(text, "STRAIN", o)
    strain = {int(v[0]): v[1] for v in st}
    strain_e = np.array([strain.get(int(v[0]), np.nan) for v in els])
    _, tm = parse_section(text, "NDTMP", o)
    temp = np.full(len(rz), np.nan)
    for v in tm:
        temp[nid[int(v[0])]] = v[1]

    def panel(fig, ax, values, title, cmap, cb_label, elemental):
        if elemental:
            coll = PolyCollection([np.column_stack([r[q], z[q]]) for q in quads], array=values, cmap=cmap, edgecolors="none")
            ax.add_collection(coll); h = coll
        else:
            tris = np.array([t for q in quads for t in ([q[0], q[1], q[2]], [q[0], q[2], q[3]])])
            h = ax.tripcolor(r, z, tris, values, cmap=cmap, shading="gouraud")
        fig.colorbar(h, ax=ax, fraction=0.046, pad=0.04).set_label(cb_label)
        ax.set_aspect("equal"); ax.set_xlabel("r / mm"); ax.set_ylabel("z / mm"); ax.set_title(title, fontsize=11)
        ax.set_xlim(0, r.max() * 1.1); ax.set_ylim(z.min() - 0.3, z.max() * 1.07); ax.axvline(0, color="0.5", lw=0.6, ls="--")

    fig, axes = plt.subplots(1, 2, figsize=(11.2, 5.6), dpi=150)
    panel(fig, axes[0], strain_e, "%s等效应变（工件）" % a.step_label, "viridis", "等效应变", True)
    panel(fig, axes[1], temp, "%s温度 / °C（工件）" % a.step_label, "inferno", "温度 / °C", False)
    fig.suptitle(a.label, fontsize=12, y=1.02); fig.tight_layout()
    save(fig, a.outdir, ["终态应变与温度分布.png", "strain_temperature.png"], bbox_inches="tight"); plt.close(fig)
    for vals, t, cm, lab, el, names in ((strain_e, "等效应变", "viridis", "等效应变", True, ["终态等效应变分布.png", "effective_strain.png"]),
                                       (temp, "温度 / °C", "inferno", "温度 / °C", False, ["终态温度分布.png", "temperature.png"])):
        fig, ax = plt.subplots(figsize=(5.2, 6.0), dpi=150)
        panel(fig, ax, vals, a.step_label + t, cm, lab, el); fig.tight_layout(); save(fig, a.outdir, names); plt.close(fig)

    mid = np.abs(z - 0.5 * (z.max() + z.min())) < 0.4
    s = ["nodes=%d elements=%d" % (len(rz), len(quads)),
         "R_min=%.6f R_max=%.6f mm" % (r.min(), r.max()),
         "Z_min=%.6f Z_max=%.6f height=%.6f mm" % (z.min(), z.max(), z.max() - z.min()),
         "strain_min=%.6f strain_max=%.6f strain_mean=%.6f" % (np.nanmin(strain_e), np.nanmax(strain_e), np.nanmean(strain_e)),
         "temp_min=%.4f temp_max=%.4f temp_mean=%.4f C" % (np.nanmin(temp), np.nanmax(temp), np.nanmean(temp)),
         "R_max_near_midheight=%.6f mm (nodes with |z-zmid|<0.4)" % (r[mid].max() if mid.any() else float("nan"))]
    with open(os.path.join(a.outdir, "final_field_stats.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(s) + "\n")
    print("\n".join(s))


if __name__ == "__main__":
    main()
