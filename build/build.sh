# 清理之前的构建
rm -rf build dist
rm -rf temp_build

# 安装必要工具
# brew install create-dmg imagemagick

# 检查并安装 pyinstaller
if ! pip show pyinstaller > /dev/null 2>&1; then
    echo "正在安装 pyinstaller..."
    pip install pyinstaller certifi
fi


# 获取 Python 证书路径
CERT_PATH=$(python3 -c "import certifi; print(certifi.where())")

# 打包命令
pyinstaller  \
    --workpath temp_build \
    --distpath dist \
    --clean \
    --onefile \
    --noconsole \
    --name "Quick" \
    --icon tb.icns \
    --add-data "${CERT_PATH}:certifi" \
    --add-data "../quick_replies.db:." \
    --paths ".." \
    ../main.py


# 打包完成后清理临时文件
rm -rf temp_build

# 创建输出目录
mkdir -p output

# 创建 DMG
create-dmg \
    --volname "Quick" \
    --volicon "tb.icns" \
    --window-pos 200 120 \
    --window-size 480 200 \
    --icon-size 128 \
    --icon "Quick" 120 40 \
    --hide-extension "Quick" \
    --app-drop-link 360 40 \
    --format UDBZ \
    "output/Quick.dmg" \
    "dist/"




# 清理临时文件
rm -rf dist