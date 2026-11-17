# -*- coding: utf-8 -*-
"""生成 DEFORM-2D v11 轴对称圆柱热压缩 KEY 文件 + DEF_PRE 动作文件。

单位：SI（UNIT 1）—— mm、N、MPa、s、°C。几何：圆柱半截面（r=0 为对称轴）。
工件：粘塑性，结构化四边形网格；上下模：刚体平砧（上模恒速下行，下模静止）。
材料：从 DEFORM 安装目录材料库里的 SI 单位 KEY 文件读入（--material-key），
材料号自动改为 1；模具（材料 2）只给常值热物性（参数 die_thrcnd / die_heatcp）。

兼容 Python 2.7 与 3.x（DEFORM 机器上可能只有 2.7）。

用法：
  python build_key.py --params params.json --material-key "<库文件路径>" --outdir <工程目录>
  python build_key.py --params params.json --set temp=1100 --set rate=1.0 ...
"""
from __future__ import print_function
import argparse, io, json, os, re, sys

DEFAULTS = {
    "name": "HOTCOMP_2D",
    "material_label": "MATERIAL",   # 只用于标题/说明
    "R": 5.0, "H": 15.0,            # mm 工件半径、高度
    "die_R": 12.0, "die_T": 2.0,    # mm 平砧外半径、厚度
    "temp": 1000.0,                 # °C 工件初温
    "die_temp": None,               # °C 模具温度，缺省 = temp
    "rate": 0.1,                    # 1/s 目标初始应变速率；上模速度 v = rate*H
    "reduction": 0.5,               # 压下率（行程 = reduction*H）
    "demax": 0.02,                  # 每步最大等效应变增量；DTMAX = demax/rate
    "nstep": 80, "stpinc": 1,
    "fric": 0.3,                    # 常剪切摩擦因子 m
    "ihtc": 0.4,                    # N/s/mm/°C 界面换热
    "envtmp": 20.0, "cnvcof": 0.02, # 环境温度、对流系数
    "nr": 12, "nz": 36,             # 工件网格
    "dnr": 8, "dnz": 2,             # 每个模具网格
    "remesh": True, "rmstrk": 1.5, "rmstep": 15, "mgsizr": 0.6, "mgnelm": 800, "mgtelm": 4,
    "die_thrcnd": 32.896,           # 模具常值导热（应取模具温度下的值）
    "die_heatcp": 4.30,             # 模具常值热容
    "die_mat_name": "RigidDie_thermal",
}


def sci(x):
    return "%21.10E" % float(x)


def kw(name, *vals):
    parts = ["%-8s" % name]
    for v in vals:
        if isinstance(v, bool):
            v = int(v)
        if isinstance(v, int):
            parts.append("%8d" % v)
        elif isinstance(v, float):
            parts.append(sci(v))
        else:
            parts.append(str(v))
    return "".join(parts).rstrip()


def structured_rect(r0, r1, z0, z1, nr, nz):
    nodes = []
    for j in range(nz + 1):
        z = z0 + (z1 - z0) * j / float(nz)
        for i in range(nr + 1):
            nodes.append((r0 + (r1 - r0) * i / float(nr), z))
    els = []
    for j in range(nz):
        for i in range(nr):
            n00 = j * (nr + 1) + i + 1
            n01 = (j + 1) * (nr + 1) + i + 1
            els.append((n00, n00 + 1, n01 + 1, n01))
    return nodes, els


KEYLINE = re.compile(r"^([A-Z][A-Z0-9]{2,7})(\s+)(\d+)(?=\s|$)")


def load_material(path, new_no=1):
    """读材料库 KEY，把每条关键字行的材料号改为 new_no。返回 (文本, 原材料号集合)。"""
    with io.open(path, "r", encoding="latin-1") as f:
        txt = f.read()
    out, seen = [], set()
    for line in txt.splitlines():
        m = KEYLINE.match(line)
        if m and m.group(1) == "UNIT":
            if m.group(3) != "1":
                sys.exit("材料文件 UNIT=%s，不是 SI（1）；请改用库里的 _s 文件" % m.group(3))
            continue  # UNIT 已在过程段给出
        if m:
            seen.add(m.group(3))
            line = m.group(1) + m.group(2) + "%d" % new_no + line[m.end():]
        line = re.sub(r"(Property Data of Material\s+)\d+", lambda mm: mm.group(1) + str(new_no), line)
        out.append(line)
    if len(seen) > 1:
        print("警告：材料文件含多个材料号 %s，全部改成了 %d，请人工核对" % (sorted(seen), new_no), file=sys.stderr)
    if not any(l.startswith("FSTRES") for l in out):
        sys.exit("材料文件里没有 FSTRES（流动应力），不像 DEFORM 材料 KEY")
    return "\n".join(out).rstrip("\n"), seen


def e3(x):
    """1.2345678E+001 样式（三位指数，与 DEFORM 材料库一致）。"""
    m, e = ("%.7E" % float(x)).split("E")
    return "%sE%s%03d" % (m, "-" if int(e) < 0 else "+", abs(int(e)))


def die_material(p):
    return "\n".join([
        "*", "*  Property Data of Material     2  (rigid-die thermal only)", "*",
        "MTNAME       2",
        p.get("die_mat_name") or "RigidDie_thermal",
        "FRAE2H       2  9.0000000E-001",
        "FPERV        2  0.0000000E+000",
        "FRCMOD       2       0  0.0000000E+000  0.0000000E+000  0.0000000E+000  0.0000000E+000",
        "FSTRES       2       0  1.0000000E+002",
        "YOUNG        2       0  2.0675400E+005",
        "POISON       2       0  3.0000000E-001",
        "EXPAND       2       0  1.2000000E-005  2.0000000E+001",
        "THRCND       2       0  " + e3(p["die_thrcnd"]),
        "HEATCP       2       0  " + e3(p["die_heatcp"]),
        "EMSVTY       2       0  7.0000000E-001",
        "MASDEN       2       0  7.8500000E-009",
        "HDNPHA       2       0  0.0000000E+000",
        "MSTMTR       2       0",
        "CREEP        2       0",
        "DIFCOE       2       0  0.0000000E+000",
        "ELRST        2       0  0.0000000E+000",
        "UTSDAT       2       0  0.0000000E+000",
        "HDNRUL       2       0",
        "PMEAB        2       0  0.0000000E+000",
        "PMITT        2       0  0.0000000E+000",
        "BURGRS       2       0  0.0000000E+000",
        "ALPHA        2       0  0.0000000E+000",
        "NDISFM       2       0  0.0000000E+000",
        "SRFNRG       2       0  0.0000000E+000",
    ])


def object_header(obj, otype, name, vel_angle, vel, temp, avgstr):
    return ["*", "*  Data for Object #     %d" % obj, "*",
            kw("OBJTYP", obj, otype, 0), kw("OBJNAM", obj), name,
            kw("AVGSTR", obj, avgstr), kw("LMTSTR", obj, 0.001), kw("ZSTR", obj, 0, 0.0),
            kw("PENVOL", obj, 1.0e6, 1), kw("REFTMP", obj, temp), kw("TMPLMT", obj, 0.0),
            kw("TRGVOL", obj, 0, 0.0), kw("ELPSOL", obj, 0), kw("OTPRNG", obj, 0, 0.0, 0.0),
            kw("PRSNAM", obj), "",
            kw("MOVCTL", obj, 1, 0, vel_angle, vel), kw("STROKE", obj, 0.0, 0.0),
            kw("ANGMOV", obj, 1, 0, 0.0), kw("CNTRAX", obj, 0.0, 0.0, 0.0), kw("OBJUPD", obj, 0)]


def emit_mesh(L, obj, nodes, els, temp, mat, p, remesh=False):
    L.append(kw("RZ", obj, len(nodes)))
    for i, (r, z) in enumerate(nodes, 1):
        L.append("%8d%s%s" % (i, sci(r), sci(z)))
    L.append(kw("DRZ", obj, 0, 0.0))
    axis = [i for i, (r, z) in enumerate(nodes, 1) if abs(r) < 1e-12]  # 轴线节点 Vr=0
    L.append(kw("BCCDEF", obj, len(axis), 0))
    for n in axis:
        L.append("%8d%8d%8d" % (n, 1, 0))
    for k, v in (("BCCDFN", (0, 0)), ("URZ", (0, 0.0)), ("FRZ", (0, 0.0)), ("BCCTMP", (0, 0)),
                 ("BCCTFN", (0, 0)), ("NDTMP", (0, temp, 2)), ("NDHEAT", (0, 0.0)), ("USRNOD", (0, 0.0, 2))):
        L.append(kw(k, obj, *v))
    L.append(kw("ELMCON", obj, len(els)))
    for i, e in enumerate(els, 1):
        L.append("%8d%8d%8d%8d%8d" % ((i,) + tuple(e)))
    rm = remesh and p["remesh"]
    rows = [("MTLGRP", (0, mat)), ("STRAIN", (0, 0.0)), ("STNCMP", (0, 4, 0.0)), ("DENSTY", (0, 1.0)),
            ("DAMAGE", (0, 0.0)), ("STRESS", (0, 0.0, 4)), ("YLDS", (0, 0.0)), ("USRELM", (0, 0.0, 2)),
            ("RMDPTH", (0.0,)), ("RMSTRK", (float(p["rmstrk"]) if rm else 0.0,)), ("RMTIME", (0.0,)),
            ("RMSTEP", (int(p["rmstep"]) if rm else 0,)), ("MGSIZR", (float(p["mgsizr"]) if rm else 3.0,)),
            ("MGWTMP", (0.0,)), ("MGWSTN", (0.25,)), ("MGWSTR", (0.25,)),
            ("MGNELM", (int(p["mgnelm"]) if rm else 40,)), ("MGTELM", (int(p["mgtelm"]),)),
            ("MGWCUV", (0.5,)), ("MGGRID", (25, 25)), ("MGERR", (0.01, 32.0)), ("MGWUSR", (0.0,)),
            ("FRCSTP", (0,)), ("FRCNEL", (0,)), ("FRCMTH", (0,)), ("CRPTIM", (0,)), ("DATOM", (0, 0.0)),
            ("HDNEST", (0, 0, 0.0, 0.0)), ("HDNOBJ", (0, 0.0)), ("BCCCRB", (0, 0)), ("VOTAGE", (0, 0.0)),
            ("BCCRHT", (0, 0)), ("RHTFLX", (0, 0.0)), ("CSFREQ", (0, 0.0)), ("VOLCRG", (0, 0.0)),
            ("ZEFI", (0, 0.0)), ("CURRNT", (0, 0.0)), ("ECCDEF", (0, 0)), ("ECDEFN", (0, 0)),
            ("ECPRES", (0, 0.0)), ("ECCTMP", (0, 0)), ("ECTMFN", (0, 0)), ("ECHFLX", (0, 0.0)),
            ("ECCATM", (0, 0)), ("ECATFN", (0, 0)), ("ECAFLX", (0, 0.0)), ("ECCRHT", (0, 0)),
            ("ECRHFN", (0, 0)), ("ECRFLX", (0, 0.0)), ("MATAXI", (0, 1, 0.0))]
    for k, v in rows:
        L.append(kw(k, obj, *v))


def emit_diegeo(L, obj, corners):
    L.append(kw("DIEGEO", obj, 1, len(corners)))
    for i, (r, z) in enumerate(corners, 1):
        L.append("%8d%s%s%s" % (i, sci(r), sci(z), sci(0.0)))


def contact_pair(o1, o2, relation, fric, ihtc):
    return [kw("CNTACT", o1, o2, relation), kw("FRCFAC", o1, o2, 1, 0, fric), kw("FRCROT", o1, o2, 0, 0.0),
            kw("IHTCOF", o1, o2, 0, ihtc), kw("SEPRES", o1, o2, 0, 0.0), kw("SEPDEN", o1, o2, 0.0),
            kw("INTRST", o1, o2, 0, 0.0)]


def coerce(k, v):
    d = DEFAULTS.get(k)
    if isinstance(d, bool):
        return str(v).lower() in ("1", "true", "yes", "on")
    if isinstance(d, int):
        return int(v)
    if isinstance(d, float) or d is None:
        try:
            return float(v)
        except ValueError:
            return v
    return v


def build(p, material_txt, outdir):
    R, H, NAME = float(p["R"]), float(p["H"]), p["name"]
    TEMP = float(p["temp"])
    DTEMP = TEMP if p.get("die_temp") in (None, "") else float(p["die_temp"])
    RATE = float(p["rate"]); VEL = RATE * H; STROKE = float(p["reduction"]) * H; T_END = STROKE / VEL
    DEMAX = float(p["demax"]); DTMAX = DEMAX / RATE
    DIE_R, DIE_T = float(p["die_R"]), float(p["die_T"])
    wp_nodes, wp_els = structured_rect(0.0, R, 0.0, H, int(p["nr"]), int(p["nz"]))
    top_nodes, top_els = structured_rect(0.0, DIE_R, H, H + DIE_T, int(p["dnr"]), int(p["dnz"]))
    bot_nodes, bot_els = structured_rect(0.0, DIE_R, -DIE_T, 0.0, int(p["dnr"]), int(p["dnz"]))
    dia = "phi%gx%g" % (2 * R, H)
    title = p.get("title") or "2D axi hot compression %s %s %gC %g/s %gpct" % (
        p["material_label"], dia, TEMP, RATE, 100 * float(p["reduction"]))

    L = ["*", "*  DEFORM-2D V11.0 KEYWORD FILE",
         "*  Auto-built: axisymmetric hot compression of a phi%g x %g mm cylinder" % (2 * R, H),
         "*", "*  Process Definition", "*", "TITLE", title,
         kw("CURSIM", 1, 0, 0), "SIMNAM", NAME,
         kw("SMODE", 3), kw("STYPE", 1), kw("GEOTYP", 1), kw("MESHNO", 1), kw("UNIT", 1),
         kw("TNOW", 0.0, 0.0, 0, 0.0), kw("TRANS", 1, 1, 0, 0, 0), kw("HTMTHD", 0),
         kw("STNOUT", 0, 0, 0, 0, 1, 0, 0), kw("ELMNOD", 10),
         "       0       0       0       0       0       0       0       0       0       0",
         "*", "*  Stopping & Step Controls", "*",
         kw("NSTART", -1), kw("STPINC", int(p["stpinc"])), kw("PDIE", 1, 0), kw("OSCTRL", 0, 0, 0, 0),
         kw("NSTEP", int(p["nstep"])), kw("EMAX", 0.0), kw("TMAX", T_END), kw("SMAX", 0.0, STROKE),
         kw("VMIN", 0.0, 0.0), kw("LMAX", 0.0, 0.0), kw("STPDEF", 1), kw("DEMAX", DEMAX),
         kw("DTMAX", DTMAX, 0.0), kw("DTTYPE", 0, 0), kw("SLDERR", 0.0), kw("DTPMAX", 0.0, 0.0, 0.0, 0.0, 0.0),
         kw("DVMAX", 0.0, 0.0), kw("MDSOBJ", 0, 0, 0, 0.0), kw("CNTERR", 0, 0.0), kw("VFACTR", 0), kw("DTSUB", 0.0),
         "*", "*  Iteration Controls", "*",
         kw("CVGERR", 0.001, 0.01), kw("ITRMTH", 2), kw("SOLMTD", 1), kw("ITRMXD", 200), kw("DEFBWD", 1),
         kw("SOLMTT", 1), kw("ITRMXT", 200), kw("TMPBWD", 1), kw("LATENT", 0),
         "*", "*  Processing Conditions", "*",
         kw("GEOERR", 1.0e-6, 1.0e-4), kw("PENINF", 1.0e9), kw("UNTE2H", 1.0), kw("TINTGF", 0.75),
         kw("BLZMAN", 5.669e-11), kw("ENVTMP", 0, float(p["envtmp"])), kw("CNVCOF", 0, float(p["cnvcof"])),
         kw("ENVMPR", 1.26e-9), kw("ENVMPT", 8.80e-15), kw("EHRATE", 0.0), kw("ENVATM", 0, 1.69),
         kw("ACVCOF", 0, 2.5e-4),
         "*", "*  User Defined Variables", "*",
         kw("UNNAME", 1, 2), "", "", kw("UENAME", 1, 2), ""]
    L.append("")
    L.append(material_txt)
    L.append(die_material(p))
    L.extend(object_header(1, 1, "TOP_FLAT_DIE", -90.0, VEL, DTEMP, RATE))
    emit_diegeo(L, 1, [(0.0, H), (DIE_R, H), (DIE_R, H + DIE_T), (0.0, H + DIE_T)])
    emit_mesh(L, 1, top_nodes, top_els, DTEMP, 2, p)
    L.extend(object_header(2, 2, "WORKPIECE_" + dia.upper().replace("X", "x"), 0.0, 0.0, TEMP, RATE))
    emit_mesh(L, 2, wp_nodes, wp_els, TEMP, 1, p, remesh=True)
    L.extend(object_header(3, 1, "BOTTOM_FLAT_DIE", -90.0, 0.0, DTEMP, RATE))
    emit_diegeo(L, 3, [(0.0, -DIE_T), (DIE_R, -DIE_T), (DIE_R, 0.0), (0.0, 0.0)])
    emit_mesh(L, 3, bot_nodes, bot_els, DTEMP, 2, p)
    L.extend(["*", "*  Inter-Object Data", "*"])
    L.extend(contact_pair(2, 1, 1, float(p["fric"]), float(p["ihtc"])))  # 工件为从，模具为主
    L.extend(contact_pair(2, 3, 1, float(p["fric"]), float(p["ihtc"])))
    L.append(kw("CNTACT", 1, 3, 0))
    L.append("")

    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    for i, line in enumerate(L):
        try:
            (line if isinstance(line, bytes) else line.encode("ascii"))
        except (UnicodeEncodeError, UnicodeDecodeError):
            sys.exit("KEY 第 %d 行含非 ASCII 字符（标题/名称请用英文）：%r" % (i + 1, line[:60]))
    key_path = os.path.join(outdir, NAME + ".KEY")
    with io.open(key_path, "w", encoding="latin-1", newline="\n") as f:
        f.write(u"\n".join(L) + u"\n")
    with open(os.path.join(outdir, "preprocess_actions.key"), "w") as f:
        f.write("\n".join(["KFREAD", NAME + ".KEY", "KFWRIT", "input_readback.KEY",
                           "GENCTC 0.0001", "GENDB 2", NAME + ".DB", ""]))
    used = dict(p, die_temp=DTEMP, derived=dict(top_die_speed_mm_s=VEL, stroke_mm=STROKE, duration_s=T_END,
                dtmax_s=DTMAX, wp_nodes=len(wp_nodes), wp_elements=len(wp_els),
                die_nodes=len(top_nodes), die_elements=len(top_els)))
    with open(os.path.join(outdir, "params_used.json"), "w") as f:
        json.dump(used, f, indent=1, sort_keys=True)
    print("wrote", key_path, "lines", len(L), "bytes", os.path.getsize(key_path))
    print("VEL %.6g mm/s  STROKE %.6g mm  T_END %.6g s  DTMAX %.6g s" % (VEL, STROKE, T_END, DTMAX))
    return key_path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--params", help="JSON 参数文件（缺省项用内置默认值）")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="覆盖单个参数，可重复")
    ap.add_argument("--material-key", required=True, help="材料库 SI KEY 文件（安装目录 2D/MaterialLibrary/... 下的 _s*.KEY）")
    ap.add_argument("--outdir", default=".", help="输出目录（工程目录）")
    a = ap.parse_args()
    p = dict(DEFAULTS)
    if a.params:
        with open(a.params) as f:
            for k, v in json.load(f).items():
                if k.startswith("_"):
                    continue
                if k not in DEFAULTS and k != "title":
                    sys.exit("未知参数：%s" % k)
                p[k] = v
    for s in a.set:
        k, v = s.split("=", 1)
        if k not in DEFAULTS and k != "title":
            sys.exit("未知参数：%s" % k)
        p[k] = coerce(k, v)
    if float(p["reduction"]) <= 0 or float(p["reduction"]) >= 1:
        sys.exit("reduction 应在 (0,1)")
    mat, seen = load_material(a.material_key)
    print("material numbers in source:", sorted(seen), "-> 1")
    build(p, mat, a.outdir)


if __name__ == "__main__":
    main()
