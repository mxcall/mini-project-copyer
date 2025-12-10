
**使用说明：**

**使用说明：**

本工具用于文件/文件夹拷贝，支持 exclusions 排除配置。
所有的配置项均通过 `config.json` 文件进行设置，不再支持命令行参数。

**配置步骤 (Config)：**

1. 打开 `config.json` 文件。
2. 修改配置项（**注意：路径中的反斜杠 `\` 需要转义，例如 `D:\\path`**）：
   - `TARGET_DIR`: 目标存放目录（必填）。
   - `HTTP_PORT`: HTTP服务端口，默认 10888。
   - `SRC_PDIR`: 批量扫描的父目录。如果设置此项，将扫描该目录下的子文件夹。
   - `SRC_DIR`: 单个源目录。如果 `SRC_PDIR` 为空，将使用此配置。
   - `SRC_PDIR_PREFIX`: 需要扫描的子目录前缀列表（仅在 `SRC_PDIR` 生效时使用），例如 `["XXX_", "YYY_"]`。
   - `EXCLUDE_DIRS`: 需要排除的文件夹名称。
   - `EXCLUDE_PATTERNS`: 需要排除的文件模式（支持通配符）。

**运行方式：**

```bash
# 激活环境 (如有)
.venv\Scripts\activate.bat

# 运行脚本
python main.py

# 打包
uv run pyinstaller --onefile --noconsole --name "mini-project-copyer" main.py
```

**特性：**

- ✅ **配置文件驱动**：所有设置集成在 `config.json`，无需记忆复杂的命令行参数。
- ✅ **智能优先级**：优先使用 `SRC_PDIR` 进行批量扫描；若未配置，则回退到 `SRC_DIR` 单目录拷贝。
- ✅ **前缀过滤**：支持自定义多个目录前缀（如 `XXX_`, `YYY_`）。
- ✅ **自动备份**：自动添加日期后缀（格式：`原文件夹名_YYYYMMDD`）。
- ✅ **排除机制**：支持文件夹和文件模式的递归排除。
- ✅ **安全覆盖**：如果生成的带日期后缀的目标文件夹已存在，会自动清理旧版并重新拷贝。
- ✅ **HTTP预览**：内置HTTP服务器，可把目标目录映射为Web服务，支持日志查看。