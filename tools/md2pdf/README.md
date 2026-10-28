# md2pdf · Markdown 转 PDF 工具

用 headless Chrome（DevTools Protocol）把 Markdown 渲染成带页眉页脚、样式化排版的 A4 PDF。

## 用法

```bash
python md2pdf.py <输入.md> <输出.pdf>
```

示例（从项目根目录执行）：

```bash
python tools/md2pdf/md2pdf.py \
  robot_app/docs/output/需求文档-简版.md \
  robot_app/docs/output/需求文档-简版.pdf
```

## 依赖

```bash
pip install markdown websocket-client
```

- `markdown` —— Python-Markdown（表格需 `tables` 扩展，脚本已启用）
- `websocket-client` —— 提供 `websocket` 模块，用于 DevTools 通信
- Chrome 或 Edge（脚本按顺序自动探测 `C:\Program Files\Google\Chrome\Application\chrome.exe` 等路径）

## 两个脚本的分工

| 脚本 | 作用 |
|---|---|
| `md2pdf.py` | 主转换脚本：Markdown → HTML → headless Chrome → PDF |
| `replace_pdf.py` | **Windows 同步盘专用补丁**。百度网盘等同步客户端会锁定已存在的 PDF，导致 `os.replace` 抛 `PermissionError (WinError 32)`。本脚本以退避重试方式替换目标文件。 |

同步盘场景下的完整流程：

```bash
python md2pdf.py 输入.md 输出.pdf        # 若报权限错误，.tmp 里已存好新文件
python replace_pdf.py 输出.pdf           # 退避重试替换
```

## 排版特性

- A4，页边距 20/17mm，中文字体优先 Microsoft YaHei
- 标题左侧蓝色竖线、表格斑马纹、代码块浅灰底
- 页眉显示文档名，页脚显示「页码 / 总页数」
- `h2` / `h3` 避免跨页断裂，表格行不跨页
- 支持 GFM 表格、围栏代码块、有序/无序列表

## 注意

- 生成后请确认 PDF 的**修改时间晚于源 md**，否则是旧版
- 输出文件若被同步盘锁定，先执行 `replace_pdf.py`，或手动删除旧 PDF 后重新生成
