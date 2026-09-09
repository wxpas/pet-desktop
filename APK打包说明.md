# 电子宠物 · APK 打包说明

> Kivy 版本的电子宠物应用，支持打包为 Android APK。

---

## 快速开始（推荐）

最快的方式是使用 **GitHub Actions** 自动构建，只需把代码推到 GitHub 即可：

```bash
# 1. 初始化 Git 仓库
git init
git add .
git commit -m "Initial commit"

# 2. 创建 GitHub 仓库并推送
git remote add origin https://github.com/你的用户名/电子宠物.git
git branch -M main
git push -u origin main

# 3. 在 GitHub 仓库页面 → Actions 中查看构建进度
#    构建完成后在 Artifacts 中下载 APK
```

详见下方「方法零：GitHub Actions 自动构建」。

---

## 一、项目结构

```
电子宠物/
├── main.py                  # Kivy 主程序入口
├── buildozer.spec           # Buildozer 打包配置
├── build_apk_colab.ipynb    # Google Colab 在线打包脚本
├── .github/workflows/
│   └── build-apk.yml        # GitHub Actions 自动构建配置
├── .gitignore               # Git 忽略文件
├── pet_core/                # 核心游戏逻辑（跨平台）
│   ├── __init__.py
│   ├── constants.py         # 常量定义
│   ├── utils.py             # 工具函数
│   ├── pet_state.py         # 状态管理
│   └── game_logic.py        # RPG 游戏逻辑
├── sprites/                 # 精灵图资源
│   ├── cockroach/
│   ├── cat/
│   ├── dog/
│   ├── rabbit/
│   ├── hamster/
│   ├── corgi/
│   ├── penguin/
│   └── panda/
├── pet_library.json         # 宠物库定义（只读）
├── pet_config.json          # 默认宠物配置
└── pet_state.json           # 游戏存档（运行时生成）
```

---

## 二、本地开发测试（Windows）

### 2.1 安装依赖

```bash
pip install kivy pillow
```

### 2.2 运行程序

```bash
python main.py
```

### 2.3 操作说明

- **单击宠物**：惊吓反应（加速逃跑 + 气泡台词）
- **长按宠物**（0.5秒）：弹出操作菜单
- **菜单功能**：喂食、摸摸头、逗它玩、冒险、商店、背包、签到、成就、属性、更换宠物、退出

---

## 三、打包 APK 方法

### 方法零：GitHub Actions 自动构建（最推荐）

把代码推到 GitHub 后，Actions 会自动构建 APK，无需任何本地环境。

#### 前置条件
- 一个 GitHub 账号（免费）

#### 步骤：

1. **初始化 Git 仓库**
   ```bash
   cd 电子宠物
   git init
   git add .
   git commit -m "Initial commit"
   ```

2. **在 GitHub 创建新仓库**
   - 访问 https://github.com/new
   - 填写仓库名称（如 `pet-desktop`）
   - 选择 Public 或 Private
   - 不勾选 README、.gitignore 等初始化选项
   - 点击 Create repository

3. **推送代码到 GitHub**
   ```bash
   git remote add origin https://github.com/你的用户名/仓库名.git
   git branch -M main
   git push -u origin main
   ```
   如果是私有仓库，可能需要输入 GitHub 密码（建议使用 Personal Access Token）。

4. **查看构建进度**
   - 打开 GitHub 仓库页面
   - 点击顶部的 **Actions** 标签
   - 你会看到一个正在运行的 workflow：「Build Android APK」
   - 点击进入可以查看实时日志
   - 首次构建约 30-45 分钟（需要下载 Android SDK/NDK）
   - 后续构建约 15-25 分钟（有缓存）

5. **下载 APK**
   - 构建完成后（显示绿色对勾），点击进入该 workflow
   - 滚动到页面底部的 **Artifacts** 区域
   - 点击 `pet-app-debug-apk` 下载
   - 解压后即可得到 APK 文件

6. **安装到手机**
   - 将 APK 传到手机
   - 在手机上点击安装
   - 如果提示「未知来源」，在设置中允许安装未知来源应用

#### 触发构建的方式：
- **自动触发**：每次 push 到 main/master 分支时自动构建
- **手动触发**：在 Actions 页面点击「Run workflow」按钮
- **发布版本**：打 tag（如 `v1.0`）时自动创建 Release 并附带 APK

#### 优势：
- 完全免费（公开仓库无限，私有仓库每月 2000 分钟免费额度）
- 速度快，配置好的 Linux 环境
- 自动缓存，后续构建更快
- 支持 Release 自动发布

---

### 方法一：Google Colab 在线打包（无需本地环境）

使用 `build_apk_colab.ipynb` 在云端打包，最简单快捷。

#### 步骤：

1. 将整个项目打包为 zip 文件
   ```bash
   # 选中以下文件/文件夹打包：
   # main.py, buildozer.spec, pet_core/, sprites/, pet_library.json, pet_config.json
   # 注意：不要包含 pet_state.json（本地存档）
   ```

2. 上传 `build_apk_colab.ipynb` 到 Google Drive

3. 双击文件，选择「Google Colaboratory」打开

4. 依次运行每个单元格：
   - 第一步：安装环境（约 3-5 分钟）
   - 第二步：上传项目 zip 包
   - 第三步：确认/修改配置
   - 第四步：开始构建（约 20-40 分钟，首次构建较慢）
   - 第五步：下载生成的 APK

#### 注意事项：
- Colab 会话有时长限制（约 12 小时），但构建 APK 足够
- 首次构建需要下载 Android SDK/NDK，耗时较长
- 后续构建会快很多（有缓存）
- 如果构建失败，查看日志排查问题

---

### 方法二：Linux 本地打包（需要 Linux 环境）

如果你有 Linux 机器或 WSL2，可以在本地打包。

#### 步骤：

1. **安装系统依赖**
   ```bash
   sudo apt update
   sudo apt install -y build-essential git zip unzip openjdk-17-jdk python3-pip autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev
   ```

2. **安装 Python 依赖**
   ```bash
   pip3 install --user --upgrade Cython==0.29.36 buildozer
   echo 'export PATH=$PATH:~/.local/bin' >> ~/.bashrc
   source ~/.bashrc
   ```

3. **配置 Java 环境**
   ```bash
   export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
   export PATH=$JAVA_HOME/bin:$PATH
   ```

4. **进入项目目录，开始构建**
   ```bash
   cd /path/to/电子宠物
   buildozer android debug
   ```

5. **获取 APK**
   
   构建成功后，APK 文件在 `bin/` 目录下：
   ```
   bin/desktop-1.0-arm64-v8a-debug.apk
   ```

#### 常用 buildozer 命令：
```bash
buildozer android debug       # 构建 debug APK
buildozer android release     # 构建 release APK（需要签名）
buildozer android clean       # 清理构建缓存
buildozer -v android debug    # 详细输出
```

---

### 方法三：Docker 打包

如果你有 Docker 环境：

```bash
# 拉取 buildozer 镜像
docker pull kivy/buildozer

# 进入项目目录，运行容器
docker run --rm -v "$(pwd)":/home/user/hostcwd kivy/buildozer android debug
```

---

## 四、buildozer.spec 配置说明

关键配置项：

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `title` | 电子宠物 | 应用名称（中文） |
| `package.name` | desktop | 包名（英文） |
| `package.domain` | org.pet | 域名反向 |
| `source.dir` | . | 源码目录 |
| `source.include_exts` | py,png,jpg,json | 包含的文件扩展名 |
| `requirements` | python3,kivy==2.3.1,pillow | Python 依赖 |
| `android.api` | 33 | 目标 Android API 级别 |
| `android.minapi` | 21 | 最低支持 Android 5.0 |
| `android.arch` | armeabi-v7a,arm64-v8a | CPU 架构 |
| `android.permissions` | INTERNET,VIBRATE | 权限 |
| `orientation` | landscape | 横屏显示 |
| `fullscreen` | 1 | 全屏模式 |

### 修改应用名称

编辑 `buildozer.spec`，修改 `title` 字段：
```
title = 电子宠物
```

### 修改版本号

```
version = 1.0
```

### 添加权限

在 `android.permissions` 中添加，用逗号分隔：
```
android.permissions = INTERNET,VIBRATE,CAMERA
```

---

## 五、常见问题

### Q1: 构建失败，提示内存不足

A: Colab 免费版内存有限，尝试：
- 使用 `buildozer -v android debug` 查看详细错误
- 如果是 OOM，尝试增加交换空间或使用付费版 Colab

### Q2: APK 安装后闪退

A: 常见原因：
1. 权限问题 - 检查是否缺少必要权限
2. 资源路径错误 - 确认 sprites/ 目录被正确打包
3. 查看 logcat：`adb logcat | grep python`

### Q3: 中文显示乱码

A: Kivy 默认字体可能不支持中文，解决方案：
- 打包时包含中文字体文件
- 在 App 中设置中文字体

### Q4: 图片加载失败

A: 检查：
1. 图片路径是否正确
2. buildozer.spec 是否包含了图片文件
3. 使用 `source.include_exts` 确保 png 被包含

### Q5: 如何添加启动图标

A: 准备一张 512x512 的 PNG 图标，命名为 `icon.png`，放在项目根目录，然后在 buildozer.spec 中设置：
```
icon.filename = icon.png
presplash.filename = presplash.png
```

---

## 六、Android 版功能说明

### 与桌面版的差异

| 功能 | 桌面版 | Android 版 |
|------|--------|-----------|
| 显示方式 | 小窗口悬浮在桌面 | 全屏 App |
| 移动方式 | 移动窗口位置 | 移动屏幕上的精灵 |
| 透明背景 | 完全透明（可点击穿透） | 半透明背景 |
| 窗口置顶 | 支持 | App 内全屏 |
| 开机自启 | 支持（注册表） | 不适用 |

### Android 操作

- **点击宠物**：惊吓反应
- **长按宠物**：弹出菜单
- **返回键**：退出应用

---

## 七、后续优化方向

1. **添加启动图标和启动页**
2. **优化 APK 体积**（移除未使用的资源）
3. **添加音效和背景音乐**
4. **支持保存到 Google Play Games**
5. **添加广告或内购（可选）**
6. **适配更多屏幕尺寸**
7. **添加震动反馈**
8. **支持多语言**

---

*文档版本：v1.0 | 更新日期：2026-09-09*
