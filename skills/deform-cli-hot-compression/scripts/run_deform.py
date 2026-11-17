# -*- coding: utf-8 -*-
"""DEFORM-2D v11 命令行批处理：查找安装、前处理、求解（无 GUI）。兼容 Python 2.7 / 3.x。

只在工程目录内写文件；环境变量只在子进程里设置；不碰授权、注册表、安装目录。
在用户 Windows 机器上运行前须得到用户批准。

  python run_deform.py find                                   # 只读查找 DEF_PRE.exe
  python run_deform.py pre   --deform-root "<...\\DEFORM\\v11.0>" --workdir <工程目录> --name HOTCOMP_2D
  python run_deform.py arm   --deform-root ... --workdir ... --name ...
  python run_deform.py all   --deform-root ... --workdir ... --name ...
  python run_deform.py probe-pre --deform-root ... --workdir ...   # 只抓 DEF_PRE 菜单，确认菜单编号
"""
from __future__ import print_function
import argparse, glob, os, string, subprocess, sys, time

# DEF_PRE 文本菜单输入：空行、2(文件输入)、1(输入 KEYWORD)、动作文件、空行、E、E、Y
# 在 v11.0 2D 上验证过一次；其它版本先用 probe-pre 看菜单。
PRE_STDIN = "\n2\n1\npreprocess_actions.key\n\nE\nE\nY\n"


def find_installs():
    hits = []
    for d in string.ascii_uppercase:
        root = d + ":\\"
        if not os.path.isdir(root):
            continue
        for pat in ("Program Files\\SFTC\\DEFORM\\v*\\2D\\DEF_PRE.exe",
                    "Program Files (x86)\\SFTC\\DEFORM\\v*\\2D\\DEF_PRE.exe",
                    "SFTC\\DEFORM\\v*\\2D\\DEF_PRE.exe", "DEFORM*\\v*\\2D\\DEF_PRE.exe"):
            hits.extend(glob.glob(os.path.join(root, pat)))
    return sorted(set(hits))


def paths(root):
    d2 = os.path.join(root, "2D")
    return d2, os.path.join(d2, "DEF_PRE.exe"), os.path.join(d2, "DEF_ARM_CTL.com"), os.path.join(d2, "DEF_SIM.exe")


def env(root):
    d2 = os.path.join(root, "2D")
    e = os.environ.copy()
    e["DEFORM_DIR"] = d2
    e["DEFORM2_DIR"] = d2
    e["DEFORM3_DIR"] = os.path.join(root, "3D")
    e["DEFORM23_DIR"] = root
    e["PATH"] = d2 + ";" + root + ";" + e.get("PATH", "")
    return e


def _run(cmd, cwd, root, logname, stdin_text=None):
    logp = os.path.join(cwd, logname)
    t0 = time.time()
    lf = open(logp, "wb")
    rc = None
    try:
        p = subprocess.Popen(cmd, cwd=cwd, env=env(root), stdin=subprocess.PIPE, stdout=lf, stderr=subprocess.STDOUT)
        try:
            p.communicate(stdin_text.encode("ascii") if stdin_text else None)
        except Exception as ex:
            print("communicate error:", ex)
            try:
                p.kill()
            except Exception:
                pass
        rc = p.returncode
    finally:
        lf.close()
    print("%s returncode %s elapsed %.2f s" % (os.path.basename(cmd[0]), rc, time.time() - t0))
    try:
        sys.stdout.write(open(logp, "r").read())
    except Exception as ex:
        print("could not read log", ex)
    return rc


def run_pre(a):
    d2, pre, arm, sim = paths(a.deform_root)
    if not os.path.isfile(pre):
        sys.exit("找不到 %s" % pre)
    for fn in (a.name + ".KEY", "preprocess_actions.key"):
        if not os.path.isfile(os.path.join(a.workdir, fn)):
            sys.exit("工程目录缺 %s（先跑 build_key.py）" % fn)
    print("stdin:", repr(PRE_STDIN))
    rc = _run([pre], a.workdir, a.deform_root, "preprocess_pre.log", PRE_STDIN)
    db = os.path.join(a.workdir, a.name + ".DB")
    ok = os.path.isfile(db)
    print("DB exists:", ok, "size:", os.path.getsize(db) if ok else 0)
    log = open(os.path.join(a.workdir, "preprocess_pre.log"), "r").read()
    for s in ("Input data has no errors", "DEFORM Database Generated"):
        print("[%s] %s" % ("OK" if s in log else "缺", s))
    return rc, ok


def run_arm(a):
    d2, pre, arm, sim = paths(a.deform_root)
    if not os.path.isfile(arm):
        sys.exit("找不到 %s" % arm)
    rc = _run([arm, a.name, "B"], a.workdir, a.deform_root, "solver_launch.log")
    for fn in (a.name + ".LOG", a.name + ".MSG"):
        fp = os.path.join(a.workdir, fn)
        if os.path.isfile(fp):
            lines = open(fp, "r").read().splitlines()
            print("===== %s (%d lines, last 40) =====" % (fn, len(lines)))
            print("\n".join(lines[-40:]))
    log = os.path.join(a.workdir, a.name + ".LOG")
    if os.path.isfile(log):
        t = open(log, "r").read()
        print("[%s] 正常结束标志 'End of Simulation'" % ("OK" if "End of Simulation" in t else "缺"))
    return rc


def probe_pre(a):
    d2, pre, arm, sim = paths(a.deform_root)
    logp = os.path.join(a.workdir, "pre_menu_probe.log")
    lf = open(logp, "wb")
    p = subprocess.Popen([pre], cwd=a.workdir, env=env(a.deform_root), stdin=subprocess.PIPE, stdout=lf, stderr=subprocess.STDOUT)
    time.sleep(8)
    try:
        p.stdin.write(b"E\nE\nY\nQ\n"); p.stdin.flush()
    except Exception as ex:
        print("stdin write:", ex)
    time.sleep(3)
    if p.poll() is None:
        print("still running, killing pid", p.pid); p.kill()
    lf.close()
    sys.stdout.write(open(logp, "r").read())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["find", "pre", "arm", "all", "probe-pre"])
    ap.add_argument("--deform-root", help="DEFORM 版本目录，如 ...\\SFTC\\DEFORM\\v11.0（用 find 查到后填；含空格时可用 8.3 短路径）")
    ap.add_argument("--workdir", default=".", help="工程目录（KEY 所在处）")
    ap.add_argument("--name", default="HOTCOMP_2D")
    a = ap.parse_args()
    if a.cmd == "find":
        hits = find_installs()
        print("\n".join(hits) if hits else "未找到；请到卸载信息/开始菜单查实际安装位置")
        return
    if not a.deform_root:
        sys.exit("--deform-root 必填（先运行 find）")
    a.workdir = os.path.abspath(a.workdir)
    if a.cmd == "probe-pre":
        return probe_pre(a)
    if a.cmd in ("pre", "all"):
        rc, ok = run_pre(a)
        if not ok:
            print("PRE 没有生成 DB，不启动求解。")
            sys.exit(2 if not rc else rc)
    if a.cmd in ("arm", "all"):
        rc = run_arm(a)
        sys.exit(0 if rc == 0 else rc)


if __name__ == "__main__":
    main()
