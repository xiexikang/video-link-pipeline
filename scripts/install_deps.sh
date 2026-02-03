#!/bin/bash
# 视频提取系统依赖安装脚本
# 支持 macOS 和 Linux

set -e

echo "======================================"
echo "视频提取与处理系统 - 依赖安装"
echo "======================================"
echo

# 检查操作系统
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    echo "检测到操作系统: macOS"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    echo "检测到操作系统: Linux"
else
    echo "警告: 未识别的操作系统 $OSTYPE"
    OS="unknown"
fi

# 检查并安装 Homebrew (仅限 macOS)
if [ "$OS" = "macos" ]; then
    if ! command -v brew &> /dev/null; then
        echo "正在安装 Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
fi

# 安装系统依赖
echo
echo "[1/5] 安装系统依赖..."
echo "--------------------------------------"

if [ "$OS" = "macos" ]; then
    # macOS 依赖
    echo "安装 FFmpeg..."
    brew install ffmpeg || echo "FFmpeg 安装失败，请手动安装"
    
    echo "安装其他工具..."
    brew install wget curl git || true
    
    # 检查 Python
    if ! command -v python3 &> /dev/null; then
        echo "安装 Python3..."
        brew install python
    fi
    
elif [ "$OS" = "linux" ]; then
    # Linux 依赖
    if command -v apt-get &> /dev/null; then
        # Debian/Ubuntu
        echo "使用 apt 安装依赖..."
        sudo apt-get update
        sudo apt-get install -y ffmpeg wget curl git python3 python3-pip python3-venv
    elif command -v yum &> /dev/null; then
        # RHEL/CentOS/Fedora
        echo "使用 yum 安装依赖..."
        sudo yum install -y ffmpeg wget curl git python3 python3-pip
    elif command -v pacman &> /dev/null; then
        # Arch Linux
        echo "使用 pacman 安装依赖..."
        sudo pacman -Sy ffmpeg wget curl git python python-pip
    else
        echo "警告: 无法识别包管理器，请手动安装 FFmpeg、Python3 和 pip"
    fi
fi

echo "✓ 系统依赖安装完成"

# 检查 Python 版本
echo
echo "[2/5] 检查 Python 版本..."
echo "--------------------------------------"

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python 版本: $PYTHON_VERSION"

# 检查是否为 Python 3.8+
REQUIRED_VERSION="3.8"
if python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
    echo "✓ Python 版本符合要求 (>= 3.8)"
else
    echo "✗ Python 版本过低，需要 >= 3.8"
    exit 1
fi

# 创建虚拟环境
echo
echo "[3/5] 创建 Python 虚拟环境..."
echo "--------------------------------------"

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✓ 虚拟环境已创建"
else
    echo "✓ 虚拟环境已存在"
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source venv/bin/activate

# 升级 pip
echo "升级 pip..."
pip install --upgrade pip

# 安装 Python 依赖
echo
echo "[4/5] 安装 Python 依赖..."
echo "--------------------------------------"

if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo "✓ Python 依赖安装完成"
else
    echo "✗ 未找到 requirements.txt 文件"
    exit 1
fi

# 下载 Whisper 模型（可选）
echo
echo "[5/5] 检查 Whisper 模型..."
echo "--------------------------------------"

echo "Whisper 模型将在首次转录时自动下载"
echo "如需预下载，可以运行: python -c 'from faster_whisper import WhisperModel; WhisperModel(\"small\")'"

# 创建必要的目录
echo
echo "创建项目目录..."
echo "--------------------------------------"

mkdir -p output temp logs

echo "✓ 目录创建完成"

# 配置检查
echo
echo "======================================"
echo "安装完成!"
echo "======================================"
echo
echo "接下来你需要:"
echo
echo "1. 编辑 config.yaml 配置你的 API Keys (可选):"
echo "   - Claude API Key (用于生成摘要)"
echo "   - OpenAI API Key (替代方案)"
echo
echo "2. 激活虚拟环境:"
echo "   source venv/bin/activate"
echo
echo "3. 测试视频下载:"
echo "   python download_video.py 'https://www.youtube.com/watch?v=xxxxx'"
echo
echo "4. 如需转录:"
echo "   python parallel_transcribe.py --input output/xxx/video.mp4"
echo
echo "5. 生成摘要:"
echo "   python generate_summary.py --transcript output/xxx/transcript.txt"
echo
echo "详细用法请参考 index.md"
echo
