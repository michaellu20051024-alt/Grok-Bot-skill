---
name: deepseek
description: >-
  仅当用户明确说要用 DeepSeek 时使用（所有 bot 通用）：把写作、翻译、总结等生成类活交给 DeepSeek
  API，并按任务自动选模型（deepseek-flash / deepseek-v4-pro）和思考深度；用户没说就不用。
---
# DeepSeek 分流

盒子上用 `scripts/deepseek.py` 调 DeepSeek 官方接口（与 OpenAI 兼容，`https://api.deepseek.com`）。脚本只用 Python 标准库。路径：`<技能目录>/scripts/deepseek.py`。

## 什么时候用
- 适用于用户的所有 bot，包括以后新建的。
- 默认不用。只有用户在当前任务里明确说要用 DeepSeek（如「用 DeepSeek」「交给 DeepSeek」）才用；用户没说，就不主动分流，也不主动建议。用户对 A bot 说的「用 DeepSeek」随任务转给其他岗位时一并写明。
- 用户说了要用但没指定模型或深度时，自己按任务复杂度、长度、专业性选，不再问：
  - `deepseek-flash` + `low`：短翻译、摘要、改写、格式整理等简单活。
  - `deepseek-flash` + `high`：一般长度的写作、较长翻译、需要一定推理的总结。
  - `deepseek-v4-pro` + `high`：长文写作、专业术语密集或逻辑要求高的内容、多文档综合。
  - `deepseek-v4-pro` + `max`：很难、很长、要严密推理的任务，或上一档结果明显不够好时重做。
  - 拿不准时先选低一档，结果不行再升一档。用户指定了模型或深度就照用户的。
- 交付时用一句话说明用了哪个模型和哪档深度。

## 先看能不能外发
- 内容会发到 DeepSeek 的服务器。涉及未发表的科研数据、实验结果、专利技术方案、他人个人信息或账号凭据时，先问用户能不能外发，没有明确同意就不发。
- 分流不是零成本：调用方 bot 侧准备任务、调用脚本、核对结果照样算用量；DeepSeek 侧按用户自己的 DeepSeek 账户另计费。
- 适合分流：需要大量生成文字的初稿、翻译、总结、改写。不适合：需要工具、联网检索、引用核实的活。结果是初稿，交付前仍要按各岗规则核对事实、数字和引用。

## Key
- 只从环境变量 `DEEPSEEK_API_KEY` 读。绝不把 Key 写进脚本、命令行参数、日志、结果文件或聊天；不要 `echo` 它，只用 `[ -n "$DEEPSEEK_API_KEY" ]` 检查是否存在。
- 缺 Key 时脚本报错退出，告诉用户需要重新提供，不要问明文。

## 用法
```
S=<技能目录>/scripts/deepseek.py
python3 $S models                                   # 列模型、输入类型、effort 档位
python3 $S chat -e low -p "把这段译成英文：..."     # 默认 deepseek-flash
python3 $S chat -m deepseek-v4-pro -e high -f task.md -o out/result.json
```
- `-m` 模型：`deepseek-flash`（默认，快、便宜）或 `deepseek-v4-pro`（更强）。模型名以 `models` 实时返回为准。
- `-e` effort：`low` / `high` / `max`，不传则用接口默认（目前 high）；按上面「什么时候用」选。
- `-f` 从 Markdown/文本文件读任务（UTF-8）；`-p` 直接给提示；都不给则读标准输入。`-s` 加系统提示。
- `-o` 把结果存成 JSON（模型、effort、来源文件、正文、finish_reason、token 用量、耗时），UTF-8 且不转义中文；默认不存思考过程，需要时加 `--keep-reasoning`。
- `--timeout` 默认 300 秒；429/5xx/网络错误自动重试 2 次；其他 HTTP 错误打印接口报错并以非 0 退出。`--max-tokens`、`--temperature` 可选。
- 长文先写进任务文件再用 `-f`，不要塞进命令行。输出被截断时脚本会警告，调大 `--max-tokens` 或拆任务。

## 交付
- 核对后再用，不原样转贴；照各岗的中文去 AI 味、不编数字规则修改。
- 结果 JSON 只是中间产物，放在工作目录；是否进 Drive 按各岗交付规则。

## 已验证 / 未验证（编写时）
- 已实测：`models`；flash（`-f` Markdown、`-e low`、`-o`）；pro（`-p`、`-e low`、`-o`）；错误模型名返回 HTTP 400 并非 0 退出。
- 未实测：超时与重试路径、`max` effort、图像输入（脚本暂不支持传图）、长文本。effort 参数接口接受，但档位对效果的影响未量化。
