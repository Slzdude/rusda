#!/usr/bin/env python3
"""
frida-server 检测特征扫描脚本

对 frida-core、frida-gum、frida-tools 中的可检测特征进行系统性扫描，
输出特征清单 CSV 供反检测魔改参考。

用法:
  python tools/scan-frida-signatures.py [--source-dir DIR] [--binary-dir DIR] [--output FILE]
"""

import argparse
import csv
import os
import subprocess
import sys
from pathlib import Path

# 预定义特征列表（32 项）: (特征, 类别, 检测方式, 是否已 patched, 建议修改)
SIGNATURES = [
    # 字符串与常量
    ("frida:rpc", "string", "内存扫描 RPC 协议标识", "yes", "rpc.vala → rusda:rpc"),
    ("User-Agent: Frida/", "string", "HTTP 头嗅探", "yes", "socket.vala → Rusda/"),
    ("Server: Frida/", "string", "HTTP 头嗅探", "yes", "socket.vala → Rusda/"),
    ("FridaScriptEngine", "string", "内存 .rodata 匹配", "yes", "topatch.py 反转"),
    ("GLib-GIO", "string", "GObject 类型名", "yes", "topatch.py 反转"),
    ("GDBusProxy", "string", "GObject 类型名", "yes", "topatch.py 反转"),
    ("GumScript", "string", "GObject 类型名", "yes", "topatch.py 反转"),
    ("re.frida.", "string", "D-Bus 对象路径", "yes", "session.vala → re.rusda."),
    ("6769746875622e636f6d2f6672696461", "string", "hex github.com/frida", "yes", "session.vala → rusda"),
    ("frida-generate-certificate", "string", "线程名", "yes", "p2p.vala → rusda-generate-certificate"),
    ("frida-error-quark", "string", "GError 域", "yes", "xpc.vala → rusda-error-quark"),
    ("remote frida-server", "string", "错误消息", "yes", "session.vala → rusda-server"),
    # 符号
    ("frida_agent_main", "symbol", "符号表/内存符号", "yes", "topatch.py → main"),
    ("frida", "symbol", "符号前缀", "partial", "devkit.py frida_prefixes"),
    ("libfrida-agent-raw", "symbol", "链接器 so 列表", "no", "lib/agent meson.build"),
    # 线程名
    ("gum-js-loop", "thread", "/proc/pid/task/*/comm", "yes", "topatch.py → russellloop"),
    ("gmain", "thread", "GLib 默认线程名", "yes", "topatch.py → rmain"),
    ("gdbus", "thread", "GDBus 默认线程名", "yes", "topatch.py → rubus"),
    ("frida-gadget", "thread", "gadget worker 线程", "yes", "gadget-glue.c + topatch"),
    ("frida-gadget-tcp-", "thread", "gadget 监听线程", "yes", "gadget.vala + topatch"),
    ("frida-gadget-unix", "thread", "gadget unix 线程", "yes", "gadget.vala + topatch"),
    ("pool-frida", "thread", "iOS GLib 线程池", "no", "需查 GLib 源码"),
    ("pool-spawner", "thread", "iOS GLib 线程池", "no", "需查 GLib 源码"),
    # 端口
    ("27042", "port", "端口扫描", "no", "socket.vala DEFAULT_CONTROL_PORT"),
    ("27052", "port", "端口扫描", "no", "socket.vala DEFAULT_CLUSTER_PORT"),
    # 路径
    ("/data/local/tmp/frida-", "path", "Android 路径枚举", "no", "injector.vala, linux-host-session.vala"),
    ("/usr/lib/frida/", "path", "iOS 路径检测", "no", "package-server-fruity.sh"),
    ("memfd:frida-agent", "path", "/proc/pid/maps", "yes", "linux.vala → jit-cache"),
    # 二进制/库名
    ("frida-server", "binary", "进程名", "yes", "meson.build → rusda-server"),
    ("frida-inject", "binary", "可执行名", "yes", "meson.build → rusda-inject"),
    ("frida-gadget.so", "binary", "库加载检测", "yes", "meson.build → rusda-gadget.so"),
    ("frida-agent", "binary", "库/资源名", "yes", "meson.build + embed-agent.py"),
    ("frida-helper", "binary", "Android helper", "partial", "re.frida.helper 等"),
    # D-Bus
    ("re.frida.HostSession", "dbus", "D-Bus 对象路径", "yes", "session.vala → re.rusda.HostSession"),
    ("re.frida.Gadget", "dbus", "Gadget 上报 ID", "yes", "gadget.vala + topatch"),
    ("re.frida.server", "dbus", "Android 包名", "yes", "server.vala"),
]


def run_grep(pattern: str, search_dir: Path, glob: str = "*.vala", fixed: bool = True) -> list[tuple[str, int, str]]:
    """在目录中 grep 搜索，返回 [(file, line, line_content), ...]"""
    results = []
    try:
        cmd = [
            "grep", "-rn", "--include=" + glob, "-F" if fixed else "-E", pattern,
            str(search_dir)
        ]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if out.returncode == 0 and out.stdout:
            for line in out.stdout.strip().split("\n"):
                if ":" in line:
                    parts = line.split(":", 2)
                    if len(parts) >= 3:
                        filepath, lineno, content = parts[0], parts[1], parts[2]
                        results.append((filepath, int(lineno), content.strip()))
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return results


def scan_binary(binary_path: Path) -> dict[str, list]:
    """对二进制执行 strings 和 readelf，返回检测到的特征"""
    results = {"strings": [], "symbols": []}
    if not binary_path.exists():
        return results

    try:
        out = subprocess.run(
            ["strings", str(binary_path)],
            capture_output=True, text=True, timeout=60
        )
        if out.returncode == 0:
            frida_lines = [l for l in out.stdout.splitlines() if "frida" in l.lower() or "gum" in l.lower()]
            results["strings"] = frida_lines[:50]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    try:
        out = subprocess.run(
            ["readelf", "-s", str(binary_path)],
            capture_output=True, text=True, timeout=30
        )
        if out.returncode == 0:
            sym_lines = [l for l in out.stdout.splitlines() if "frida" in l.lower()]
            results["symbols"] = sym_lines[:30]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return results


def find_binaries(root: Path) -> list[Path]:
    """查找可能的构建产物"""
    candidates = []
    for pattern in [
        "build*/bin/rusda-server",
        "build*/bin/frida-server",
        "build*/frida-*/bin/*server",
        "dist-android/*",
        "build*/lib/rusda/*/rusda-gadget.so",
        "build*/lib/frida/*/frida-gadget.so",
    ]:
        for p in root.glob(pattern):
            if p.is_file():
                candidates.append(p)
    return candidates


def main():
    parser = argparse.ArgumentParser(description="frida-server 检测特征扫描")
    parser.add_argument("--source-dir", type=Path, default=None, help="源码根目录")
    parser.add_argument("--binary-dir", type=Path, default=None, help="二进制目录（可选）")
    parser.add_argument("--output", "-o", type=Path, default=None, help="输出 CSV 路径")
    parser.add_argument("--skip-source", action="store_true", help="跳过源码扫描")
    parser.add_argument("--skip-binary", action="store_true", help="跳过二进制扫描")
    args = parser.parse_args()

    root = args.source_dir or Path(__file__).resolve().parent.parent
    output_path = args.output or root / "doc" / "frida-signatures.csv"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. 输出预定义特征清单 CSV
    rows = []
    for sig, category, detect_method, patched, suggestion in SIGNATURES:
        rows.append({
            "signature": sig,
            "category": category,
            "detect_method": detect_method,
            "patched": patched,
            "suggestion": suggestion,
            "source_location": "",
            "binary_hits": "",
        })

    # 2. 源码扫描
    if not args.skip_source:
        subprojects = ["frida-core", "frida-gum", "frida-tools"]
        for sig_row in rows:
            locs = []
            for sp in subprojects:
                sp_path = root / "subprojects" / sp
                if not sp_path.exists():
                    continue
                for ext in ["*.vala", "*.c", "*.h", "*.py"]:
                    hits = run_grep(sig_row["signature"], sp_path, ext)
                    for h in hits[:5]:
                        try:
                            rel = Path(h[0]).relative_to(root)
                            locs.append(f"{rel}:{h[1]}")
                        except ValueError:
                            locs.append(f"{h[0]}:{h[1]}")
            if locs:
                sig_row["source_location"] = "; ".join(locs[:10])

    # 3. 二进制扫描（若存在）
    binaries = []
    if not args.skip_binary:
        if args.binary_dir and args.binary_dir.exists():
            binaries = [p for p in args.binary_dir.rglob("*") if p.is_file() and os.access(p, os.R_OK)]
        else:
            binaries = find_binaries(root)

        for bin_path in binaries[:5]:  # 最多扫描 5 个
            bin_results = scan_binary(bin_path)
            for sig_row in rows:
                sig_lower = sig_row["signature"].lower()
                for s in bin_results["strings"]:
                    if sig_lower in s.lower():
                        sig_row["binary_hits"] = (sig_row["binary_hits"] or "") + f"{bin_path.name}: " + s[:60] + "; "
                        break

    # 4. 写入 CSV
    if rows:
        fieldnames = ["signature", "category", "detect_method", "patched", "suggestion", "source_location", "binary_hits"]
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    print(f"Written {len(rows)} signatures to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
