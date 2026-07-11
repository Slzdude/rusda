#!/usr/bin/env python3
"""
基于干净的 frida 17.15.4 源码生成 rusda 补丁
运行方式：在 frida-src/subprojects/frida-core 目录下执行
"""

import subprocess
import sys
from pathlib import Path


def run(cmd, cwd=None):
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[!] 命令失败: {cmd}")
        print(f"    {result.stderr}")
    return result


def sed_replace(filepath, old, new):
    """精确替换文件内容"""
    content = Path(filepath).read_text()
    if old not in content:
        print(f"  [!] 未找到: {old[:50]}... in {filepath}")
        return False
    content = content.replace(old, new)
    Path(filepath).write_text(content)
    return True


def apply_changes(frida_core_dir):
    """应用所有 rusda 改动"""
    d = Path(frida_core_dir)

    print("=== 应用 rusda 改动 ===\n")

    # 1. compat/build.py - 产物名替换
    print("[1] compat/build.py")
    f = d / "compat/build.py"
    c = f.read_text()
    # helper/agent/gadget/server 输出名
    c = c.replace('name=f"frida-helper-{other_arch}"', 'name=f"__BRAND__-helper-{other_arch}"')
    c = c.replace('name=f"frida-agent-{other_arch}.dylib"', 'name=f"__BRAND__-agent-{other_arch}.dylib"')
    c = c.replace('name=f"frida-gadget-{other_arch}.dylib"', 'name=f"__BRAND__-gadget-{other_arch}.dylib"')
    c = c.replace('name=f"frida-server-{other_arch}"', 'name=f"__BRAND__-server-{other_arch}"')
    c = c.replace('name="frida-agent-arm.so"', 'name="__BRAND__-agent-arm.so"')
    c = c.replace('name="frida-agent-arm64.so"', 'name="__BRAND__-agent-arm64.so"')
    # 文件路径
    c = c.replace('Path("src") / "frida-helper.exe"', 'Path("src") / "__BRAND__-helper.exe"')
    c = c.replace('Path("src") / "frida-helper"', 'Path("src") / "__BRAND__-helper"')
    c = c.replace('Path("lib") / "agent" / "frida-agent.dll"', 'Path("lib") / "agent" / "__BRAND__-agent.dll"')
    c = c.replace('Path("lib") / "agent" / "frida-agent.dylib"', 'Path("lib") / "agent" / "__BRAND__-agent.dylib"')
    c = c.replace('Path("lib") / "agent" / "frida-agent.so"', 'Path("lib") / "agent" / "__BRAND__-agent.so"')
    c = c.replace('Path("lib") / "gadget" / "frida-gadget.dll"', 'Path("lib") / "gadget" / "__BRAND__-gadget.dll"')
    c = c.replace('Path("lib") / "gadget" / "frida-gadget.dylib"', 'Path("lib") / "gadget" / "__BRAND__-gadget.dylib"')
    c = c.replace('Path("lib") / "gadget" / "frida-gadget.so"', 'Path("lib") / "gadget" / "__BRAND__-gadget.so"')
    c = c.replace('Path("server") / "frida-server"', 'Path("server") / "__BRAND__-server"')
    f.write_text(c)
    print("  ✓ 产物名和路径替换完成")

    # 2. inject/meson.build
    print("[2] inject/meson.build")
    f = d / "inject/meson.build"
    c = f.read_text()
    c = c.replace("  output: 'frida-inject' + exe_suffix,", "  output: '__BRAND__-inject' + exe_suffix,")
    c = c.replace("  command: post_process + ['executable', 're.frida.Inject', '@INPUT1@'],",
                  "  command: post_process + ['executable', 're.__BRAND__.Inject', '@INPUT1@'],")
    f.write_text(c)
    print("  ✓ 注入工具名替换完成")

    # 3. meson.build - 主构建配置
    print("[3] meson.build")
    f = d / "meson.build"
    c = f.read_text()
    c = c.replace("helper_name = 'frida-helper' + exe_suffix", "helper_name = '__BRAND__-helper' + exe_suffix")
    c = c.replace("agent_name = 'frida-agent' + shlib_suffix", "agent_name = '__BRAND__-agent' + shlib_suffix")
    c = c.replace("gadget_name = 'frida-gadget' + shlib_suffix", "gadget_name = '__BRAND__-gadget' + shlib_suffix")
    c = c.replace("frida_libdir_name = f'frida-@api_version@'", "frida_libdir_name = f'__BRAND__-@api_version@'")
    f.write_text(c)
    print("  ✓ 主构建配置替换完成")

    # 4. server/meson.build
    print("[4] server/meson.build")
    f = d / "server/meson.build"
    c = f.read_text()
    c = c.replace("server_name = 'frida-server' + exe_suffix", "server_name = '__BRAND__-server' + exe_suffix")
    c = c.replace("  command: post_process + ['executable', 're.frida.Server', '@INPUT1@'],",
                  "  command: post_process + ['executable', 're.__BRAND__.Server', '@INPUT1@'],")
    f.write_text(c)
    print("  ✓ 服务构建配置替换完成")

    # 5. server/server.vala - 服务目录
    print("[5] server/server.vala")
    f = d / "server/server.vala"
    c = f.read_text()
    c = c.replace('private const string DEFAULT_DIRECTORY = "re.frida.server";',
                  'private const string DEFAULT_DIRECTORY = "re.__BRAND__.server";')
    f.write_text(c)
    print("  ✓ 服务目录替换完成")

    # 6. src/agent-container.vala - 入口符号
    print("[6] src/agent-container.vala")
    f = d / "src/agent-container.vala"
    c = f.read_text()
    c = c.replace('container.module.symbol ("frida_agent_main", out main_func_symbol)',
                  'container.module.symbol ("main", out main_func_symbol)')
    f.write_text(c)
    print("  ✓ 入口符号替换完成")

    # 7. src/darwin/darwin-host-session.vala
    print("[7] src/darwin/darwin-host-session.vala")
    f = d / "src/darwin/darwin-host-session.vala"
    c = f.read_text()
    c = c.replace('unowned string entrypoint = "frida_agent_main";',
                  'unowned string entrypoint = "main";')
    f.write_text(c)
    print("  ✓ Darwin 入口符号替换完成")

    # 8. src/linux/linux-host-session.vala
    print("[8] src/linux/linux-host-session.vala")
    f = d / "src/linux/linux-host-session.vala"
    c = f.read_text()
    c = c.replace('PathTemplate ("frida-agent-<arch>.so")', 'PathTemplate ("__BRAND__-agent-<arch>.so")')
    c = c.replace('new AgentResource ("frida-agent-arm.so"', 'new AgentResource ("__BRAND__-agent-arm.so"')
    c = c.replace('new AgentResource ("frida-agent-arm64.so"', 'new AgentResource ("__BRAND__-agent-arm64.so"')
    c = c.replace('string entrypoint = "frida_agent_main";', 'string entrypoint = "main";')
    c = c.replace('name = "frida-agent-arm.so";', 'name = "__BRAND__-agent-arm.so";')
    c = c.replace('name = "frida-agent-arm64.so";', 'name = "__BRAND__-agent-arm64.so";')
    f.write_text(c)
    print("  ✓ Linux 入口符号和 agent 名替换完成")

    # 9. src/freebsd/freebsd-host-session.vala
    print("[9] src/freebsd/freebsd-host-session.vala")
    f = d / "src/freebsd/freebsd-host-session.vala"
    c = f.read_text()
    c = c.replace('"frida_agent_main"', '"main"')
    f.write_text(c)
    print("  ✓ FreeBSD 入口符号替换完成")

    # 10. src/qnx/qnx-host-session.vala
    print("[10] src/qnx/qnx-host-session.vala")
    f = d / "src/qnx/qnx-host-session.vala"
    c = f.read_text()
    c = c.replace('"frida_agent_main"', '"main"')
    f.write_text(c)
    print("  ✓ QNX 入口符号替换完成")

    # 11. src/windows/windows-host-session.vala
    print("[11] src/windows/windows-host-session.vala")
    f = d / "src/windows/windows-host-session.vala"
    c = f.read_text()
    c = c.replace('"frida_agent_main"', '"main"')
    f.write_text(c)
    print("  ✓ Windows 入口符号替换完成")

    # 12. src/droidy/droidy-host-session.vala - nice-name
    print("[12] src/droidy/droidy-host-session.vala")
    f = d / "src/droidy/droidy-host-session.vala"
    c = f.read_text()
    c = c.replace('--nice-name=re.frida.helper', '--nice-name=re.__BRAND__.helper')
    f.write_text(c)
    print("  ✓ Droidy nice-name 替换完成")

    # 13. src/droidy/droidy-client.vala - 静默错误
    print("[13] src/droidy/droidy-client.vala")
    f = d / "src/droidy/droidy-client.vala"
    c = f.read_text()
    c = c.replace('throw new Error.PROTOCOL ("Unexpected command");',
                  'break; // throw new Error.PROTOCOL ("Unexpected command");')
    f.write_text(c)
    print("  ✓ Droidy 错误静默完成")

    # 14. src/frida-glue.c - 进程名和线程名
    print("[14] src/frida-glue.c")
    f = d / "src/frida-glue.c"
    c = f.read_text()
    # 在 g_io_module_openssl_register 后面加 prgname
    c = c.replace(
        '#endif\n\n    if (runtime == FRIDA_RUNTIME_OTHER)',
        '#endif\n\n    g_set_prgname ("__BRAND__");\n\n    if (runtime == FRIDA_RUNTIME_OTHER)')
    c = c.replace('main_thread = g_thread_new ("frida-main-loop"',
                  'main_thread = g_thread_new ("__BRAND__-loop"')
    f.write_text(c)
    print("  ✓ 进程名和线程名替换完成")

    # 15. src/embed-agent.py - 添加注释
    print("[15] src/embed-agent.py")
    f = d / "src/embed-agent.py"
    c = f.read_text()
    c = c.replace(
                'shutil.copy(agent, embedded_agent)\n            else:',
                'shutil.copy(agent, embedded_agent)\n                # Agent 已由 post_process 中的 topatch 处理，此处无需再 patch\n            else:')
    f.write_text(c)
    print("  ✓ embed-agent 注释添加完成")

    # 16. lib/base/linux.vala - memfd 名
    print("[16] lib/base/linux.vala")
    f = d / "lib/base/linux.vala"
    c = f.read_text()
    c = c.replace('return Linux.syscall (LinuxSyscall.MEMFD_CREATE, name, flags);',
                  'return Linux.syscall (LinuxSyscall.MEMFD_CREATE, "jit-cache", flags);')
    f.write_text(c)
    print("  ✓ memfd 名替换完成")

    # 17. lib/base/rpc.vala - RPC 混淆
    print("[17] lib/base/rpc.vala")
    f = d / "lib/base/rpc.vala"
    c = f.read_text()
    # 添加 get_rpc_str 方法
    c = c.replace(
        '\t\t/**\n\t\t * Calls a remote method',
        '\t\tprivate static string get_rpc_str (bool quoted) {\n\t\t\tvar s = Obfuscate.decode_hex_xor ("__XOR_FRIDA_RPC__");\n\t\t\treturn quoted ? "\\"" + s + "\\"" : s;\n\t\t}\n\n\t\t/**\n\t\t * Calls a remote method')
    c = c.replace('.add_string_value ("frida:rpc")', '.add_string_value (get_rpc_str (false))')
    c = c.replace('if (json.index_of ("\\"frida:\\"")', 'if (json.index_of (get_rpc_str (true))')  # may not exist
    c = c.replace('if (json.index_of ("\\"frida:rpc\\"") == -1)', 'if (json.index_of (get_rpc_str (true)) == -1)')
    c = c.replace('if (type == null || type != "frida:rpc")', 'if (type == null || type != get_rpc_str (false))')
    f.write_text(c)
    print("  ✓ RPC 混淆完成")

    # 18. lib/base/xpc.vala - 错误标识
    print("[18] lib/base/xpc.vala")
    f = d / "lib/base/xpc.vala"
    c = f.read_text()
    c = c.replace('Quark.from_string ("frida-error-quark")',
                  'Quark.from_string (Obfuscate.decode_hex_xor ("__XOR_FRIDA_ERROR_QUARK__"))')
    f.write_text(c)
    print("  ✓ 错误标识替换完成")

    # 19. lib/base/p2p.vala - 线程名
    print("[19] lib/base/p2p.vala")
    f = d / "lib/base/p2p.vala"
    c = f.read_text()
    c = c.replace('new Thread<bool> ("frida-generate-certificate"',
                  'new Thread<bool> (Obfuscate.decode_hex_xor ("33273c31347832303b302734213078363027213c333c36342130")')
    f.write_text(c)
    print("  ✓ P2P 线程名替换完成")

    # 20. lib/agent/agent.vala - 线程名
    print("[20] lib/agent/agent.vala")
    f = d / "lib/agent/agent.vala"
    c = f.read_text()
    c = c.replace('"frida-eternal-agent"', 'Obfuscate.decode_hex_xor ("33273c313478302130273b3439783432303b21")')
    c = c.replace('"frida-agent-emulated"', 'Obfuscate.decode_hex_xor ("33273c3134783432303b21783038203934213031")')
    f.write_text(c)
    print("  ✓ Agent 线程名替换完成")

    # 21. lib/gadget/gadget.vala - 线程名
    print("[21] lib/gadget/gadget.vala")
    f = d / "lib/gadget/gadget.vala"
    c = f.read_text()
    c = c.replace('"frida-gadget-tcp-%u".printf (listen_port)',
                  '"%s%u".printf (Obfuscate.decode_hex_xor ("33273c3134783234313230217821362578"), listen_port)')
    c = c.replace('"frida-gadget-unix"', 'Obfuscate.decode_hex_xor ("33273c31347832343132302178203b3c2d")')
    f.write_text(c)
    print("  ✓ Gadget 线程名替换完成")

    # 21b. src/linux/linux-host-session.vala - zymbiote socket
    print("[21b] src/linux/linux-host-session.vala - zymbiote socket")
    f = d / "src/linux/linux-host-session.vala"
    c = f.read_text()
    c = c.replace('/frida-zymbiote-', f'/__BRAND__-zymbiote-')
    c = c.replace('/frida-zymbiote-00000000000000000000000000000000',
                  f'/__BRAND__-zymbiote-00000000000000000000000000000000')
    f.write_text(c)
    print("  ✓ Zymbiote socket 路径替换完成")

    # 21c. src/linux/helpers/zymbiote.c - zymbiote 模板
    print("[21c] src/linux/helpers/zymbiote.c - zymbiote 模板")
    zymbiote_c = d / "src/linux" / "helpers" / "zymbiote.c"
    if zymbiote_c.exists():
        c = zymbiote_c.read_text()
        c = c.replace('/frida-zymbiote-00000000000000000000000000000000',
                      f'/__BRAND__-zymbiote-00000000000000000000000000000000')
        zymbiote_c.write_text(c)
        print("  ✓ Zymbiote 模板替换完成")
    else:
        print("  ⚠ zymbiote.c 不存在，跳过")

    # 21d. src/linux/frida-helper-process.vala - helper 名
    print("[21d] src/linux/frida-helper-process.vala - helper 名")
    f = d / "src/linux" / "frida-helper-process.vala"
    c = f.read_text()
    c = c.replace('"frida-helper-32"', '"__BRAND__-helper-32"')
    c = c.replace('"frida-helper-64"', '"__BRAND__-helper-64"')
    f.write_text(c)
    print("  ✓ Helper 名替换完成")

    # 21e. src/linux/linux-host-session.vala - helper 路径
    print("[21e] src/linux/linux-host-session.vala - helper 路径")
    f = d / "src/linux" / "linux-host-session.vala"
    c = f.read_text()
    c = c.replace('/data/local/tmp/frida-helper-', '/data/local/tmp/__BRAND__-helper-')
    c = c.replace('/frida-helper-', '/__BRAND__-helper-')
    f.write_text(c)
    print("  ✓ Helper 路径替换完成")

    # 22. lib/base/meson.build - 添加 obfuscate.vala
    print("[22] lib/base/meson.build")
    f = d / "lib/base/meson.build"
    c = f.read_text()
    c = c.replace("  'stream.vala',\n  'rpc.vala',", "  'stream.vala',\n  'obfuscate.vala',\n  'rpc.vala',")
    f.write_text(c)
    print("  ✓ 添加 obfuscate.vala 到构建")

    # 23. lib/base/obfuscate.vala - 新文件
    print("[23] lib/base/obfuscate.vala (新建)")
    obfuscate_content = '''namespace Frida {
\t/**
\t * 运行时解码特征字符串，避免二进制中出现 frida 相关字面量，规避内存扫描。
\t * 支持 XOR 编码，可替换实现。
\t */
\tnamespace Obfuscate {
\t\tprivate const uint8 XOR_KEY = 0x55;

\t\t/**
\t\t * 从 hex 编码的 XOR 密文解码字符串。
\t\t * 编译期仅保留 hex 字面量，运行时还原真实字符串。
\t\t */
\t\tpublic static string decode_hex_xor (string hex) {
\t\t\tvar len = hex.length / 2;
\t\t\tvar sb = new StringBuilder.sized (len);
\t\t\tfor (var i = 0; i < len; i++) {
\t\t\t\tint64 val;
\t\t\t\tint64.try_parse (hex.substring (i * 2, 2), out val, null, 16);
\t\t\t\tvar b = (uint8) val;
\t\t\t\tsb.append_c ((char) (b ^ XOR_KEY));
\t\t\t}
\t\t\treturn sb.str;
\t\t}
\t}
}
'''
    (d / "lib/base/obfuscate.vala").write_text(obfuscate_content)
    print("  ✓ obfuscate.vala 创建完成")

    # 24. src/topatch.py - 新文件
    print("[24] src/topatch.py (新建)")
    topatch_content = '''import lief
import sys
import random
import string
import os


def random_alpha(length: int) -> str:
    """生成随机纯字母字符串"""
    return ''.join(random.choices(string.ascii_lowercase, k=length))


def log_color(msg):
    print(f"\\033[1;31;40m{msg}\\033[0m")


if __name__ == "__main__":
    input_file = sys.argv[1]

    log_color(f"[*] Patch frida-agent: {input_file}")
    binary = lief.parse(input_file)

    # 随机生成品牌名（5字母，等长替换 frida）
    brand = random_alpha(5)
    log_color(f"[*] Patch `frida` to `{brand}`")

    if not binary:
        log_color(f"[*] Not ELF, exit")
        sys.exit(1)
    else:
        # 符号表替换
        for symbol in binary.symbols:
            if symbol.name == "frida_agent_main":
                symbol.name = "main"
            if "frida" in symbol.name:
                symbol.name = symbol.name.replace("frida", brand)
            if "FRIDA" in symbol.name:
                symbol.name = symbol.name.replace("FRIDA", brand.upper())

        # .rodata 字符串反转
        all_patch_string = ["FridaScriptEngine", "GLib-GIO", "GDBusProxy", "GumScript"]

        for section in binary.sections:
            if section.name != ".rodata":
                continue
            for patch_str in all_patch_string:
                addr_all = section.search_all(patch_str)

                for addr in addr_all:
                    patch = [ord(n) for n in list(patch_str)[::-1]]
                    log_color(
                        f"[*] Patching section name={section.name} offset={hex(section.file_offset + addr)} orig:{patch_str} new:{''.join(list(patch_str)[::-1])}")
                    binary.patch_address(section.file_offset + addr, patch)

        binary.write(input_file)

        # 线程名替换（随机生成，等长替换）
        thread_gum_js_loop = random_alpha(11)  # gum-js-loop = 11字符
        log_color(f"[*] Patch `gum-js-loop` to `{thread_gum_js_loop}`")
        os.system(f"sed -b -i s/gum-js-loop/{thread_gum_js_loop}/g {input_file}")

        thread_gmain = random_alpha(5)  # gmain = 5字符
        log_color(f"[*] Patch `gmain` to `{thread_gmain}`")
        os.system(f"sed -b -i s/gmain/{thread_gmain}/g {input_file}")

        thread_gdbus = random_alpha(5)  # gdbus = 5字符
        log_color(f"[*] Patch `gdbus` to `{thread_gdbus}`")
        os.system(f"sed -b -i s/gdbus/{thread_gdbus}/g {input_file}")

        # 注：frida-gadget 不可全局 sed，会破坏 injector 的 frida-gadget-tcp- 匹配；gadget.glue 线程名已由 gadget.vala Obfuscate 处理

        # 仅做二进制 patch，不改协议（re.frida.*、frida:rpc 等），保证与标准 frida 客户端兼容

        # SONAME 残留特征：libfrida-gadget-raw.so / libfrida-agent-raw.so
        # 等长替换（frida->brand 均 5 字节），不改变 ELF 结构，安全
        for raw_name in ["libfrida-gadget-raw", "libfrida-agent-raw"]:
            new_raw = raw_name.replace("frida", brand)
            log_color(f"[*] Patch `{raw_name}` to `{new_raw}`")
            os.system(f"sed -b -i s/{raw_name}/{new_raw}/g {input_file}")
        log_color(f"[*] Patch Finish")
'''
    (d / "src/topatch.py").write_text(topatch_content)
    print("  ✓ topatch.py 创建完成")

    # 25. tools/post-process.py - 添加 topatch 调用
    print("[25] tools/post-process.py")
    f = d / "tools/post-process.py"
    c = f.read_text()
    # 在 termux_elf_cleaner 调用后面添加 topatch 调用
    old = "                           **run_kwargs)\n    except subprocess.CalledProcessError as e:"
    new = """                           **run_kwargs)

        # 内存特征 patch：对 Linux/Android 的 shared-library 和 executable 运行 topatch，规避内存扫描检测
        if host_os in {"linux", "android"} and kind in {"shared-library", "executable"}:
            topatch = Path(__file__).resolve().parent.parent / "src" / "topatch.py"
            if topatch.exists():
                # 不使用 PIPE，让 topatch 输出到终端/日志，便于确认 patch 已执行
                subprocess.run([sys.executable, str(topatch), str(intermediate_path)], check=True)
    except subprocess.CalledProcessError as e:"""
    c = c.replace(old, new)
    f.write_text(c)
    print("  ✓ post-process.py 添加 topatch 调用完成")

    print("\n=== 所有改动应用完成 ===")


def generate_patches(frida_core_dir, output_dir):
    """从改动生成补丁"""
    d = Path(frida_core_dir)
    out = Path(output_dir)

    print("\n=== 生成补丁 ===\n")

    # 生成 frida-core.patch（包含修改的文件）
    result = subprocess.run(
        ["git", "diff"],
        cwd=d,
        capture_output=True,
        text=True
    )

    # 添加新文件到 diff
    new_files = ["lib/base/obfuscate.vala", "src/topatch.py"]
    for nf in new_files:
        nf_path = d / nf
        if nf_path.exists():
            add_result = subprocess.run(
                ["git", "diff", "--no-index", "--", "/dev/null", nf],
                cwd=d,
                capture_output=True,
                text=True
            )
            # 直接使用相对路径，不需要修正
            result.stdout += add_result.stdout

    # 保存补丁
    patch_file = out / "frida-core.patch"
    patch_file.write_text(result.stdout)
    print(f"[✓] 生成 {patch_file} ({len(result.stdout)} bytes)")

    # 先还原源码
    subprocess.run(["git", "checkout", "."], cwd=d, capture_output=True)
    for nf in new_files:
        nf_path = d / nf
        if nf_path.exists():
            nf_path.unlink()
    print("[✓] 源码已还原")

    # 然后检查补丁（在干净的源码上）
    check = subprocess.run(
        ["git", "apply", "--check", str(patch_file)],
        cwd=d,
        capture_output=True,
        text=True
    )
    if check.returncode == 0:
        print("[✓] 补丁检查通过")
    else:
        print(f"[!] 补丁检查失败:")
        print(f"    {check.stderr[:500]}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python generate_patches.py <frida-core目录> [输出目录]")
        sys.exit(1)

    frida_core_dir = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "."

    apply_changes(frida_core_dir)
    generate_patches(frida_core_dir, output_dir)
