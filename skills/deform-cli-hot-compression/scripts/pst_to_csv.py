# -*- coding: utf-8 -*-
"""把 DEF_PST「Data Extraction → Object Information → OBJECT CHARACTERISTICS」逐步导出的文本，
整理成载荷-行程 CSV。兼容 Python 2.7 / 3.x。

每个导出文件对应一个存储步，用 STEP=路径 传入：
  python pst_to_csv.py --die-top 1 --die-bottom 3 --out load_stroke_curve.csv 1=s1.txt 2=s2.txt ...
可选 --time STEP=秒（时间取自求解日志/PST，不要自己按行程推算后冒充实测）。

读取每个对象的 `STROKE obj  sx  sy` 与 `* OBJECT_DATA obj  Vx  Vy  Fx  Fy`。
注意：PST「Load-Stroke-Time」专用导出在 v11 2D 试验里行程和力全为 0，不能用。
"""
from __future__ import print_function
import argparse, csv, io, re, sys

NUM = r"([-+]?\d*\.?\d+(?:[EeDd][-+]?\d+)?)"


def f(x):
    return float(x.replace("D", "E").replace("d", "e"))


def parse(path):
    t = io.open(path, "r", encoding="latin-1").read()
    stroke, od = {}, {}
    for m in re.finditer(r"(?m)^\s*STROKE\s+(\d+)\s+" + NUM + r"\s+" + NUM, t):
        stroke[int(m.group(1))] = (f(m.group(2)), f(m.group(3)))
    for m in re.finditer(r"(?m)^\s*\*\s*OBJECT_DATA\s+(\d+)\s+" + NUM + r"\s+" + NUM + r"\s+" + NUM + r"\s+" + NUM, t):
        od[int(m.group(1))] = tuple(f(m.group(i)) for i in range(2, 6))
    return stroke, od


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dumps", nargs="+", metavar="STEP=PATH")
    ap.add_argument("--die-top", type=int, default=1)
    ap.add_argument("--die-bottom", type=int, default=3)
    ap.add_argument("--time", action="append", default=[], metavar="STEP=SEC")
    ap.add_argument("--out", default="load_stroke_curve.csv")
    a = ap.parse_args()
    times = dict((int(k), v) for k, v in (s.split("=", 1) for s in a.time))
    rows = []
    for item in a.dumps:
        k, p = item.split("=", 1)
        st, od = parse(p)
        if a.die_top not in st or a.die_top not in od:
            sys.exit("%s 里没有对象 %d 的 STROKE/OBJECT_DATA" % (p, a.die_top))
        sy = st[a.die_top][1]
        vx, vy, fx, fy = od[a.die_top]
        fyb = od.get(a.die_bottom, (None,) * 4)[3]
        rows.append([int(k), times.get(int(k), ""), sy, abs(sy), vy, fx, fy, abs(fy), "" if fyb is None else fyb])
        if fyb is not None and abs(fy) > 0 and abs(abs(fy) - abs(fyb)) / abs(fy) > 0.01:
            print("警告：步 %s 上下模 Fy 不平衡：%g vs %g" % (k, fy, fyb), file=sys.stderr)
    rows.sort(key=lambda r: r[0])
    with open(a.out, "w") as fo:
        w = csv.writer(fo, lineterminator="\n")
        w.writerow(["step", "time_s", "signed_stroke_mm", "compression_stroke_mm", "die_velocity_mm_s",
                    "Fx_top_N", "Fy_top_N", "compression_load_N", "Fy_bottom_N"])
        w.writerows(rows)
    print("wrote", a.out, len(rows), "rows")


if __name__ == "__main__":
    main()
