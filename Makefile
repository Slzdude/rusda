# rusda 构建系统
# 用法：make build ARCH=arm64

ARCH ?= arm64
VERSION = 17.15.4
FRIDA_SRC = frida-src
RUSDA_DIR = $(shell pwd)
NDK_ROOT = $(ANDROID_NDK_ROOT)
JOBS = $(shell nproc 2>/dev/null || echo 4)

# 从构建产物中读取品牌名
GET_BRAND = grep -oP "helper_name = '\K[^']*" $(FRIDA_SRC)/subprojects/frida-core/meson.build 2>/dev/null | sed 's/-helper//'

.PHONY: all help reset apply build package clean full-reset quick install-device test

help:
	@echo "rusda 构建系统"
	@echo ""
	@echo "用法:"
	@echo "  make              # 完整构建 arm64"
	@echo "  make ARCH=arm     # 完整构建 arm"
	@echo "  make build        # 只编译（已 apply 后）"
	@echo "  make quick        # 快速重新编译"
	@echo "  make clean        # 清理构建产物"
	@echo "  make full-reset   # 清理 + 还原源码"
	@echo "  make test         # 构建 + 安装到设备 + 测试"
	@echo ""
	@echo "可用架构: arm, arm64, x86, x86_64"

# 还原源码
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
	@rm -f $(FRIDA_SRC)/package-lock.json
	@echo "[✓] 源码已还原"

# 应用补丁 + 安装依赖
apply: reset
	@echo "=== 应用补丁 ==="
	@python3 $(RUSDA_DIR)/tools/apply_patches.py $(RUSDA_DIR)/$(FRIDA_SRC)
	@echo "[✓] 补丁已应用"

# 配置
configure: apply
ifndef ANDROID_NDK_ROOT
	$(error ANDROID_NDK_ROOT 未设置)
endif
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
		make -j$(JOBS) 2>&1 | tail -20 || true
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
	@BRAND=$$($(GET_BRAND)); \
	STAGING=$(FRIDA_SRC)/dist-android/staging-$(ARCH); \
	BITS=$$( [ "$(ARCH)" = "arm" ] || [ "$(ARCH)" = "x86" ] && echo 32 || echo 64 ); \
	for bin in server inject; do \
		f="$$STAGING/bin/$${BRAND}-$$bin"; \
		[ -f "$$f" ] && { echo "  $${BRAND}-$$bin-$(VERSION)-android-$(ARCH).xz"; xz -c -T0 "$$f" > "dist-android/$${BRAND}-$$bin-$(VERSION)-android-$(ARCH).xz"; }; \
	done; \
	GADGET=$$(find "$$STAGING/lib" -path "*/$$BITS/$${BRAND}-gadget.so" 2>/dev/null | head -1); \
	[ -n "$$GADGET" ] && { echo "  $${BRAND}-gadget-$(VERSION)-android-$(ARCH).so.xz"; xz -c -T0 "$$GADGET" > "dist-android/$${BRAND}-gadget-$(VERSION)-android-$(ARCH).so.xz"; }; \
	echo "[✓] 打包完成"; ls -lh dist-android/*.xz 2>/dev/null

# 完整构建
all: package
	@echo ""
	@echo "=== 构建完成 ==="

# 清理构建产物
clean:
	@echo "=== 清理 ==="
	@rm -rf $(FRIDA_SRC)/build-android-*
	@rm -rf $(FRIDA_SRC)/dist-android
	@rm -rf dist-android
	@echo "[✓] 已清理"

# 完全重置
full-reset: clean reset
	@echo "[✓] 完全重置完成"

# 快速编译（跳过还原和补丁）
quick:
ifndef ANDROID_NDK_ROOT
	$(error ANDROID_NDK_ROOT 未设置)
endif
	@echo "=== 快速编译 $(ARCH) ==="
	@cd $(FRIDA_SRC)/build-android-$(ARCH) && \
		export ANDROID_NDK_ROOT=$(NDK_ROOT) && \
		export PATH=$(NDK_ROOT):$$PATH && \
		make -j$(JOBS) 2>&1 | tail -20 || true
	@echo "[✓] 编译完成"

# 安装到设备并测试
test: package
	@echo "=== 安装到设备 ==="
	@BRAND=$$($(GET_BRAND)); \
	SERVER="dist-android/$${BRAND}-server-$(VERSION)-android-$(ARCH).xz"; \
	xz -dk "$$SERVER" -c > /tmp/$${BRAND}-server 2>/dev/null || cp "$(FRIDA_SRC)/dist-android/staging-$(ARCH)/bin/$${BRAND}-server" /tmp/$${BRAND}-server; \
	adb push /tmp/$${BRAND}-server /data/local/tmp/ && \
	adb shell "su -c 'chmod 755 /data/local/tmp/$${BRAND}-server'" && \
	rm -f /tmp/$${BRAND}-server; \
	echo "=== 启动 server ===" ; \
	adb shell "su -c '/data/local/tmp/$${BRAND}-server'" & sleep 3; \
	echo "=== 测试连接 ===" ; \
	frida-ps -U 2>&1 | head -5 || echo "连接失败"; \
	echo ""; \
	echo "启动: adb shell su -c '/data/local/tmp/$${BRAND}-server'"
