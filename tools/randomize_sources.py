#!/usr/bin/env python3
"""
随机化已打补丁的 frida 源码
在应用原始补丁后运行，将硬编码的 rusda/russell 替换为随机值
"""

import sys
import json
import random
import string
import re
from pathlib import Path
from typing import Dict, List, Tuple


def random_alpha(length: int) -> str:
    """生成随机纯字母字符串"""
    return ''.join(random.choices(string.ascii_lowercase, k=length))


def random_readable(length: int) -> str:
    """生成可读的随机字符串"""
    consonants = 'bcdfghjklmnpqrstvwxyz'
    vowels = 'aeiou'
    result = []
    for i in range(length):
        if i % 2 == 0:
            result.append(random.choice(consonants))
        else:
            result.append(random.choice(vowels))
    return ''.join(result)


def xor_encode(text: str, key: int = 0x55) -> str:
    """将字符串编码为 XOR hex"""
    return ''.join(f'{ord(c) ^ key:02x}' for c in text)


def generate_random_config() -> Dict:
    """生成随机配置"""
    brand = random_alpha(5)  # rusda → 5字母
    prgname = random_readable(7)  # russell → 7字母

    return {
        'brand': brand,
        'prgname': prgname,
        'thread_replacements': [
            # (原始值, 新值, 文件模式)
            ('russellloop', random_alpha(11), '*.patch'),
            ('rmain', random_alpha(5), '*.patch'),
            ('rubus', random_alpha(5), '*.patch'),
        ],
        'xor_key': 0x55,
    }


def replace_in_file(file_path: Path, replacements: List[Tuple[str, str]]) -> int:
    """在文件中执行替换，返回替换次数"""
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        # 跳过二进制文件或无法读取的文件
        return 0

    original_content = content
    count = 0

    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)

    # 计算替换次数
    for old, new in replacements:
        count += original_content.count(old)

    if content != original_content:
        file_path.write_text(content, encoding='utf-8')

    return count


def randomize_frida_core(src_dir: Path, config: Dict):
    """随机化 frida-core 源码"""
    print("[*] 随机化 frida-core...")

    brand = config['brand']
    prgname = config['prgname']

    # 基本替换规则
    replacements = [
        # 品牌名 (rusda → random)
        ('rusda', brand),
        ('RUSDA', brand.upper()),

        # 进程名 (russell → random)
        ('russell', prgname),

        # 服务目录
        (f're.{brand}.server', f're.{brand}.server'),  # 已经是随机的
        (f're.{brand}.Inject', f're.{brand}.Inject'),
        (f're.{brand}.Server', f're.{brand}.Server'),
        (f're.{brand}.helper', f're.{brand}.helper'),
    ]

    # 需要处理的文件模式
    file_patterns = [
        '*.vala',
        '*.c',
        '*.h',
        '*.py',
        'meson.build',
    ]

    total_replacements = 0
    for pattern in file_patterns:
        for file_path in src_dir.rglob(pattern):
            if '.git' in str(file_path):
                continue
            count = replace_in_file(file_path, replacements)
            if count > 0:
                total_replacements += count
                print(f"  [✓] {file_path.relative_to(src_dir)} ({count} 处)")

    print(f"  [*] 总计替换: {total_replacements} 处")


def randomize_obfuscate_vala(src_dir: Path, config: Dict):
    """随机化 obfuscate.vala 中的 XOR 密文"""
    print("[*] 随机化 XOR 混淆字符串...")

    brand = config['brand']
    prgname = config['prgname']
    key = config['xor_key']

    # 需要重新编码的字符串
    strings_to_encode = {
        # 线程名
        'frida-eternal-agent': random_alpha(20),
        'frida-agent-emulated': random_alpha(21),
        'frida-generate-certificate': random_alpha(28),
        'frida-gadget-tcp-': random_alpha(18),
        'frida-gadget-unix': random_alpha(18),

        # RPC 标识
        'frida:rpc': f'{brand}:rpc',

        # 错误标识
        'frida-error-quark': f'{brand}-error-quark',
    }

    # 生成新的 XOR 密文
    xor_replacements = []
    for original, replacement in strings_to_encode.items():
        encoded = xor_encode(replacement, key)
        # 在源码中查找旧的密文并替换
        # 这需要读取当前的 obfuscate.vala 来找到旧的 hex 字符串
        print(f"  [*] {original} → {replacement} (hex: {encoded})")

    # 修改 agent.vala, gadget.vala, p2p.vala, rpc.vala, xpc.vala 中的 XOR 调用
    # 这些文件中的 Obfuscate.decode_hex_xor("...") 需要更新密文

    vala_files = [
        'lib/agent/agent.vala',
        'lib/gadget/gadget.vala',
        'lib/base/p2p.vala',
        'lib/base/rpc.vala',
        'lib/base/xpc.vala',
    ]

    for vala_file in vala_files:
        file_path = src_dir / vala_file
        if not file_path.exists():
            continue

        content = file_path.read_text()

        # 替换 XOR 密文
        for original, replacement in strings_to_encode.items():
            old_encoded = xor_encode(original, key)
            new_encoded = xor_encode(replacement, key)
            content = content.replace(old_encoded, new_encoded)

        file_path.write_text(content)
        print(f"  [✓] {vala_file}")


def update_topatch_py(src_dir: Path, config: Dict):
    """更新 topatch.py 中的替换规则"""
    print("[*] 更新 topatch.py...")

    topatch_file = src_dir / 'src' / 'topatch.py'
    if not topatch_file.exists():
        print("  [!] topatch.py 不存在")
        return

    content = topatch_file.read_text()

    # 替换线程名
    thread_replacements = {
        'russellloop': random_alpha(11),
        'rmain': random_alpha(5),
        'rubus': random_alpha(5),
    }

    for old, new in thread_replacements.items():
        content = content.replace(old, new)

    # 替换品牌名
    content = content.replace('rusda', config['brand'])

    topatch_file.write_text(content)
    print("  [✓] topatch.py 已更新")


def main():
    if len(sys.argv) < 2:
        print("用法: python randomize_sources.py <frida源码目录>")
        print("示例: python randomize_sources.py /path/to/frida17.15.4")
        print("\n注意: 请先应用原始补丁，再运行此脚本")
        sys.exit(1)

    src_dir = Path(sys.argv[1]).resolve()
    if not (src_dir / 'subprojects' / 'frida-core').exists():
        print(f"[!] 错误: {src_dir} 不是 frida 源码目录")
        sys.exit(1)

    print("=" * 60)
    print("rusda 源码随机化工具")
    print("=" * 60)

    # 生成随机配置
    print("\n[*] 生成随机配置...")
    config = generate_random_config()

    print(f"\n[*] 本次构建配置:")
    print(f"    品牌名: {config['brand']}")
    print(f"    进程名: {config['prgname']}")

    # 保存配置
    config_file = src_dir / 'rusda_config.json'
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"[*] 配置已保存: {config_file}")

    # 执行随机化
    print("\n" + "=" * 60)
    randomize_frida_core(src_dir / 'subprojects' / 'frida-core', config)
    randomize_obfuscate_vala(src_dir / 'subprojects' / 'frida-core', config)
    update_topatch_py(src_dir / 'subprojects' / 'frida-core', config)

    print("\n" + "=" * 60)
    print("[✓] 随机化完成！")
    print(f"\n[*] 下一步:")
    print(f"    cd {src_dir}")
    print(f"    export ANDROID_NDK_ROOT=/path/to/ndk")
    print(f"    ./tools/build-android-all.sh")


if __name__ == '__main__':
    main()
