#!/bin/bash

# 斐波那契金字塔建仓系统启动脚本

echo "======================================"
echo "  斐波那契金字塔建仓量化交易系统"
echo "======================================"
echo ""

# 检查Python版本
echo "检查Python环境..."
python3 --version

if [ $? -ne 0 ]; then
    echo "错误: 未找到Python3，请先安装Python 3.8+"
    exit 1
fi

# 检查是否在项目根目录
if [ ! -f "requirements.txt" ]; then
    echo "错误: 请在项目根目录运行此脚本"
    exit 1
fi

# 检查是否已安装依赖
echo ""
echo "检查依赖..."

if ! python3 -c "import flask" 2>/dev/null; then
    echo "依赖未安装，正在安装..."
    pip3 install -r requirements.txt --break-system-packages

    if [ $? -ne 0 ]; then
        echo "错误: 依赖安装失败"
        exit 1
    fi
    echo "依赖安装完成！"
else
    echo "依赖已安装"
fi

# 启动服务
echo ""
echo "======================================"
echo "正在启动服务..."
echo "======================================"
echo ""
echo "访问地址: http://localhost:5000"
echo "按 Ctrl+C 停止服务"
echo ""

cd backend && python3 app.py
