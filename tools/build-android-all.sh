#!/bin/bash
# rusda Android 构建脚本
# 支持全架构或指定架构编译
#
# 用法:
#   ./tools/build-android-all.sh                    # 编译全部架构
#   ./tools/build-android-all.sh arm64              # 只编译 arm64
#   ./tools/build-android-all.sh arm arm64          # 编译 arm 和 arm64
#   ./tools/build-android-all.sh --list             # 列出可用架构
#   ./tools/build-android-all.sh --help             # 显示帮助

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_DIR="${SRC_ROOT}/dist-android"

# 可用架构列表
ALL_ARCHS="x86 x86_64 arm arm64"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[*]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[!]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }
log_debug() { echo -e "${BLUE}[i]${NC} $1"; }

# 显示帮助
show_help() {
    cat << EOF
rusda Android 构建脚本

用法:
    $(basename "$0") [选项] [架构...]

选项:
    --help, -h      显示此帮助
    --list, -l      列出可用架构
    --clean, -c     构建前清理输出目录
    --keep, -k      保留构建目录（不清理）

可用架构:
    arm             ARM 32位 (armeabi-v7a)
    arm64           ARM 64位 (arm64-v8a) [推荐]
    x86             x86 32位
    x86_64          x86 64位

示例:
    $(basename "$0")                  # 编译全部架构
    $(basename "$0") arm64            # 只编译 arm64
    $(basename "$0") arm arm64        # 编译 arm 和 arm64
    $(basename "$0") --clean arm64    # 清理后编译 arm64

环境变量:
    ANDROID_NDK_ROOT    NDK 路径 (必须)

EOF
    exit 0
}

# 列出可用架构
list_archs() {
    echo "可用架构:"
    for arch in $ALL_ARCHS; do
        case "$arch" in
            arm)    echo "  arm     - ARM 32位 (armeabi-v7a)" ;;
            arm64)  echo "  arm64   - ARM 64位 (arm64-v8a)" ;;
            x86)    echo "  x86     - x86 32位" ;;
            x86_64) echo "  x86_64  - x86 64位" ;;
        esac
    done
    exit 0
}

# 解析参数
ARCHS=()
CLEAN_OUTPUT=false
KEEP_BUILD=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            show_help
            ;;
        --list|-l)
            list_archs
            ;;
        --clean|-c)
            CLEAN_OUTPUT=true
            shift
            ;;
        --keep|-k)
            KEEP_BUILD=true
            shift
            ;;
        arm|arm64|x86|x86_64)
            ARCHS+=("$1")
            shift
            ;;
        *)
            log_error "未知参数: $1"
            echo "使用 --help 查看帮助"
            exit 1
            ;;
    esac
done

# 默认编译全部架构
if [ ${#ARCHS[@]} -eq 0 ]; then
    ARCHS=($ALL_ARCHS)
fi

# 版本号自动推导
VERSION_FALLBACK="17.15.4"
VERSION=""
if [ -f "${SRC_ROOT}/releng/frida_version.py" ]; then
    VERSION="$(python3 "${SRC_ROOT}/releng/frida_version.py" 2>/dev/null \
                | grep -oE '[0-9]+\.[0-9]+\.[0-9]+(-dev\.[0-9]+)?' | head -1)"
fi
VERSION="${VERSION:-$VERSION_FALLBACK}"
log_info "打包版本号: ${VERSION}"

# 检查 NDK
if [ -z "$ANDROID_NDK_ROOT" ]; then
    log_error "请设置 ANDROID_NDK_ROOT 环境变量"
    echo "  export ANDROID_NDK_ROOT=/path/to/ndk-r29"
    exit 1
fi

# 检查 NDK 版本
NDK_VERSION=$(cat "$ANDROID_NDK_ROOT/source.properties" 2>/dev/null | grep Pkg.Revision | cut -d'=' -f2 | tr -d ' ')
if [[ ! "$NDK_VERSION" =~ ^29\. ]]; then
    log_warn "NDK 版本 $NDK_VERSION 可能不兼容，建议使用 r29"
fi

# 检查依赖
log_info "检查依赖..."
command -v python3 >/dev/null || { log_error "缺少 python3"; exit 1; }
command -v node >/dev/null || { log_error "缺少 node"; exit 1; }
command -v npm >/dev/null || { log_error "缺少 npm"; exit 1; }

# 检查并安装 Python 依赖
python3 -c "import lief" 2>/dev/null || {
    log_warn "缺少 lief，正在安装..."
    pip3 install lief
}

# 检查并安装 npm 依赖（compiler 需要）
COMPILER_DIR="${SRC_ROOT}/subprojects/frida-core/src/compiler"
if [ -f "${COMPILER_DIR}/package.json" ] && [ ! -d "${COMPILER_DIR}/node_modules" ]; then
    log_info "安装 compiler npm 依赖..."
    (cd "${COMPILER_DIR}" && npm install --silent 2>&1 | tail -3)
fi

cd "$SRC_ROOT"

# 清理输出目录
if [ "$CLEAN_OUTPUT" = true ]; then
    log_info "清理输出目录..."
    rm -rf "$OUTPUT_DIR"
fi
mkdir -p "$OUTPUT_DIR"

# 单架构构建
build_arch() {
    local arch=$1
    local build_dir="${SRC_ROOT}/build-android-${arch}"
    local prefix="${OUTPUT_DIR}/staging-${arch}"

    log_info "[$arch] 开始配置..."

    # 清理构建目录（除非指定 --keep）
    if [ "$KEEP_BUILD" = false ]; then
        rm -rf "$build_dir"
    fi
    mkdir -p "$build_dir"
    cd "$build_dir"

    # 配置
    if ! ../configure \
        --prefix="$prefix" \
        --host="android-${arch}" \
        --enable-server \
        --enable-gadget \
        --enable-inject \
        --enable-compiler \
        2>&1 | tail -5; then
        log_error "[$arch] 配置失败"
        return 1
    fi

    log_info "[$arch] 开始编译..."
    if ! make -j$(nproc) 2>&1 | tail -10; then
        log_error "[$arch] 编译失败"
        return 1
    fi

    log_info "[$arch] 安装..."
    make install 2>&1 | tail -3

    cd "$SRC_ROOT"
    log_info "[$arch] 完成"
    return 0
}

# ELF 架构校验
elf_machine_for_arch() {
    case "$1" in
        arm)     echo "ARM" ;;
        arm64)   echo "AArch64" ;;
        x86)     echo "Intel 80386" ;;
        x86_64)  echo "X86-64" ;;
    esac
}

assert_elf_arch() {
    local file=$1 arch=$2
    local expect="$(elf_machine_for_arch "$arch")"
    if ! command -v readelf >/dev/null 2>&1; then
        log_warn "未找到 readelf，跳过架构校验"
        return 0
    fi
    local machine="$(readelf -h "$file" 2>/dev/null | sed -n 's/.*Machine:[[:space:]]*//p')"
    if [[ "$machine" != *"$expect"* ]]; then
        log_error "$(basename "$file") 架构不符: 期望 '$expect'，实际 '$machine'"
        return 1
    fi
    return 0
}

# 获取品牌名
get_brand_name() {
    local brand=$(grep -oP "helper_name = '\K[^']*" "${SRC_ROOT}/subprojects/frida-core/meson.build" 2>/dev/null | sed 's/-helper//')
    echo "${brand:-rusda}"
}

BRAND=$(get_brand_name)
log_info "品牌名: $BRAND"
log_info "编译架构: ${ARCHS[*]}"

# 串行编译指定架构
log_info ""
log_info "=== 开始构建 ==="
FAILED_ARCHS=()

for arch in "${ARCHS[@]}"; do
    if ! build_arch "$arch"; then
        FAILED_ARCHS+=("$arch")
        log_error "[$arch] 构建失败，继续..."
    fi
done

# 打包
log_info ""
log_info "=== 打包产物 ==="

for arch in "${ARCHS[@]}"; do
    staging="${OUTPUT_DIR}/staging-${arch}"

    # server
    if [ -f "$staging/bin/${BRAND}-server" ]; then
        assert_elf_arch "$staging/bin/${BRAND}-server" "$arch" || continue
        log_info "  ${BRAND}-server-${VERSION}-android-${arch}.xz"
        xz -c -T0 "$staging/bin/${BRAND}-server" > "${OUTPUT_DIR}/${BRAND}-server-${VERSION}-android-${arch}.xz"
    fi

    # inject
    if [ -f "$staging/bin/${BRAND}-inject" ]; then
        assert_elf_arch "$staging/bin/${BRAND}-inject" "$arch" || continue
        log_info "  ${BRAND}-inject-${VERSION}-android-${arch}.xz"
        xz -c -T0 "$staging/bin/${BRAND}-inject" > "${OUTPUT_DIR}/${BRAND}-inject-${VERSION}-android-${arch}.xz"
    fi

    # gadget（按位宽选择）
    bits=$([ "$arch" = "arm" ] || [ "$arch" = "x86" ] && echo 32 || echo 64)
    gadget="$(find "$staging/lib" -path "*/${bits}/${BRAND}-gadget.so" 2>/dev/null | head -1)"
    if [ -n "$gadget" ] && [ -f "$gadget" ]; then
        assert_elf_arch "$gadget" "$arch" || continue
        log_info "  ${BRAND}-gadget-${VERSION}-android-${arch}.so.xz"
        xz -c -T0 "$gadget" > "${OUTPUT_DIR}/${BRAND}-gadget-${VERSION}-android-${arch}.so.xz"
    fi

    # compiler
    compiler="$(find "$staging/lib" -name "*compiler*.so" -o -name "*compiler*.dll" 2>/dev/null | head -1)"
    if [ -n "$compiler" ] && [ -f "$compiler" ]; then
        assert_elf_arch "$compiler" "$arch" || continue
        log_info "  ${BRAND}-compiler-${VERSION}-android-${arch}.so.xz"
        xz -c -T0 "$compiler" > "${OUTPUT_DIR}/${BRAND}-compiler-${VERSION}-android-${arch}.so.xz"
    fi
done

# 清理 staging
rm -rf "${OUTPUT_DIR}"/staging-*

# 结果汇总
log_info ""
log_info "=== 构建完成 ==="
log_info "输出目录: $OUTPUT_DIR"
ls -lh "$OUTPUT_DIR"/*.xz 2>/dev/null || true

if [ ${#FAILED_ARCHS[@]} -gt 0 ]; then
    log_warn "以下架构构建失败: ${FAILED_ARCHS[*]}"
    exit 1
fi
