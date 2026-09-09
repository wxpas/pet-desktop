[app]

# ============================================================
#  电子宠物 · Buildozer 配置文件
#  Kivy Android 打包配置
# ============================================================

# ---------- 基本信息 ----------

# 应用标题（显示在 Android 桌面图标下方，支持中文）
title = 电子宠物

# 应用包名（应用名部分，与 package.domain 组成完整包名）
# 完整包名 = package.domain + "." + package.name
package.name = desktop

# 应用包域名（反向域名格式）
# 与 package.name 组合后完整包名为：org.pet.desktop
package.domain = org.pet

# 源代码所在目录（相对于 buildozer.spec 的路径）
source.dir = .

# 主程序入口文件（Python 主模块）
source.include_exts = py,png,jpg,kv,atlas,json,ttf,otf

# 额外需要包含的文件/目录（默认会自动包含 source.dir 下的所有文件）
# 这里明确列出确保资源被正确打包
source.include_patterns =
    sprites/*.png,
    sprites/**/*.png,
    sprites/**/**/*.png,
    pet_config.json,
    pet_library.json,
    pet_state.json,
    pet_core/*.py

# 需要排除的文件/目录（开发期文件不进 APK）
source.exclude_patterns =
    __pycache__,
    */__pycache__,
    **/__pycache__,
    *.pyc,
    *.pyo,
    .git*,
    .idea,
    .vscode,
    buildozer.spec,
    make_sprites.py,
    sprite_preview_all.png,
    sprite_sheet_*.png,
    sprite_sheet_raw.png,
    cockroach_pet.py,
    宠物控制台.py,
    代码结构分析报告.md,
    使用说明.md,
    APK打包说明.md,
    build_apk_colab.ipynb,
    *.bat,
    *.vbs,
    .github,
    pet_apk_build.zip

# ---------- 版本信息 ----------

# 应用版本号（用户可见）
version = 1.0

# ---------- 需求与依赖 ----------

# Python 版本要求
requirements = python3, kivy==2.3.1, pillow

# 额外的 Python 包索引（可选）
# pypi = https://pypi.org/simple/

# ---------- 方向与显示 ----------

# 屏幕方向：landscape（横屏）、portrait（竖屏）、sensor（自适应）
orientation = landscape

# 是否全屏模式（隐藏状态栏和导航栏）
fullscreen = 1

# ---------- Android 配置 ----------

# Android API 级别（目标 SDK 版本，使用较新的稳定版）
android.api = 33

# Android 最低支持的 API 级别
android.minapi = 21

# Android NDK 版本
android.ndk = 25b

# Android SDK 工具版本
# android.sdk = 24.0.0

# 支持的 CPU 架构
# 可选：armeabi-v7a, arm64-v8a, x86, x86_64
android.archs = armeabi-v7a, arm64-v8a

# 应用权限
# INTERNET：网络权限（可选，预留未来功能）
# VIBRATE：震动权限（可选，用于震动反馈）
# 不需要危险权限（如 CAMERA、READ_CONTACTS 等）
android.permissions = INTERNET, VIBRATE

# 应用图标（各分辨率图标路径，留空则使用默认图标）
# 建议尺寸：72x72(ldpi)、96x96(mdpi)、144x144(hdpi)、192x192(xhdpi)
# icon.filename = %(source.dir)s/data/icon.png
# icon.presplash = %(source.dir)s/data/presplash.png
# icon.presplash_color = #FFFFFF

# 启动页（Splash Screen）配置
# android.presplash = %(source.dir)s/data/presplash.png
# android.presplash_color = #FFFFFF

# ---------- 服务与活动 ----------

# 入口 Activity 名称（一般不需要修改）
# android.entrypoint = org.kivy.android.PythonActivity

# 是否允许备份
android.allow_backup = True

# 是否可调试（发布版设为 0）
android.debug = 0

# ---------- 元数据 ----------

# 应用支持的屏幕尺寸
android.support_screens = small, normal, large, xlarge

# 最低 OpenGL ES 版本（Kivy 需要 2.0）
android.opengl = 2

# ---------- 服务配置 ----------

# 前台服务（可选，用于保活）
# android.services =

# ---------- 构建配置 ----------

# 构建模式：debug 或 release
# 可通过命令行参数覆盖：buildozer android debug/release
# 默认为 debug

# 输出目录
# build.dir = .buildozer

# ---------- 高级选项 ----------

# 启动时白屏等待时间（毫秒），设置较长时间避免启动时黑屏
android.wait_for_debugger = 0

# 是否启用 AndroidX 支持库
android.useAndroidX = True

# 是否在 AndroidManifest.xml 中添加 cleartext 支持
# （Android 9+ 默认禁止明文 HTTP，若使用 HTTP 接口需开启）
# android.cleartext = False

# 网络安全配置文件路径（可选）
# android.network_security_config =

# ---------- 环境变量 ----------

# 构建时设置的环境变量
# android.gradle_dependencies =
# android.add_aapt2 = True

# ---------- 过滤与优化 ----------

# 是否启用 aab 格式（Android App Bundle，用于 Google Play 发布）
# android.aab = False

# 是否压缩 Python 字节码
# python.compile = True

# ============================================================
#  [buildozer] 全局配置
# ============================================================

[buildozer]

# 构建日志级别：debug, info, warning, error
log_level = 2

# 构建警告级别
warn_on_root = 1

# 构建输出目录
# build_dir = .buildozer

# 二进制缓存目录（加速重复构建）
# bin_dir = bin

# 下载缓存目录
# cache_dir = .buildozer/cache

# 临时目录
# tmp_dir = .buildozer/tmp

# ============================================================
#  构建说明
# ============================================================
#
# 首次构建（debug 版）：
#   buildozer android debug
#
# 发布构建（release 版）：
#   buildozer android release
#
# 清理构建：
#   buildozer android clean
#
# 部署到设备（需开启 USB 调试）：
#   buildozer android debug deploy run
#
# 查看日志：
#   buildozer android logcat
#
# 注意事项：
#   1. 首次构建会自动下载 Android SDK/NDK，耗时较长，请耐心等待
#   2. Windows 下建议使用 WSL 或 Linux 虚拟机进行构建
#   3. 图标和启动图可后续添加到项目中，再取消对应注释
#   4. 如需上架应用商店，需配置签名证书（android.sign 相关）
#   5. pet_state.json 为运行时状态文件，打包的是默认初始状态
#
# ============================================================
