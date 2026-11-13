#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 apktool 反编译后的 APK 目录，整包重命名 Android 应用包名。

JMGO 兼容版重签改造通道专用：把官方 com.fongmi.android.tv 改造成
com.jmgo.android.tv，使重签版永远不与任何官方 com.fongmi.android.tv 安装包
（如 5.6.3）撞包名，根治 INSTALL_FAILED_UPDATE_INCOMPATIBLE（MuMu -7）。

这是 apktool 改包名的标准做法，必须同时做三件事，缺一件都会装完闪退 /
签名校验失败 / 找不到四大组件：
  1. AndroidManifest.xml 的 package="..." 属性；
  2. 所有 <provider android:authorities="old.xxx"> 等里的包名（随 #1 一起替换）；
  3. smali 目录 com/fongmi/android/tv 整体迁移到 com/jmgo/android/tv，
     并替换所有 smali / xml / 资源里对旧包名的文本引用
     （含 Lcom/fongmi/android/tv/...; 类型描述符与 "com.fongmi.android.tv" 字符串常量）。

用法：
  python3 rename_package.py --decoded-dir <dir> --old <old_pkg> --new <new_pkg>
  python3 rename_package.py --decoded-dir <dir> --old <old> --new <new> --dry-run
"""
import argparse
import os
import shutil
import sys

# 只在这些文本扩展名（或清单/ apktool 配置）上做字符串替换，二进制文件一律跳过，
# 避免把 resources.arsc / 图片 / lib/*.so 里的字节误改导致包损坏。
TEXT_EXT = {
    '.xml', '.smali', '.txt', '.json', '.html', '.htm', '.prop', '.java',
    '.kt', '.gradle', '.yaml', '.yml', '.cfg', '.ini', '.md', '.xml',
}
ALWAYS_TEXT = {'AndroidManifest.xml', 'apktool.yml'}


def is_text_file(path: str) -> bool:
    try:
        with open(path, 'rb') as f:
            chunk = f.read(4096)
    except OSError:
        return False
    if not chunk:
        return True
    if b'\x00' in chunk:          # 含 NUL 基本是二进制
        return False
    printable = sum(1 for b in chunk if 32 <= b < 127 or b in (9, 10, 13))
    if printable / len(chunk) < 0.7:   # 不可打印字符占比过高视为二进制
        return False
    return True


def move_smali_dirs(root: str, old_pkg: str, new_pkg: str):
    """把每个 smali* 目录下的 old_pkg 路径整体迁移到 new_pkg 路径。"""
    src_rel = os.path.join(*old_pkg.split('.'))
    dst_rel = os.path.join(*new_pkg.split('.'))
    moved = []
    for name in sorted(os.listdir(root)):
        if not name.startswith('smali'):
            continue
        base = os.path.join(root, name)
        if not os.path.isdir(base):
            continue
        src = os.path.join(base, src_rel)
        if not os.path.isdir(src):
            continue
        dst = os.path.join(base, dst_rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
        moved.append(src + ' -> ' + dst)
        # 清理旧的空父目录（com/fongmi/android、com/fongmi）
        p = os.path.join(base, *old_pkg.split('.')[:-1])
        while p != base:
            try:
                os.rmdir(p)
            except OSError:
                break
            p = os.path.dirname(p)
    return moved


def replace_text_refs(root: str, old_pkg: str, new_pkg: str):
    """在全部文本文件里替换旧包名：点号形式与斜杠形式都替换。"""
    old_slash = old_pkg.replace('.', '/')
    new_slash = new_pkg.replace('.', '/')
    changed_files = 0
    scanned = 0
    for dirpath, dirnames, filenames in os.walk(root):
        # 跳过重签无关的二进制大目录（加快速度，且更安全）
        if os.path.basename(dirpath) in ('lib', 'assets', 'original', 'res'):
            # res 里有 xml 需要替换，所以不能整体跳 res；只跳 lib/assets/original
            pass
        for fn in filenames:
            fp = os.path.join(dirpath, fn)
            ext = os.path.splitext(fn)[1].lower()
            if fn not in ALWAYS_TEXT and ext not in TEXT_EXT:
                continue
            if fn in ('resources.arsc',):   # 二进制编译产物，apktool 会重建，勿动
                continue
            if not is_text_file(fp):
                continue
            scanned += 1
            try:
                with open(fp, 'rb') as f:
                    data = f.read()
                text = data.decode('utf-8', 'surrogateescape')
            except Exception:
                continue
            new_text = text.replace(old_pkg, new_pkg).replace(old_slash, new_slash)
            if new_text != text:
                with open(fp, 'wb') as f:
                    f.write(new_text.encode('utf-8', 'surrogateescape'))
                changed_files += 1
    return scanned, changed_files


def replace_manifest(root: str, old_pkg: str, new_pkg: str):
    m = os.path.join(root, 'AndroidManifest.xml')
    if not os.path.isfile(m):
        return 0
    s = open(m, encoding='utf-8').read()
    # 先精确改 package 属性，再 blanket 替换其余引用（authorities / 组件类名）
    s = s.replace('package="%s"' % old_pkg, 'package="%s"' % new_pkg)
    s = s.replace(old_pkg, new_pkg)
    open(m, 'w', encoding='utf-8').write(s)
    return s.count(new_pkg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--decoded-dir', required=True)
    ap.add_argument('--old', required=True)
    ap.add_argument('--new', required=True)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    root = args.decoded_dir
    if not os.path.isdir(root) or not os.path.isfile(os.path.join(root, 'AndroidManifest.xml')):
        print('::error::not an apktool decoded dir (missing AndroidManifest.xml):', root,
              file=sys.stderr)
        return 2

    print('rename package:', args.old, '->', args.new)
    print('decoded dir   :', root)

    if args.dry_run:
        # 仅清点会改哪些文件，不落盘
        old_slash = args.old.replace('.', '/')
        new_slash = args.new.replace('.', '/')
        hits = 0
        for dirpath, _, filenames in os.walk(root):
            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                ext = os.path.splitext(fn)[1].lower()
                if fn not in ALWAYS_TEXT and ext not in TEXT_EXT:
                    continue
                if fn == 'resources.arsc':
                    continue
                if not is_text_file(fp):
                    continue
                try:
                    t = open(fp, 'rb').read().decode('utf-8', 'surrogateescape')
                except Exception:
                    continue
                if args.old in t or old_slash in t:
                    hits += 1
                    print('  would patch:', os.path.relpath(fp, root))
        print('dry-run: %d file(s) contain old package references' % hits)
        return 0

    moved = move_smali_dirs(root, args.old, args.new)
    print('moved smali dirs: %d' % len(moved))
    for m in moved:
        print('   ', m)

    manifest_hits = replace_manifest(root, args.old, args.new)
    print('manifest package/authority replacements:', manifest_hits)

    scanned, changed = replace_text_refs(root, args.old, args.new)
    print('text files scanned: %d, patched: %d' % (scanned, changed))

    # 自检：解码目录里不应再残留旧包名（文本范围内）
    leftover = 0
    old_slash = args.old.replace('.', '/')
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            fp = os.path.join(dirpath, fn)
            ext = os.path.splitext(fn)[1].lower()
            if fn not in ALWAYS_TEXT and ext not in TEXT_EXT:
                continue
            if fn == 'resources.arsc':
                continue
            if not is_text_file(fp):
                continue
            try:
                t = open(fp, 'rb').read().decode('utf-8', 'surrogateescape')
            except Exception:
                continue
            if args.old in t or old_slash in t:
                leftover += 1
                print('  ::warning::leftover old package in', os.path.relpath(fp, root))
    if leftover:
        print('::error::%d file(s) still reference old package after rename' % leftover,
              file=sys.stderr)
        return 1
    print('self-check OK: no leftover "%s" references in text files' % args.old)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
