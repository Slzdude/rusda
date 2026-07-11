#!/usr/bin/env python3
"""
rusda 补丁应用工具
生成随机配置，替换占位符，应用补丁到 frida 源码

用法：
    python apply_patches.py <frida源码目录>
    python apply_patches.py /path/to/frida17.15.4
"""

import sys
import json
import random
import string
import subprocess
from pathlib import Path


def random_alpha(length: int) -> str:
    """生成随机纯字母字符串"""
    return ''.join(random.choices(string.ascii_lowercase, k=length))


def generate_config() -> dict:
    """生成随机配置"""
    brand = random_alpha(5)  # frida = 5字符
    prgname = random_alpha(7)  # russell = 7字符

    # 线程名（等长替换）
    thread_gum_js_loop = random_alpha(11)  # gum-js-loop = 11字符
    thread_gmain = random_alpha(5)  # gmain = 5字符
    thread_gdbus = random_alpha(5)  # gdbus = 5字符

    return {
        'brand': brand,
        'prgname': prgname,
        'thread_gum_js_loop': thread_gum_js_loop,
        'thread_gmain': thread_gmain,
        'thread_gdbus': thread_gdbus,
    }


def apply_patch_with_replacements(patch_file: Path, target_dir: Path, config: dict) -> bool:
    """应用补丁，替换占位符"""
    print(f"\n[*] 应用补丁: {patch_file.name}")

    # 读取补丁内容
    content = patch_file.read_text()

    # 替换品牌名占位符
    brand = config['brand']
    content = content.replace('__BRAND__', brand)

    # 替换进程名占位符（7字符，与品牌名不同）
    content = content.replace('__PRGNAME__', config['prgname'])

    # 替换线程名占位符
    content = content.replace('__THREAD_GUM_JS_LOOP__', config['thread_gum_js_loop'])
    content = content.replace('__THREAD_GMAIN__', config['thread_gmain'])
    content = content.replace('__THREAD_GDBUS__', config['thread_gdbus'])

    # 写入临时文件
    tmp_patch = patch_file.with_suffix('.tmp')
    tmp_patch.write_text(content)

    try:
        # 检查补丁是否可以应用
        result = subprocess.run(
            ['git', 'apply', '--check', str(tmp_patch)],
            cwd=target_dir,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"[!] 补丁检查失败: {result.stderr}")
            return False

        # 应用补丁
        result = subprocess.run(
            ['git', 'apply', str(tmp_patch)],
            cwd=target_dir,
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print(f"[✓] 补丁应用成功: {patch_file.name}")
            return True
        else:
            print(f"[!] 补丁应用失败: {result.stderr}")
            return False

    finally:
        # 清理临时文件
        tmp_patch.unlink(missing_ok=True)


def main():
    if len(sys.argv) < 2:
        print("用法: python apply_patches.py <frida源码目录>")
        print("示例: python apply_patches.py /path/to/frida17.15.4")
        sys.exit(1)

    frida_dir = Path(sys.argv[1]).resolve()

    # 检查是否是 git 仓库
    if not (frida_dir / '.git').exists():
        print(f"[!] 错误: {frida_dir} 不是 git 仓库")
        sys.exit(1)

    # 补丁目录
    patch_dir = Path(__file__).parent.parent / 'patches'
    if not patch_dir.exists():
        print(f"[!] 错误: 补丁目录不存在: {patch_dir}")
        sys.exit(1)

    print("=" * 60)
    print("rusda 补丁应用工具")
    print("=" * 60)

    # 生成随机配置
    print("\n[*] 生成随机配置...")
    config = generate_config()

    print(f"\n[*] 本次构建配置:")
    print(f"    品牌名: {config['brand']}")
    print(f"    进程名: {config['prgname']}")
    print(f"    线程名: {config['thread_gum_js_loop']}, {config['thread_gmain']}, {config['thread_gdbus']}")

    # 保存配置到 frida 源码目录
    config_file = frida_dir / 'rusda_config.json'
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"[*] 配置已保存: {config_file}")

    # 应用补丁
    print("\n" + "=" * 60)

    patches = [
        ('superrepo.patch', frida_dir),
        ('frida-core.patch', frida_dir / 'subprojects' / 'frida-core'),
        ('frida-gum.patch', frida_dir / 'subprojects' / 'frida-gum'),
    ]

    success = True
    for patch_name, target_dir in patches:
        patch_file = patch_dir / patch_name
        if not patch_file.exists():
            print(f"[!] 补丁文件不存在: {patch_file}")
            continue

        if not apply_patch_with_replacements(patch_file, target_dir, config):
            success = False
            break

    if success:
        # 安装 compiler 的 npm 依赖
        compiler_dir = frida_dir / 'subprojects' / 'frida-core' / 'src' / 'compiler'
        if (compiler_dir / 'package.json').exists():
            print("\n[*] 安装 compiler npm 依赖...")
            result = subprocess.run(
                ['npm', 'install', '--silent'],
                cwd=compiler_dir,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print("[✓] npm 依赖安装完成")
            else:
                print(f"[!] npm 安装失败: {result.stderr[:200]}")

        print("\n" + "=" * 60)
        print("[✓] 所有补丁应用成功！")
        print(f"\n[*] 下一步:")
        print(f"    cd {frida_dir}")
        print(f"    export ANDROID_NDK_ROOT=/path/to/ndk")
        print(f"    ./tools/build-android-all.sh")
    else:
        print("\n[!] 补丁应用失败，请检查错误信息")
        sys.exit(1)


if __name__ == '__main__':
    main()
