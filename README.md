# 研数公式速查 2.0

面向考研数学一的 Windows 离线公式检索工具。覆盖高等数学、线性代数、概率论与数理统计，重点回答三个问题：公式是什么、什么时候用、什么情况下不能直接用。

![研数公式速查 2.0 界面](docs/界面预览.png)

## 直接使用

从仓库的 `release/研数公式速查-2.0.exe` 下载后双击运行，不需要安装 Python、Node.js 或数据库。

- Windows 10/11 64 位
- 需要 Microsoft Edge WebView2 Runtime；较新的 Windows 通常已自带
- 当前 EXE 未购买商业代码签名证书，Windows 可能显示“未知发布者”

## 内容与功能

- 208 个公式主题、24 个章节
- 高等数学 113 条
- 线性代数 39 条
- 概率论与数理统计 56 条
- 公式、适用场景、成立条件、禁用边界、易错点、解题步骤和关联公式
- 中文自然语言、题型、别名、关键词与 LaTeX 混合检索
- 收藏、最近查看、逐行复制、速查模式、置顶、明暗主题和系统托盘
- 左侧章节、中间结果和右侧详情分别滚动，修复长列表无法滚动的问题
- 完全离线，公式由本地 KaTeX 排版

可尝试搜索：

- `泰勒 展开`
- `同阶 无穷小`
- `方差未知 均值`
- `二重积分 换元`
- `矩阵求逆`
- `路径无关`

## 快捷键

| 快捷键 | 作用 |
|---|---|
| `Ctrl + Shift + Space` | 全局唤出或隐藏窗口 |
| `Ctrl + Alt + M` | 备用全局唤出快捷键 |
| `Ctrl + K` | 聚焦搜索框 |
| `↑` / `↓` | 在结果中移动 |
| `Enter` | 打开当前结果 |
| `Ctrl + D` | 收藏或取消收藏 |
| `Ctrl + Shift + C` | 复制当前公式 LaTeX |
| `Alt + 1 / 2 / 3` | 切换高数、线代、概率 |
| `Esc` | 清空搜索；再次按下隐藏窗口 |

若全局快捷键被其他软件占用，可从系统托盘唤出。

## 本地数据

收藏、最近查看、主题和窗口设置保存在：

```text
%APPDATA%\KaoyanMathQuickRef\settings.json
```

应用不上传搜索记录或个人数据。

## 从源码运行

需要 Python 3.12：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

打包：

```powershell
.\build.ps1
```

生成文件位于 `dist/研数公式速查-2.0.exe`。

## 内容校验

内容库在打包前经过：

- 字段完整性、ID 唯一性、科目与章节覆盖检查
- 208 条公式的 KaTeX 离线渲染检查
- 极限、泰勒展开、导数、Jacobian、矩阵、概率分布与统计量等代表性高风险公式的 SymPy 符号核验
- 实际 EXE 启动、中文显示、搜索、独立滚动和窄窗口布局检查

运行完整校验需要 Node.js 与开发依赖：

```powershell
.\.venv\Scripts\python.exe validate_content.py `
  --node (Get-Command node).Source `
  --katex-root web\vendor_src\node_modules\katex
```

## 资料来源

公式库不是对单一资料的照搬。主要交叉参考：

- [EndaCai / kaoyanMath](https://gitee.com/EndaCai/kaoyanMath)
- [OpenStax Calculus](https://openstax.org/subjects/math)
- [MIT OpenCourseWare 18.06 Linear Algebra](https://ocw.mit.edu/courses/18-06sc-linear-algebra-fall-2011/)
- [Penn State STAT 414/415](https://online.stat.psu.edu/stat414/)

第三方许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

本工具用于复习速查，不替代教材推导与报考年度正式考试大纲。
