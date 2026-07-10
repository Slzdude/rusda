# rusda

基于 [frida](https://github.com/frida/frida) 的反检测修改版本。

移除 frida 二进制中的固定特征（进程名、线程名、内存字符串、符号、memfd 名等），用于绕过目标应用的 frida 检测。

## 下载

到 [Releases](https://github.com/Slzdude/rusda/releases) 下载，每个版本包含四架构产物：
- `arm` / `arm64` / `x86` / `x86_64`
- `server` / `inject` / `gadget` / `compiler`

产物命名：`rusda-{server,inject,gadget,compiler}-<版本>-android-<架构>(.so).xz`

```bash
xz -d rusda-server-*-android-arm64.xz
adb push rusda-server-* /data/local/tmp/rusda-server
adb shell /data/local/tmp/rusda-server
```

## 自动构建

推送 tag 自动触发 CI 构建并发布（版本号与 frida 一致，不带 v 前缀）：

```bash
git tag 17.15.4
git push origin 17.15.4
```

## 修改内容

### 源码层

| 改动 | 目的 |
|------|------|
| `frida-*` → `rusda-*` | 文件名/进程名 |
| `re.frida.server` → `re.rusda.server` | 工作目录 |
| `frida:rpc` 运行时混淆 | RPC 标识 |
| 线程名 XOR 混淆 | `/proc/pid/task/*/comm` |
| `memfd:frida-agent` → `jit-cache` | maps 检测 |
| `frida_agent_main` → `main` | 入口符号 |
| `g_set_prgname("frida")` | 进程名 |

### 二进制层

通过 `topatch.py` 在编译后处理：
- `.rodata` 中的 GObject 类型名等长反转
- 符号表 `frida` → `rusda`
- 线程名等长替换
- SONAME 替换

## 自行编译

环境：Linux / WSL、Node 22、NDK r29、`pip install lief`

```bash
git clone https://github.com/Slzdude/rusda.git
cd rusda

git clone --recurse-submodules -b 17.15.4 https://github.com/frida/frida frida-src
cd frida-src

git apply --exclude=releng ../patches/superrepo.patch
( cd subprojects/frida-core && git apply ../../patches/frida-core.patch )
( cd subprojects/frida-gum  && git apply ../../patches/frida-gum.patch )

python ../tools/randomize_sources.py .

export ANDROID_NDK_ROOT=/path/to/ndk-r29
../tools/build-android-all.sh
```

## 目录结构

```
rusda/
├── .github/workflows/build.yml   # CI 自动构建
├── patches/                       # 补丁文件
├── tools/                         # 构建工具
└── README.md
```

## 发布流程

1. 修改补丁（如需要）
2. 提交到 main
3. `git tag <frida版本>`（如 `17.15.4`）
4. `git push origin <frida版本>`
5. CI 自动构建并发布

## License

本项目仅供学习研究使用，请在合法授权范围内使用。
