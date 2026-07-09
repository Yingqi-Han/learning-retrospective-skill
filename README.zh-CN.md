# Learning Retrospective Skill（学习复盘技能）

[English](README.md) | **简体中文**

`learning-retrospective` 是一个小型、与具体 agent 无关的技能（skill），用于终止重复试错并沉淀已验证的经验教训。

它适用于 Codex、Claude Code、Cursor、Cline、OpenCode，以及任何能加载 `SKILL.md` 式指令或纯 Markdown 指导的 agent 环境。

## 设计哲学

失败不等于错误——在**新问题**上反复尝试是正当的探索过程。这个技能要消灭的浪费是：**同一个问题解决第二次**——上一个会话已经解决过的坑，因为教训没被记录或没被召回，又重新从头踩一遍。因此它区分两种模式：遇到**已知问题**（已有教训覆盖该失败特征）时，先召回并遵循教训再动手；遇到**新问题**时自由探索——只是永远不要一字不改地重试——并在解决后自动把教训沉淀下来。

## 功能

- 在来之不易的成功之后自动捕获教训（两次以上失败、非显然的变通方案、机器特有的事实）——这是主要模式。
- 在重新推导修复方案之前先查记忆里有没有已有教训，并把问题分类为"已知"或"新"。
- 检测一字不改的重试循环，在继续切换工具之前强制做一次证据盘点。
- 在展开大范围排查之前设置明确的失败门（failure gate）。
- 只捕获已验证、可复用的教训。
- 把教训写入正确的层级：用户级记忆、项目级记忆或技能更新。
- 可选地请任何可用的第二审阅者（agent 或模型）做有边界的审计。
- 可选地通过 harness 钩子（hook）自动激活：检测到重复失败时注入提醒（见 `learning-retrospective/references/hook-activation.md`；其中 Claude Code 检测器已于 2026-07-09 实机部署并验证）。

## 快速开始

```bash
git clone https://github.com/Yingqi-Han/learning-retrospective-skill.git
cd learning-retrospective-skill
python install.py --agent codex     # 或：--agent claude
python install.py --agent project --target ./.agent-skills   # 项目级
```

安装器会先跑测试套件，再复制嵌套的技能文件夹并验证结果。钩子是可选的，**默认不安装**；只有在读过 [`SECURITY_NOTES.md`](SECURITY_NOTES.md) 之后才使用 `--with-hooks`，且注册步骤始终需要手动完成。想让 AI agent 代为安装，把 [`INSTALL_FOR_AGENTS.md`](INSTALL_FOR_AGENTS.md) 指给它即可。

让 AI agent 代装时，可以直接给它这段话：

```text
Clone https://github.com/Yingqi-Han/learning-retrospective-skill and install it
for Codex or Claude Code following INSTALL_FOR_AGENTS.md. Do not install hooks
unless I explicitly confirm.
```

只预览将要写入的位置、不实际改文件：

```bash
python install.py --agent codex --dry-run
```

## 手动安装

把嵌套的技能文件夹复制到受支持的技能目录。不要复制仓库根目录，除非你的 agent 明确支持仓库级技能发现。

```text
learning-retrospective/
  SKILL.md
  VERSION
  agents/openai.yaml
  references/
  examples/
  hooks/      # 可运行的重试循环检测脚本（可选）
  tests/      # 钩子脚本的自动化测试
```

示例：

```bash
# 正确做法：复制嵌套的技能文件夹，而不是仓库根目录
cp -r ./learning-retrospective ~/.codex/skills/

# Claude Code 风格的本地技能
cp -r ./learning-retrospective ~/.claude/skills/

# 项目级共享技能
mkdir -p ./.agent-skills
cp -r ./learning-retrospective ./.agent-skills/
```

如果你的 agent 不支持技能文件夹，把 `SKILL.md` 粘贴进它的自定义指令，需要时再加载 references 里的文件。

### 触发词本地化

仓库里的 `SKILL.md` 保持纯 ASCII，因为至少有一个技能校验器（Windows 上的 Codex `quick_validate.py`）用系统默认编码读文件，在 GBK 环境下遇到非 ASCII 字节会崩溃。如果你用其他语言与 agent 交互、且你的 harness 支持 UTF-8（Claude Code 支持），请把母语触发词追加到你**已安装副本**的 `description:` 行——当触发词与你实际输入的语言一致时，基于描述的召回率会显著提高。可复制的中文触发词片段和其他语言的指引见 `learning-retrospective/references/localization.md`。

### 钩子（可选，安装前先读安全说明）

`learning-retrospective/hooks/` 里有 Claude Code 和 Codex 两个版本的可运行重试循环检测脚本，`learning-retrospective/tests/` 里有配套的自动化测试（只依赖标准库）：

```bash
python learning-retrospective/tests/test_retry_loop_detector.py
```

钩子是会在以后每次工具调用时运行的本地可执行代码——安装前请阅读 `SECURITY_NOTES.md`，审查脚本内容，注册后用一次故意失败做实机验证。各 harness 的注册步骤见 `learning-retrospective/references/hook-activation.md`。

## 兼容性

| Agent | 测试状态 | 安装位置 | 说明 |
|---|---:|---|---|
| Codex | 已验证：结构校验 + 子代理实测（Windows 11，Codex 桌面版 26.623.141536，2026-07-09） | `~/.codex/skills/` | 使用 `SKILL.md` frontmatter 和可选的 `agents/openai.yaml`；为兼容 Windows 校验器请保持 `SKILL.md` 纯 ASCII。钩子配置已通过管道测试；钩子字段形状是经验观察，升级后需重测。 |
| Claude Code | 已验证：部署并被发现（Windows 11，2026-07-09） | `~/.claude/skills/` | 复制文件夹即可；技能从 `SKILL.md` frontmatter 实时发现，无需重启。`agents/openai.yaml` 会被忽略。基于钩子的自动激活同日实机验证——见 `references/hook-activation.md`。 |
| Cursor | 尚未测试 | rules 或自定义指令 | 粘贴 `SKILL.md`；需要时手动加载 references。 |
| Cline | 尚未测试 | `.clinerules` 或 memory bank | 若不支持技能文件夹，可作为纯 Markdown 工作流指导使用。 |
| OpenCode | 尚未测试 | 自定义技能或指令目录 | 若支持，用同样的 `SKILL.md` + references 模式。 |

## 安全默认值

- 除非用户明确要求保存/更新教训，否则不写入用户记忆、仓库规则、项目文档或其他技能。
- 权限不明确时，先呈现拟写入的教训和目标位置。
- 不存储密钥、token、cookie、凭据、隐私数据、大段原始日志或未经验证的猜测。
- 先完成用户的任务，再花时间写复盘。
- 安装钩子脚本前请阅读 [`SECURITY_NOTES.md`](SECURITY_NOTES.md)：钩子是本地可执行代码，教训是持久化的特权写入（存在记忆污染风险面）。

## 示例

`examples/` 目录包含具体的循环模式：

- PDF 渲染/转换循环
- GitHub Actions 重试循环
- DOCX 转换循环
- Zotero 链接附件循环
- 依赖安装循环
- 一份填写完整的教训实例（LibreOffice 转换），展示捕获产物应有的样子
- 反例（`bad-lessons.md`）：会污染记忆、必须拒绝的捕获模式

## 定位

这不是记忆数据库、MCP 服务器、钩子框架或自主技能生成器。它是一个小的控制环，负责判断：

1. 我们是否在重复失败的尝试？
2. 我们漏掉了哪个已验证的事实？
3. 下一个有证据支撑的动作是什么？
4. 未来的 agent 应该记住什么教训？

它可以与 Claudeception、10x/agent-loom、claude-memory-skill、agentmemory 等更大的系统配合使用。

## 许可证

MIT，见 `LICENSE`。
