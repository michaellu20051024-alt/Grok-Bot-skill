#!/usr/bin/env python3
"""DeepSeek API helper (OpenAI-compatible). Key read only from env DEEPSEEK_API_KEY."""
import argparse, json, os, sys, time, urllib.request, urllib.error

BASE = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")

def key():
    k = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not k:
        sys.exit("错误：环境变量 DEEPSEEK_API_KEY 未设置")
    return k

def req(method, path, body=None, timeout=300, retries=2):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    for attempt in range(retries + 1):
        r = urllib.request.Request(BASE + path, data=data, method=method, headers={
            "Authorization": "Bearer " + key(), "Content-Type": "application/json; charset=utf-8"})
        try:
            with urllib.request.urlopen(r, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")[:800]
            if e.code in (429, 500, 502, 503) and attempt < retries:
                time.sleep(3 * (attempt + 1)); continue
            sys.exit(f"HTTP {e.code}：{msg}")
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < retries:
                time.sleep(3 * (attempt + 1)); continue
            sys.exit(f"网络错误或超时（{timeout}s）：{getattr(e, 'reason', e)}")

def cmd_models(a):
    for m in req("GET", "/models", timeout=30).get("data", []):
        eff = m.get("effort", {})
        print(f"{m['id']}\t{m.get('name','')}\t输入:{','.join(m.get('input_modalities',[]))}\teffort:{','.join(eff.get('supported_levels',[]))}(默认{eff.get('default_level','?')})")

def cmd_chat(a):
    if a.file:
        with open(a.file, encoding="utf-8") as f: prompt = f.read()
    elif a.prompt:
        prompt = a.prompt
    else:
        prompt = sys.stdin.read()
    if not prompt.strip():
        sys.exit("错误：任务内容为空")
    msgs = []
    if a.system: msgs.append({"role": "system", "content": a.system})
    msgs.append({"role": "user", "content": prompt})
    body = {"model": a.model, "messages": msgs}
    if a.effort: body["reasoning_effort"] = a.effort
    if a.max_tokens: body["max_tokens"] = a.max_tokens
    if a.temperature is not None: body["temperature"] = a.temperature
    t0 = time.time()
    res = req("POST", "/chat/completions", body, timeout=a.timeout)
    ch = (res.get("choices") or [{}])[0]
    msg = ch.get("message", {})
    out = {"model": res.get("model"), "effort": a.effort, "source_file": a.file,
           "finish_reason": ch.get("finish_reason"), "content": msg.get("content", ""),
           "reasoning_content": msg.get("reasoning_content") if a.keep_reasoning else None,
           "usage": res.get("usage"), "elapsed_s": round(time.time() - t0, 1),
           "created": res.get("created")}
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"已保存：{a.out}", file=sys.stderr)
    print(out["content"])
    if ch.get("finish_reason") == "length":
        print("警告：输出因 max_tokens 被截断", file=sys.stderr)

def main():
    p = argparse.ArgumentParser(description="DeepSeek API 调用")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("models", help="列出可用模型").set_defaults(fn=cmd_models)
    c = sub.add_parser("chat", help="调用模型")
    c.add_argument("-m", "--model", default="deepseek-flash")
    c.add_argument("-e", "--effort", choices=["low", "high", "max"])
    g = c.add_mutually_exclusive_group()
    g.add_argument("-p", "--prompt"); g.add_argument("-f", "--file", help="从 Markdown/文本文件读任务")
    c.add_argument("-s", "--system")
    c.add_argument("-o", "--out", help="结果存 JSON 路径")
    c.add_argument("--max-tokens", type=int)
    c.add_argument("--temperature", type=float)
    c.add_argument("--timeout", type=int, default=300)
    c.add_argument("--keep-reasoning", action="store_true", help="JSON 里保留思考过程")
    c.set_defaults(fn=cmd_chat)
    a = p.parse_args(); a.fn(a)

if __name__ == "__main__":
    main()
