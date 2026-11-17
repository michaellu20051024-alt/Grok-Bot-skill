---
name: deform-cli-hot-compression
description: >-
  需要在装有 DEFORM v11 的 Windows 电脑上，不点 GUI、用 KEY 文件和命令行建 2D 轴对称圆柱热压缩模型、
  批处理求解并导出载荷-行程曲线和终态应变/温度场时使用。在用户电脑上执行命令前必须先得到用户批准。
---
# DEFORM 命令行圆柱热压缩（2D 轴对称）

流程：参数 → `build_key.py` 生成 KEY 和前处理动作文件 → `DEF_PRE` 文本菜单生成 `.DB` → `DEF_ARM_CTL … B` 批处理求解 → `DEF_PST` 文本菜单提取 → `pst_to_csv.py` / `plot_results.py` 整理出图。全程无 GUI。

脚本（`scripts/`）：
- `build_key.py`、`run_deform.py`、`pst_to_csv.py`：兼容 Python 2.7（DEFORM 机器上可能只有 2.7），在用户机器上跑。
- `plot_results.py`：Python 3 + matplotlib，可在盒子上跑。
- `params_example.json`：一次已跑通试验的参数，作模板。

## 前提
- **在用户电脑上执行的每条命令都要先得到用户批准**（含只读探查）。只在工程目录内写文件；环境变量只在子进程里设；不改安装目录、授权、注册表、永久环境变量。
- **安装路径要查，不要假设**：`python run_deform.py find`（扫各盘常见位置），找不到再看卸载信息或开始菜单。路径含空格时可用 8.3 短路径。确认 `2D\` 下有 `DEF_PRE.exe`、`DEF_ARM_CTL.com`、`DEF_SIM.exe`、`DEF_PST.exe`。
- **授权**：确认 DEFORM 授权服务在跑（试验机上是 SFTC 自有 License Manager，服务 `DeformLicenseServer` 等，不是 FlexLM）。只看服务状态，不读口令或许可文件内容。
- **材料**：从安装目录 `2D\MaterialLibrary\Standard\<类别>\` 选 SI 单位文件（`_s*.KEY`，UNIT 1）。核对流动应力表的温度、应变速率范围覆盖本次工况；在表的边缘就换一个材料条目或告诉用户。
- **版本**：只在 v11.0 2D 上跑通过一次。其他版本先 `run_deform.py probe-pre` 看菜单编号是否一致。

## 参数（`params_example.json`，可用 `--set key=value` 覆盖）
| 参数 | 含义 | 试验值 |
|---|---|---|
| `R`, `H` | 工件半径、高度 / mm | 5, 15 |
| `die_R`, `die_T` | 平砧外半径、厚度 / mm | 12, 2 |
| `temp` | 工件初温 / °C | 1000 |
| `die_temp` | 模具温度；`null` = 同 `temp` | null |
| `rate` | 目标初始应变速率 / s⁻¹；上模速度 v = rate·H（恒速） | 0.1 |
| `reduction` | 压下率；行程 = reduction·H，时间 = 行程/v | 0.5 |
| `fric` | 常剪切摩擦因子 m | 0.3 |
| `ihtc` | 界面换热 / N·s⁻¹·mm⁻¹·°C⁻¹ | 0.4（取自安装目录官方 `GRN_UPSET.KEY` 示例，不是 GUI 默认按钮读出的值） |
| `envtmp`, `cnvcof` | 环境温度、对流系数 | 20, 0.02 |
| `demax`, `nstep` | 每步最大应变增量（DTMAX = demax/rate）、最大步数 | 0.02, 80 |
| `nr`, `nz`, `dnr`, `dnz` | 工件 / 每个模具结构网格 | 12×36, 8×2 |
| `remesh`, `rmstrk`, `rmstep`, `mgsizr`, `mgnelm`, `mgtelm` | 重划分 | 开, 1.5 mm, 15, 0.6 mm, 800, 4 |
| `die_thrcnd`, `die_heatcp` | 模具常值热物性（取模具温度下的值） | 32.896, 4.30（AISI-1045 表约 1000 °C） |
| `material_label`, `name`, `title` | 标题与工程名（只能用 ASCII） | AISI-1045, HOTCOMP_2D |

固定设置：`UNIT 1`（mm、N、MPa、s、°C）、`GEOTYP 1` 轴对称、`TRANS 1 1` 非等温变形、上模方向 −90°、工件为从对象、轴线节点 Vr=0、接触由 `GENCTC 0.0001` 生成。改 `temp` 时别忘了 `die_temp` 和模具热物性。

## 步骤（每步执行前取得用户批准）
1. 工程目录：在用户指定位置新建一个空目录，不和别的工程混放。
2. 生成 KEY：
   `python build_key.py --params params.json --material-key "<库内 _s*.KEY>" --outdir <工程目录>`
   输出 `<name>.KEY`、`preprocess_actions.key`（KFREAD/KFWRIT/GENCTC/GENDB）、`params_used.json`。
3. 前处理：`python run_deform.py pre --deform-root "<…\DEFORM\v11.0>" --workdir <工程目录> --name <name>`
   向 `DEF_PRE.exe` 送 `\n2\n1\npreprocess_actions.key\n\nE\nE\nY\n`（主菜单 2 文件输入 → 1 输入 KEYWORD）。日志要有 `Input data has no errors`、`DEFORM Database Generated`，并且生成了 `.DB`。
4. 求解：`python run_deform.py arm …`（`DEF_ARM_CTL.com <name> B`）。`.LOG` 末尾应为达到 TMAX/SMAX 的停止信息和 `End of Simulation`；记录重划分次数和墙钟时间。
5. 后处理（`DEF_PST.exe` 文本菜单，打开同一 `.DB`）：「4. Data Extraction」→「5. Object Information」→「1. OBJECT CHARACTERISTICS」，逐个正解步导出对象特征（含 `STROKE` 和 `* OBJECT_DATA`）；终态步再导出工件 `RZ`、`ELMCON`、`STRAIN`、`NDTMP`（可加 `STRESS`、`STRATE`）。**不要用「7. Load-Stroke-Time」**：v11 2D 试验里它的行程和力全为 0。
   > 试验时 DEF_PST 的逐键菜单输入没有存档，本技能没有现成脚本；先手动在命令行走一遍菜单，把按键序列记下来再自动化。
6. 整理：`python pst_to_csv.py --time <步>=<秒> … <步>=<导出文件> …`（时间取自日志/PST，不要按行程反推后冒充提取值）；再 `python plot_results.py --curve load_stroke_curve.csv --fields <终态导出> --wp-obj 2 --label "<工况>" --outdir <目录>`。

## 验证（交付前逐条过）
- 日志：前处理无错误；求解正常结束，不是因发散或报错停止。
- 终态行程 = reduction·H（例 −7.50 mm），终态高度 = H·(1−reduction)。
- 力平衡：上下模 Fy 大小相等、符号相反（`pst_to_csv.py` 不平衡 >1% 会警告）。
- 载荷-行程曲线大致单调上升；重划分步附近可有小折点，要标出来。
- 均匀压缩交叉检验：工件平均等效应变 ≈ ln(1/(1−reduction))（50% 压下时 ≈ 0.693）。
- 场分布合理：鼓形、应变在模具圆角附近最高、端面中心较低；温升量级与塑性功和换热相符。
- 复现对照：首次跑通后，自行记下同一组参数的终载、平均等效应变、最大半径、温度范围、重划分次数和求解时间，供以后同参数复现时对照；这些值只是流程对照，不是材料或实验结论。

## 已知限制 / 未验证（照实告诉用户）
- `DEF_PST`「Load-Stroke-Time」导出的行程与力为 0，不能当结果；载荷取自 OBJECT CHARACTERISTICS / OBJECT_DATA。
- 2D `DEF_PRE` 的 `KFWRIT` 只回写控制和材料，不含网格和场；场数据须走 `DEF_PST`。
- 新一代 `DEF_GUI_PST.exe -m steplist` 打开 2D 库时访问冲突退出；场图是用提取的文本画的，不是 DEFORM 原生色带截图。
- 文档写明 64 位求解只用于 3D；2D 走 32 位 `DEF_SIM` / `DEF_ARM`。
- 没做过 3D、多 CPU；没改过全局许可或队列设置。
- 模型是流程可行性模板：材料来自库表，摩擦与换热是取定值，**不是**针对某篇论文或实验的标定结果。
- 界面换热 0.4 取自官方实验 KEY，GUI 默认值没有单独核对。
- `build_key.py` 的材料号改写只用从已跑通 KEY 中取出的材料段测过（含 8→1 改号）；直接读真实库文件尚未在 DEFORM 机器上验证，第一次用时检查 `input_readback.KEY` 里的材料段。
- `pst_to_csv.py` 只用一个终态步的导出验证过（与试验 CSV 第 26 步一致）；多步导出的文件格式需第一次使用时核对。

## 不要做
- 不在用户机器上未经批准执行命令；不安装软件、不改注册表/授权/安装目录。
- 不假设安装路径或版本；不编造载荷、场数据或时间。
- 不把流程试验结果说成材料标定或实验验证结论。
