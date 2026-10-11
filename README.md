# Devin 简体中文汉化包

在 MS-CEINTL 官方 VS Code 简体中文语言包基础上，补齐 **Devin Desktop 私有字符串** 的汉化，
并额外覆盖语言包机制够不到的专属扩展/智能体面板 UI。

## 覆盖范围

| 层 | 内容 | 机制 | 状态 |
|---|---|---|---|
| 核心工作台 | 667 个 nls 键(Lifeguard、DeepWiki、智能体窗口、Devin 设置等) | VSIX 语言包 | ✅ |
| 内置扩展 | 32 个 nls 键(git worktree、品牌文案等) | VSIX 语言包 | ✅ |
| 专属扩展清单 | windsurf 等 5 个扩展 package.json 的 183 条可见字符串(命令、设置描述) | `patch_app.py` 直接改文件 | ✅ |
| 专属扩展 JS | 88 条硬编码 UI 串(通知、对话框、QuickPick) | `patch_app.py` 直接改文件 | ✅ |
| 智能体面板 | chat-client i18next 字典:translation 2829 键(含 localSettings/settingsHub/sidebar/sessionMenu)+ review 1075 键(97%),3 份 bundle 副本全部注入 | `patch_app.py` 注入 `englishOverrides`(深合并)+ `addResourceBundle` | ✅ |
| 本地设置页 | 设置行 label/description、方案与用量卡片、workbench 设置项等 ~340 条硬编码字面量 | `patch_app.py` 区域内受保护替换(`translations/app/ui_patch.json`) | ✅ |
| 剩余 webapp 字典 | settings/automations/codeScan 等 web 端为主的 ~8600 键 | 未翻译,回落英文 | ⏳ 可继续补 |

## 目录结构

```text
devin-chinese/
├── README.md
├── .gitignore
├── scripts/                    构建、安装、提取、分析与调试脚本
│   └── _paths.py               统一管理项目目录和外部安装路径
├── translations/               人工维护的翻译源文件
│   ├── core/                   核心工作台：zh_patch.json
│   ├── extensions/             扩展：ext_patch.json、pkg_patch.json、extjs_patch.json
│   ├── app/                    bundle 字面量补丁：ui_patch.json（分组 files/region/strings/raw）
│   └── chat/                   智能体面板：chat_patch_[1-5].json、chat_patch_review.json
├── data/
│   ├── extracted/              英文原文快照、缺失键及提取的字符串
│   └── reports/                分析报告、分区原文与审阅清单
├── build/
│   └── chat/                   生成的 chat_zh_translation.json、chat_zh_review.json
├── dist/                       生成的扩展目录与 VSIX 安装包
├── assets/
│   └── artwork/                绘图文件，与汉化构建无关
└── tests/                      使用临时目录的工作流回归测试
```

维护翻译时只修改 `translations/`；`data/` 保留提取快照和分析资料，方便核对来源。
`build/`、`dist/`、Python 缓存和补丁备份由 `.gitignore` 忽略，已有本地文件不受影响。
聊天字典和 VSIX 均可重新构建，不要直接编辑生成物。

## 环境与路径

脚本仅依赖 Python 标准库，已在 Python 3.10 上验证，无需安装第三方依赖。
以下命令从项目根目录执行；从其他目录调用时，使用脚本的绝对路径即可，
数据读写位置不会随当前工作目录变化。输出目录会在需要时自动创建。

| 环境变量 | 作用 | 默认值 |
|---|---|---|
| `DEVIN_APP` | Devin 的应用资源目录，包含 `extensions`、`out` 等 | `E:\Devin\resources\app` |
| `VSCODE_ZH_PACK` | 官方简体中文语言包目录，包含 `package.json`、`translations` | 用户主目录下的 `.devin/extensions/ms-ceintl.vscode-language-pack-zh-hans-1.126.0-universal` |

外部安装路径统一在 `scripts/_paths.py` 中定义，推荐通过环境变量覆盖。
旧版 `scripts/install.py` 未指定 `VSCODE_ZH_PACK` 时，仍从用户主目录的 `.devin/extensions` 查找官方包。

## 安装（两步）

### 1. 安装语言包 VSIX

```bash
python scripts/build.py   # 产出 dist/zzdevin.devin-language-pack-zh-hans-1.126.0.vsix
```

在 Devin 中 `Extensions: Install from VSIX...` 安装。
publisher 为 `zzdevin`，按字典序排在 `ms-ceintl` 之后，逐 id 覆盖时胜出，
**可与官方中文包共存，无需卸载**。

### 2. 应用专属扩展 + 智能体面板补丁

```bash
python scripts/build_chat_dict.py   # 合并 chat_patch_*.json → chat_zh_*.json 并校验
python scripts/patch_app.py         # 打补丁到 E:\Devin(可用 DEVIN_APP 环境变量改路径)
```

先从 `translations/chat/` 合并字典到 `build/chat/`，再应用补丁。
打 4 类文件，均先备份为 `*.devin-zh.bak`:

- `extensions/{windsurf,windsurf-dev-containers,windsurf-remote-*}/package.json`
- 上述扩展 `dist/extension.js` 中的字符串字面量
- chat-client 字典的 3 份 bundle 副本:
  `node_modules/@exa/chat-client/index.js`、
  `out/vs/workbench/windsurf-chat-client/index.js`、
  `out/vs/sessions/sessions.desktop.main.js`(智能体/会话窗口)——利用 bundle 自带的
  `englishOverrides` 机制把 zh 字典深合并进 i18next(`en` 命名空间，
  未翻译的键自动回落英文),并按各文件自身的 i18n 实例名注入 `review` 命名空间
- bundle 内硬编码 UI 字面量(上述 3 份 + `out/vs/workbench/workbench.desktop.main.js`):
  `translations/app/ui_patch.json` 按分组定义 files/region/strings/raw,
  只在锚定区间内替换,`id:`、`category:`、`value:`、`=`/`===` 等比较位自动跳过
- `product.json` 中上述已打补丁文件的 `checksums` 条目会同步更新为补丁后内容的
  sha256,避免 Devin 提示安装损坏;未打补丁的条目不会被改动

已打补丁的文件(带 `/*devin-zh*/` 标记)下次运行会从备份重新打补丁,
因此更新翻译后直接重跑即可,无需手动还原。

`python scripts/patch_app.py` 可带参数 `all|pkg|js|chat|ui`,
`chat`/`ui` 均执行整套 bundle 管线(字典注入 + 字面量替换)。

**重启 Devin 后生效。**

## 脚本索引

以下脚本均位于 `scripts/`：

| 脚本 | 作用 | 输入 / 输出 |
|---|---|---|
| `analyze.py` / `analyze_ext.py` | 对比 Devin nls 与官方包，输出缺失键 | `data/extracted/`、`data/reports/` |
| `build.py` | 生成 VSIX(publisher=zzdevin) | `translations/core/`、`translations/extensions/ext_patch.json` → `dist/` |
| `install.py` | 旧方案：就地补丁官方包(与 VSIX 等价，二选一即可) | 读取核心与扩展翻译，修改已安装的官方包 |
| `extract_pkg.py` / `extract_extjs.py` / `extract_dicts.py` | 提取专属扩展/package/webapp 字典原文 | `data/extracted/` |
| `extract_js.py` | 扫描 JS 中的候选 UI 字符串，可传入文件路径 | 结果输出到终端 |
| `debug_dict.py` | 检查 chat-client 嵌入字典的位置和转义 | 结果输出到终端 |
| `build_chat_dict.py` | 合并 + 校验(键存在性、占位符 `{{}}`/`<tag>` 一致性) | `translations/chat/` + `data/extracted/chat_*_en.json` → `build/chat/` |
| `patch_app.py` | 应用文件级补丁，幂等、感知 Devin 更新 | `translations/extensions/` + `build/chat/` → Devin 安装目录 |

## 验证

```bash
python -m unittest discover -s tests -v
```

测试在临时目录模拟官方语言包和 Devin 安装，覆盖翻译源文件布局、字典校验与合并、
VSIX 构建、提取和分析输出路径、补丁重复执行，以及旧版安装脚本。
测试从不同工作目录启动脚本，不依赖已有 `build/`、`dist/` 或真实 Devin 安装，也不会修改它们。

## Devin 升级后

`scripts/patch_app.py` 会检测文件是否被新版本替换并重新打补丁，只需：

```bash
python scripts/build.py && python scripts/build_chat_dict.py && python scripts/patch_app.py
```

官方语言包升级后重新安装 VSIX；若 nls 新增了缺失键，重跑 `scripts/analyze*.py` 补充翻译。

## 恢复

```bash
# 还原所有被 patch_app.py 修改的文件(包括 product.json)
for f in $(find /e/Devin/resources/app -name "*.devin-zh.bak"); do mv "$f" "${f%.devin-zh.bak}"; done
```

## 已知限制

- chat-client 字典只翻了约 23%(IDE 高频区块)+ review 97%；剩余为
  settings/automations/codeScan 等 Web 端管理界面，按需继续往
  `translations/chat/chat_patch_*.json` 里加键即可
- 智能体输出的实际内容(模型生成文本)不在 UI 字典内，不受影响
- `scripts/install.py`(就地补丁官方包)与 VSIX 方案二选一，两者内容一致不会冲突
