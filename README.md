# AgentRig / Engineering Harness

`harness` 是一个工具无关的工程规则 CLI。它按项目和任务选择规则，生成可交给 Codex、Claude Code 或其他编码助手的提示词。CLI 需要 Python 3.12，运行时没有第三方依赖，也不调用模型。

## 选择项目配置

| 配置 | 适用范围 | 加载的规则与检查 |
| --- | --- | --- |
| `backend` | 后端服务或全栈项目的后端部分，适用任意语言 | 提示词包含两类规则：大对象存储、耗时任务异步化。源码检查包含两项提示：疑似数据库大字段、非测试 Python 文件中的 `time.sleep` |
| `frontend` | 纯界面、样式、组件和客户端交互 | 提示词包含首条规则：页面不得依赖小字解释。源码检查暂不启用 |

存储和异步是后端的设计问题，规则可以跨语言使用。文件大小和耗时阈值是项目配置，应按响应要求、存储和部署环境调整。默认耗时阈值触发异步评估，也要判断当前响应是否必须拿到结果。详见 [工程规则](docs/rules.md)。前端页面说明规则与框架和样式方案无关，详见 [前端规则](docs/frontend-rules.md)。

## 接入 Codex 和 Claude Code

在编码助手实际运行的环境安装一次。先克隆本仓库，再从本地源码安装：

```bash
git clone https://github.com/Brx121/AgentRig.git
cd AgentRig
uv tool install --from "$PWD" engineering-harness
harness --version
```

### 卸载与清理

`uv tool install` 安装在当前宿主机用户环境中。卸载全局 `harness` 命令使用：

```bash
uv tool uninstall engineering-harness
```

卸载后可用下面命令确认命令已不可用：

```bash
command -v harness
```

注意：卸载全局命令不会修改或删除任何目标项目。项目中的 `.harness/`，以及 `AGENTS.md`、`CLAUDE.md` 里由 AgentRig 管理的说明块仍会保留。如果要让某个项目停止自动调用 Harness，需要删除这两个文件中从 `<!-- AgentRig: begin -->` 到 `<!-- AgentRig: end -->` 的整段内容；如果不再需要项目配置，再按版本管理方式移除 `.harness/`。只重新安装 CLI 时，可再次执行原来的 `uv tool install --from ...` 命令。

后端项目在根目录运行：

```bash
harness setup --profile backend
```

也可在其他目录运行 `harness setup /path/to/project --profile backend`。未指定时，已配置的项目沿用自己的配置，未配置的项目默认使用 `backend`。后端配置会把调用说明写入项目的 `AGENTS.md` 和 `CLAUDE.md`，保留其中的手写内容。建议把生成的项目文件随仓库提交。见 [Codex 项目说明](https://learn.chatgpt.com/docs/agent-configuration/agents-md) 和 [Claude Code 项目说明](https://code.claude.com/docs/en/memory)。

纯前端项目也运行 `harness setup --profile frontend` 接入。它会创建项目配置、架构说明、提示词模板和审查清单，并把前端调用说明写入项目的 `AGENTS.md` 和 `CLAUDE.md`。如果项目原有 AgentRig 管理的后端说明块，切到前端配置时会替换为前端说明块。

## 按任务调用

全栈项目保留后端配置，涉及前后端的任务把规则用在后端部分。纯前端项目由助手按项目说明调用 Harness，并把页面可读性约束带入提示词。

```bash
# 使用当前项目的配置
harness prompt --kind bugfix -- "修复报表导出反复超时"

# 使用另一个项目的配置
harness prompt --path /path/to/project --kind feature -- "新增批量导出"

# 如果需要给纯前端任务导出一份提示词
harness prompt --profile frontend --kind feature -- "调整表格样式"

# 从标准输入读取多行需求（Bash）
harness prompt --kind feature - < task.txt
```

`--kind` 支持 `feature`、`bugfix` 和 `refactor`。提示词的 `--profile` 只影响当次任务。从子目录调用时，工具向上找最近的项目配置，到独立 Git 仓库边界为止。没有终端的助手可直接接收生成的 Markdown。

### 目标项目更新示例

假设目标项目是 `/projects/order-service`，现在要新增一个订单报表导出功能。

更新分为两类：

- **更新 AgentRig CLI**：AgentRig 规则、模板或检查逻辑发布新版本后，先更新 CLI，再到目标项目运行 `harness setup` 同步管理文件。
- **更新目标项目工程上下文**：目标项目新增存储、队列、worker、外部服务，或调整阈值与验收重点后，更新 `.harness/` 中的配置、架构说明和审查清单。

#### 最简更新方法

后端项目的常规更新只需要重新安装 CLI，再同步目标项目管理文件：

```bash
# 1. 更新 AgentRig 源码并重装 CLI
cd /path/to/AgentRig
git pull origin main
uv tool install --force --from "$PWD" engineering-harness

# 2. 进入目标项目并同步配置
cd /projects/order-service
harness setup --profile backend
git diff -- .harness AGENTS.md CLAUDE.md
```

前端项目把最后一行改为 `harness setup --profile frontend`。确认 diff 符合预期后，将 `.harness/`、`AGENTS.md` 和 `CLAUDE.md` 的管理块更新提交到目标项目。

首次接入，或项目后端架构发生变化后，在目标项目根目录同步配置和助手说明：

```bash
cd /projects/order-service
harness setup --profile backend
git diff -- .harness AGENTS.md CLAUDE.md
```

`setup` 可以重复运行。它会补齐缺失的 `.harness` 文件、更新 `AGENTS.md` 和 `CLAUDE.md` 中由 AgentRig 管理的说明块，并保留手写内容。若项目增加了对象存储、队列或新的后台任务，同步后应更新 `.harness/ARCHITECTURE.md` 和 `.harness/REVIEW_CHECKLIST.md`，让下一次生成的提示词继续反映真实架构。

#### 更新目标项目的工程上下文

目标项目新增对象存储、队列、worker、外部服务，或调整响应时延、对象大小阈值时，按下面顺序更新：

1. 调整 `.harness/config.json` 中与本次架构相关的阈值。
2. 更新 `.harness/ARCHITECTURE.md`，记录新的数据存储、队列、worker、外部调用和部署方式。
3. 更新 `.harness/REVIEW_CHECKLIST.md`，补充架构变化后的审查重点。
4. 运行 `harness check --json`，确认配置和文档有效。
5. 将 `.harness/` 变更与业务架构变更提交到同一个目标项目 commit。

普通业务需求不需要更新这些文件；只有工程架构、阈值或审查重点变化时才更新。

#### 更新 AgentRig CLI

AgentRig 自身发布更新后，在 AgentRig 仓库更新代码、验证测试，并重装全局命令：

```bash
cd /path/to/AgentRig
git pull origin main
uv sync --locked
uv run --locked pytest
uv tool install --force --from "$PWD" engineering-harness
harness --version
```

安装完成后回到目标项目，先同步管理文件，再处理当前需求：

```bash
cd /projects/order-service
harness setup --profile backend
git diff -- .harness AGENTS.md CLAUDE.md
harness prompt --kind feature -- "新增订单报表导出，导出可能超过 3 秒，需要异步任务和下载链接"
```

先阅读生成的提示词，回答预检问题，再开始修改业务代码。已接入 Codex 或 Claude Code 的项目通常会由助手按项目说明自动执行这一步。实现完成后运行：

```bash
harness check --strict --json
```

处理完检查结果后，将业务代码变更和 `.harness/` 中反映架构变化的文件一起提交到订单项目仓库。

## 配置与检查

项目配置保存在 `.harness/config.json`。后端默认对象上限是 1,048,576 字节，默认从预计 3 秒开始评估后台执行。项目的实际架构写在 `.harness/ARCHITECTURE.md`，审查要点写在 `.harness/REVIEW_CHECKLIST.md`。

后端可以编辑 `.harness/PROMPT_TEMPLATE.md`。必须保留 `{task_description}` 和 `{constraints}`，也可用 `{kind}`、`{kind_focus}`、`{preflight}`、`{architecture}` 和 `{checklist}`。字面花括号写成 `{{` 和 `}}`。

```bash
harness check --json
harness check --strict --json
```

`check` 按项目配置校验文件，并只运行该配置启用的源码检查。后端扫描是启发式提示，不能验证对象实际大小或判断业务是否适合异步。`--strict` 让告警也返回失败。前端配置校验管理文件、提示词模板和架构章节，不做源码扫描。

## 扩展规则

在 [规则注册表](src/harness/profiles.py) 定义规则的提示词、预检问题、架构说明和审查项，再将它加入需要的配置。若需要源码提示，在 [检查模块](src/harness/check_command.py) 注册检查函数，并只为适用配置启用。这样可以添加前端、特定后端或其他用途的规则，现有任务只加载所选配置的内容。

在源码目录验证改动：

```bash
uv sync --locked
uv run --locked pytest
```
