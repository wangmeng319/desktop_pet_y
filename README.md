# Desktop Pet Y

Y 是一个面向 macOS 的非官方桌宠。角色造型参考 Hotta Studio 的《异环》（Neverness to Everness，NTE）角色 Y 和曳尔沐。项目以 Python 和 PySide6 实现，交互和 PNG 帧动画的组织思路参考了 VPet。项目用于非商业同人创作。 [《异环》官方社区](https://steamcommunity.com/app/4508340/allnews/?l=schinese) · [VPet](https://github.com/LorisYounger/VPet)

| 平台 | 状态 |
| --- | --- |
| macOS | 当前支持和主要验证平台，已在 Apple Silicon 上测试 |
| Windows | 待验证，暂未列入支持范围 |

## 快速开始

准备 Python 3.13 和 uv。在克隆或下载仓库后，进入项目目录运行：

```sh
uv sync --locked
uv run main.py
```

Y 会出现在主屏幕右下角，并在所在的普通桌面空间保持置顶。全屏空间由 macOS 管理。目前通过源码运行。

| 操作 | 效果 |
| --- | --- |
| 按住角色拖动 | 拖起时切换悬空姿势，松手时播放落地帧 |
| 在角色上滚动 | 缩放立绘，保留脚底位置 |
| 单击头、手或手臂 | 闭眼微笑 |
| 单击躯干、腿或脚 | 脸红羞怒 |
| 双击角色 | 打开对话窗口 |
| 右键角色 | 打开对话、清空记忆、预览开口表情或退出 |

待机时 Y 会眨眼，并平均约每分钟自动散步一次。左右都能走完整段时随机选方向，靠近屏幕边缘时优先选择空间足够的一侧。互动期间到期的散步会顺延。

## 接入模型

桌宠的基本动作无需 API。启用对话时，将 `.env.example` 复制为 `.env`，填入自己的配置：

```sh
cp .env.example .env
```

| 配置项 | 含义 |
| --- | --- |
| `ELYMS_CHAT_URL` | 兼容 Chat Completions 的服务地址，例如 `https://api.deepseek.com`。根地址或 `/v1` 基础地址会自动补上 `/chat/completions`，也可填写完整端点 |
| `ELYMS_CHAT_MODEL` | 服务商提供的模型 ID |
| `ELYMS_CHAT_API_KEY` | API 密钥，本地服务无需鉴权时可留空 |

程序启动时自动读取项目根目录的 `.env`。同名环境变量优先。修改 [系统提示词](config/system-prompt.txt) 后，下一条消息就会使用新内容。

已完成的对话存于 `~/Library/Application Support/Y/chat-history.sqlite3`，重启后会恢复。每次发送会把系统提示词、当前消息和最近六轮对话发给所配置的服务。右键选择「清空记忆」并确认后，**会删除本地全部聊天记录**。

## 项目结构

```text
main.py                    启动入口
y_pet/
  app.py                   桌宠窗口、鼠标交互和动画调度
  chat.py                  对话窗口和模型请求
  memory.py                SQLite 对话记录
  theme.py                 聊天窗口与气泡的像素风样式
assets/y/              运行所需的 PNG 帧和步行图集
config/system-prompt.txt   系统提示词
docs/                      素材说明和发布前检查
.env.example               模型配置模板
pyproject.toml / uv.lock   项目依赖和锁文件
```

## 后续计划

- 添加更多动作、待机动画
- 偏好设置
- 更好的历史记忆管理

## 素材来源与发布

角色形象和设定来自《异环》。运行用立绘与动作帧以角色参考图为基础，通过 AI 生成和局部合成制作。VPet 作为实现参考，当前仓库使用独立的 Python 实现。详见[来源与素材说明](THIRD_PARTY_NOTICES.md)。

## 源码许可证

项目自有源码按 [PolyForm Noncommercial 1.0.0](LICENSE) 公开，允许非商业使用、修改和分享改版。授权范围限于项目自有源码。
