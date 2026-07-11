# rusda 构建系统
# 用法：make build ARCH=arm64

# 默认架构
ARCH ?= arm64

# 版本号（从 frida 源码推导）
VERSION = 17.15.4

# 目录
FRIDA_SRC = frida-src
RUSDA_DIR = $(shell pwd)
NDK_ROOT = $(ANDROID_NDK_ROOT)

# 品牌名（从构建产物中读取）
BRAND = $(shell grep -oP "helper_name = '\K[^']*" $(FRIDA_SRC)/subprojects/frida-core/meson.build 2>/dev/null | sed 's/-helper//' || echo "rusda")

.PHONY: all clean reset apply build package help

# 默认目标
all: build

# 显示帮助
help:
	@echo "rusda 构建系统"
	@echo ""
	@echo "用法:"
	@echo "  make build          # 编译 $(ARCH) 架构（默认）"
	@echo "  make build ARCH=arm64  # 编译指定架构"
	@echo "  make clean          # 清理构建产物"
	@echo "  make reset          # 还原源码到干净状态"
	@echo "  make apply          # 只应用补丁"
	@echo "  make package        # 打包产物"
	@echo "  make all            # 完整构建（reset + apply + build + package）"
	@echo ""
	@echo "可用架构: arm, arm64, x86, x86_64"

# 检查 NDK
check-ndk:
ifndef ANDROID_NDK_ROOT
	$(error ANDROID_NDK_ROOT 未设置，请设置 NDK 路径)
endif

# 还原源码到干净状态
reset:
	@echo "=== 还原源码 ==="
	@cd $(FRIDA_SRC) && git checkout . 2>/dev/null || true
	@cd $(FRIDA_SRC)/subprojects/frida-core && git checkout . 2>/dev/null || true
	@cd $(FRIDA_SRC)/subprojects/frida-gum && git checkout . 2>/dev/null || true
	@rm -f $(FRIDA_SRC)/tools/build-android-all.sh
	@rm -f $(FRIDA_SRC)/rusda_config.json
	@rm -f $(FRIDA_SRC)/subprojects/frida-core/lib/base/obfuscate.vala
	@rm -f $(FRIDA_SRC)/subprojects/frida-core/src/topatch.py
	@rm -rf $(FRIDA_SRC)/subprojects/frida-core/home
	@echo "[✓] 源码已还原"

# 应用补丁
apply: reset
	@echo "=== 应用补丁 ==="
	@python3 $(RUSDA_DIR)/tools/apply_patches.py $(RUSDA_DIR)/$(FRIDA_SRC)
	@echo "[✓] 补丁已应用"

# 安装依赖
deps: apply
	@echo "=== 安装依赖 ==="
	@cd $(FRIDA_SRC)/subprojects/frida-core/src/compiler && npm install --silent 2>/dev/null || true
	@echo "[✓] 依赖已安装"

# 配置
configure: deps check-ndk
	@echo "=== 配置 $(ARCH) ==="
	@mkdir -p $(FRIDA_SRC)/build-android-$(ARCH)
	@cd $(FRIDA_SRC)/build-android-$(ARCH) && \
		export ANDROID_NDK_ROOT=$(NDK_ROOT) && \
		export PATH=$(NDK_ROOT):$$PATH && \
		../configure \
			--prefix=$(shell pwd)/$(FRIDA_SRC)/dist-android/staging-$(ARCH) \
			--host=android-$(ARCH) \
			--enable-server \
			--enable-gadget \
			--enable-inject
	@echo "[✓] 配置完成"

# 编译
build: configure
	@echo "=== 编译 $(ARCH) ==="
	@cd $(FRIDA_SRC)/build-android-$(ARCH) && \
		export ANDROID_NDK_ROOT=$(NDK_ROOT) && \
		export PATH=$(NDK_ROOT):$$PATH && \
		make -j$$(nproc) 2>&1 | tail -20 || true
	@echo "[✓] 编译完成"

# 安装
install: build
	@echo "=== 安装 ==="
	@cd $(FRIDA_SRC)/build-android-$(ARCH) && make install 2>&1 | tail -5
	@echo "[✓] 安装完成"

# 打包
package: install
	@echo "=== 打包 ==="
	@mkdir -p dist-android
	@BRAND=$$(grep -oP "helper_name = '\K[^']*" $(FRIDA_SRC)/subprojects/frida-core/meson.build | sed 's/-helper//'); \
	if [ -f "$(FRIDA_SRC)/dist-android/staging-$(ARCH)/bin/$${BRAND}-server" ]; then \
		echo "  $${BRAND}-server-$(VERSION)-android-$(ARCH).xz"; \
		xz -c -T0 "$(FRIDA_SRC)/dist-android/staging-$(ARCH)/bin/$${BRAND}-server" > "dist-android/$${BRAND}-server-$(VERSION)-android-$(ARCH).xz"; \
	fi
	@BRAND=$$(grep -oP "helper_name = '\K[^']*" $(FRIDA_SRC)/subprojects/frida-core/meson.build | sed 's/-helper//'); \
	if [ -f "$(FRIDA_SRC)/dist-android/staging-$(ARCH)/bin/$${BRAND}-inject" ]; then \
		echo "  $${BRAND}-inject-$(VERSION)-android-$(ARCH).xz"; \
		xz -c -T0 "$(FRIDA_SRC)/dist-android/staging-$(ARCH)/bin/$${BRAND}-inject" > "dist-android/$${BRAND}-inject-$(VERSION)-android-$(ARCH).xz"; \
	fi
	@BRAND=$$(grep -oP "helper_name = '\K[^']*" $(FRIDA_SRC)/subprojects/frida-core/meson.build | sed 's/-helper//'); \
	BITS=$$( [ "$(ARCH)" = "arm" ] || [ "$(ARCH)" = "x86" ] && echo 32 || echo 64 ); \
	GADGET=$$(find "$(FRIDA_SRC)/dist-android/staging-$(ARCH)/lib" -path "*/$${BITS}/$${BRAND}-gadget.so" 2>/dev/null | head -1); \
	if [ -n "$${GADGET}" ] && [ -f "$${GADGET}" ]; then \
		echo "  $${BRAND}-gadget-$(VERSION)-android-$(ARCH).so.xz"; \
		xz -c -T0 "$${GADGET}" > "dist-android/$${BRAND}-gadget-$(VERSION)-android-$(ARCH).so.xz"; \
	fi
	@echo "[✓] 打包完成"
	@ls -lh dist-android/*.xz 2>/dev/null || true

# 完整构建
all: reset apply deps configure build install package
	@echo ""
	@echo "=== 构建完成 ==="

# 清理
clean:
	@echo "=== 清理 ==="
	@rm -rf $(FRIDA_SRC)/build-android-*
	@rm -rf $(FRIDA_SRC)/dist-android
	@rm -rf dist-android
	@echo "[✓] 已清理"

# 完全重置（包括还原源码）
full-reset: clean reset
	@echo "[✓] 完全重置完成"

# 快速编译（跳过还原和补丁，用于代码修改后重新编译）
quick:
	@echo "=== 快速编译 $(ARCH) ==="
	@cd $(FRIDA_SRC)/build-android-$(ARCH) && \
		export ANDROID_NDK_ROOT=$(NDK_ROOT) && \
		export PATH=$(NDK_ROOT):$$PATH && \
		make -j$$(nproc) 2>&1 | tail -20 || true
	@echo "[✓] 编译完成"

# 安装到手机
install-device: package
	@echo "=== 安装到设备 ==="
	@BRAND=$$(grep -oP "helper_name = '\K[^']*" $(FRIDA_SRC)/subprojects/frida-core/meson.build | sed 's/-helper//'); \
	adb push "dist-android/$${BRAND}-server-$(VERSION)-android-$(ARCH).xz" /data/local/tmp/ 2>/dev/null || \
	adb push "$(FRIDA_SRC)/dist-android/staging-$(ARCH)/bin/$${BRAND}-server" /data/local/tmp/$${BRAND}-server
	@BRAND=$$(grep -oP "helper_name = '\K[^']*" $(FRIDA_SRC)/subprojects/frida-core/meson.build | sed 's/-helper//'); \
	adb shell "su -c 'chmod 755 /data/local/tmp/$${BRAND}-server'" 2>/dev/null || true
	@echo "[✓] 已安装到设备"
	@echo "启动: adb shell su -c '/data/local/tmp/$${BRAND}-server'"
