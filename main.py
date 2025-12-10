#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
目录拷贝工具 (GUI版)
支持批量拷贝XXX_开头的文件夹或单个文件夹，并自动添加日期后缀
配置请在界面修改，会自动保存到配置 config.json
"""

import os
import shutil
import json
import codecs
from datetime import datetime
from pathlib import Path
import fnmatch
import tkinter as tk
from tkinter import messagebox, scrolledtext, font, filedialog
import threading
import sys
import io
import socket
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from functools import partial

# 默认配置
DEFAULT_CONFIG = {
    "TARGET_DIR": "D:\\test_aaa",
    "HTTP_PORT": 10888,
    "SRC_DIR": "D:\\test_bbb",
    "SRC_PDIR": "D:\\",
    "SRC_PDIR_PREFIX": ["test_", "test2_"],
    "EXCLUDE_DIRS": [
        ".idea", ".git", "target", "node_modules", ".mvn", ".vscode", "build",
        ".npm", ".cache", ".project", ".metadata", "kibana", "dist",
        ".venv", "jre", "WebContent", "apm_prod_shell", "vendor"
    ],
    "EXCLUDE_PATTERNS": ["*.log", "hs_err_pid*", "*.iml", "*.tgz"]
}


class RedirectText(io.StringIO):
    """重定向输出到Text控件"""
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def write(self, string):
        self.text_widget.after(0, self._append, string)
    
    def _append(self, string):
        self.text_widget.insert(tk.END, string)
        self.text_widget.see(tk.END)
    
    def flush(self):
        pass


class CopyerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mini Project Copyer")
        self.root.geometry("900x750")
        
        self.queued_logs = []  # 日志队列，防止UI未初始化时写入报错
        
        # 配置数据
        self.config = {}
        self.load_config()
        
        # 构建UI
        self.create_widgets()

        # HTTP Server State
        self.httpd = None
        self.server_thread = None
        self.http_server_running = False
        
        # 输出初始化阶段对日志
        self.flush_queued_logs()
        
        # 绑定关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def load_config(self):
        """加载配置，不存在则使用默认"""
        config_path = Path("config.json")
        if not config_path.exists():
            self.config = DEFAULT_CONFIG.copy()
            self.log_message("未找到 config.json，使用默认配置。")
        else:
            try:
                with codecs.open(config_path, 'r', 'utf-8') as f:
                    self.config = json.load(f)
                self.log_message("已加载配置文件 config.json")
            except Exception as e:
                self.config = DEFAULT_CONFIG.copy()
                self.log_message(f"读取配置文件失败: {e}，使用默认配置。")
                
        # 确保EXCLUDE_DIRS是列表以便编辑 (虽然JSON加载出来就是列表)
        if 'EXCLUDE_DIRS' not in self.config:
            self.config['EXCLUDE_DIRS'] = DEFAULT_CONFIG['EXCLUDE_DIRS']
        if 'EXCLUDE_PATTERNS' not in self.config:
            self.config['EXCLUDE_PATTERNS'] = DEFAULT_CONFIG['EXCLUDE_PATTERNS']

    def save_config(self):
        """保存配置到文件"""
        self.update_config_from_ui()
        try:
            with codecs.open("config.json", 'w', 'utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            messagebox.showinfo("成功", "配置已保存到 config.json")
            self.log_message("配置已保存。")
        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败: {e}")

    def update_config_from_ui(self):
        """从UI更新配置字典"""
        self.config['TARGET_DIR'] = self.entry_target_dir.get()
        self.config['SRC_DIR'] = self.entry_src_dir.get()
        self.config['SRC_PDIR'] = self.entry_src_pdir.get()
        
        prefixes = self.entry_src_pdir_prefix.get().replace('，', ',').split(',')
        self.config['SRC_PDIR_PREFIX'] = [p.strip() for p in prefixes if p.strip()]
        
        exclude_dirs = self.text_exclude_dirs.get("1.0", tk.END).strip().split('\n')
        self.config['EXCLUDE_DIRS'] = [d.strip() for d in exclude_dirs if d.strip()]
        
        exclude_patterns = self.text_exclude_patterns.get("1.0", tk.END).strip().split('\n')
        self.config['EXCLUDE_PATTERNS'] = [p.strip() for p in exclude_patterns if p.strip()]

        try:
            self.config['HTTP_PORT'] = int(self.entry_http_port.get())
        except ValueError:
            self.config['HTTP_PORT'] = 10888 # Fallback

    def browse_directory(self, entry_widget):
        """打开文件夹选择框"""
        initial_dir = entry_widget.get()
        if not initial_dir or not os.path.exists(initial_dir):
            initial_dir = os.getcwd()
            
        selected_dir = filedialog.askdirectory(initialdir=initial_dir)
        if selected_dir:
            # 兼容Windows路径显示
            selected_dir = str(Path(selected_dir))
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, selected_dir)

    def create_widgets(self):
        # 主容器：使用 PanedWindow 实现左右分栏
        paned_window = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=5)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # --- 左侧：配置区域 ---
        left_frame = tk.Frame(paned_window)
        paned_window.add(left_frame, minsize=350, stretch="always") # 设置左侧最小宽度
        
        # 字体
        lbl_font = font.Font(weight="bold")
        
        # 1. Target Dir
        tk.Label(left_frame, text="目标目录 (Target Dir):", font=lbl_font).pack(anchor="w")
        frame_target = tk.Frame(left_frame)
        frame_target.pack(fill=tk.X, pady=(0, 5))
        
        self.entry_target_dir = tk.Entry(frame_target)
        self.entry_target_dir.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry_target_dir.insert(0, self.config.get('TARGET_DIR', ''))
        
        tk.Button(frame_target, text="📂", width=3, command=lambda: self.browse_directory(self.entry_target_dir)).pack(side=tk.LEFT, padx=(5, 0))
        
        # 2. Src Dir
        tk.Label(left_frame, text="单个源目录 (Src Dir) [当PDir为空时生效]:", font=lbl_font).pack(anchor="w")
        frame_src = tk.Frame(left_frame)
        frame_src.pack(fill=tk.X, pady=(0, 5))
        
        self.entry_src_dir = tk.Entry(frame_src)
        self.entry_src_dir.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry_src_dir.insert(0, self.config.get('SRC_DIR', ''))
        
        tk.Button(frame_src, text="📂", width=3, command=lambda: self.browse_directory(self.entry_src_dir)).pack(side=tk.LEFT, padx=(5, 0))
        
        # 3. Src PDir
        tk.Label(left_frame, text="批量父目录 (Src PDir):", font=lbl_font).pack(anchor="w")
        frame_pdir = tk.Frame(left_frame)
        frame_pdir.pack(fill=tk.X, pady=(0, 5))
        
        self.entry_src_pdir = tk.Entry(frame_pdir)
        self.entry_src_pdir.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry_src_pdir.insert(0, self.config.get('SRC_PDIR', ''))
        
        tk.Button(frame_pdir, text="📂", width=3, command=lambda: self.browse_directory(self.entry_src_pdir)).pack(side=tk.LEFT, padx=(5, 0))
        
        # 4. PDir Prefix
        tk.Label(left_frame, text="子目录前缀 (逗号分隔):", font=lbl_font).pack(anchor="w")
        self.entry_src_pdir_prefix = tk.Entry(left_frame)
        self.entry_src_pdir_prefix.pack(fill=tk.X, pady=(0, 5))
        self.entry_src_pdir_prefix.insert(0, ", ".join(self.config.get('SRC_PDIR_PREFIX', [])))
        
        # 5. Exclude Dirs
        tk.Label(left_frame, text="排除目录 (每行一个):", font=lbl_font).pack(anchor="w")
        self.text_exclude_dirs = scrolledtext.ScrolledText(left_frame, height=10) # 增加高度
        self.text_exclude_dirs.pack(fill=tk.BOTH, expand=True, pady=(0, 5)) # 允许垂直扩展
        self.text_exclude_dirs.insert(tk.END, "\n".join(self.config.get('EXCLUDE_DIRS', [])))

        # 6. Exclude Patterns
        tk.Label(left_frame, text="排除文件模式 (每行一个):", font=lbl_font).pack(anchor="w")
        self.text_exclude_patterns = scrolledtext.ScrolledText(left_frame, height=8) # 增加高度
        self.text_exclude_patterns.pack(fill=tk.BOTH, expand=True, pady=(0, 5)) # 允许垂直扩展
        self.text_exclude_patterns.insert(tk.END, "\n".join(self.config.get('EXCLUDE_PATTERNS', [])))
        
        # 7. HTTP Port
        tk.Label(left_frame, text="HTTP端口 (HTTP Port):", font=lbl_font).pack(anchor="w")
        self.entry_http_port = tk.Entry(left_frame)
        self.entry_http_port.pack(fill=tk.X, pady=(0, 5))
        self.entry_http_port.insert(0, str(self.config.get('HTTP_PORT', 10888)))
        
        # 按钮区域
        btn_frame = tk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        tk.Button(btn_frame, text="保存配置", command=self.save_config, bg="#dddddd").pack(side=tk.LEFT, padx=5)
        
        self.btn_http = tk.Button(btn_frame, text="开启HTTP", command=self.toggle_http_server, bg="#2196F3", fg="white", font=lbl_font)
        self.btn_http.pack(side=tk.LEFT, padx=5)

        self.btn_run = tk.Button(btn_frame, text="执行拷贝", command=self.start_copy_thread, bg="#4CAF50", fg="white", font=lbl_font)
        self.btn_run.pack(side=tk.LEFT, padx=5)
        
        # --- 右侧：日志区域 ---
        right_frame = tk.Frame(paned_window)
        paned_window.add(right_frame, minsize=200, stretch="always")
        
        tk.Label(right_frame, text="执行日志:", font=lbl_font).pack(anchor="w")
        self.text_log = scrolledtext.ScrolledText(right_frame, state='normal')
        self.text_log.pack(fill=tk.BOTH, expand=True)

        # 设置PanedWindow的初始分割比例 (需要等UI绘制后设置才准确，这里简单用sash placement)
        # 只有在pack之后才能有效设置sash位置，或者通过add的参数控制resize behavior

    def log_message(self, msg):
        """GUI日志输出 (安全地在主线程调用)"""
        # 如果UI还未初始化，先加入队列
        if not hasattr(self, 'text_log'):
            self.queued_logs.append(msg)
            return

        if threading.current_thread() is threading.main_thread():
             self.text_log.insert(tk.END, str(msg) + "\n")
             self.text_log.see(tk.END)
        else:
             self.text_log.after(0, lambda: self.log_message(msg))

    def flush_queued_logs(self):
        """输出所有暂存的日志"""
        for msg in self.queued_logs:
            self.log_message(msg)
        self.queued_logs = []

    def start_copy_thread(self):
        """再单独线程运行拷贝"""
        self.btn_run.config(state=tk.DISABLED, text="执行中...")
        self.update_config_from_ui() # 确保使用最新输入
        t = threading.Thread(target=self.run_copy_task)
        t.start()
        
    def run_copy_task(self):
        # 重定向 stdout
        # 注意: 这里的重定向在多线程环境下可能会有竞争，但对于简单的单任务工具接受度尚可
        # 更优做法是重构 core logic 为生成器或 callback，这里复用 stdout 重定向至 text_log
        
        old_stdout = sys.stdout
        sys.stdout = RedirectText(self.text_log)
        
        try:
            print(f"--- 任务开始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
            
            # 这里复用之前的核心逻辑，但需要适配配置读取
            # 为了减少代码重复，可以将之前 global 的逻辑改为接受 config 参数的 class
            
            copier = DirectoryCopier(self.config)
            copier.run()
            
            print(f"--- 任务结束 ---")
        except Exception as e:
            print(f"任务发生严重错误: {e}")
        finally:
            sys.stdout = old_stdout
            self.root.after(0, lambda: self.btn_run.config(state=tk.NORMAL, text="执行拷贝"))

    def toggle_http_server(self):
        """切换HTTP服务状态"""
        if self.http_server_running:
            self.stop_http_server()
        else:
            self.start_http_server_thread()

    def start_http_server_thread(self):
        """启动HTTP服务线程"""
        port = 10888
        try:
            port = int(self.entry_http_port.get())
        except ValueError:
            self.log_message("HTTP端口无效，使用默认 10888")
            port = 10888
            
        target_dir = self.entry_target_dir.get()
        if not target_dir or not os.path.exists(target_dir):
            self.log_message(f"HTTP启动失败: 目标目录不存在 {target_dir}")
            return

        self.btn_http.config(text="启动中...", state=tk.DISABLED)
        
        t = threading.Thread(target=self.run_http_server, args=(target_dir, port))
        t.daemon = True
        t.start()
        self.server_thread = t

    def run_http_server(self, root_dir, port):
        """HTTP服务运行逻辑"""
        try:
            # 定义带日志回调的 Handler
            class GUIRequestHandler(SimpleHTTPRequestHandler):
                def log_message(self_handler, format, *args):
                    msg = "[HTTP] %s - - [%s] %s" % (
                        self_handler.client_address[0],
                        self_handler.log_date_time_string(),
                        format % args
                    )
                    # 通过 server 实例回调 app 的日志方法
                    if hasattr(self_handler.server, 'app_log_callback'):
                        self_handler.server.app_log_callback(msg)

            class ACThreadingHTTPServer(ThreadingHTTPServer):
                allow_reuse_address = True

            handler_class = partial(GUIRequestHandler, directory=root_dir)
            
            self.httpd = ACThreadingHTTPServer(("0.0.0.0", port), handler_class)
            self.httpd.app_log_callback = self.log_message_thread_safe
            
            self.http_server_running = True
            
            # 获取本机IP
            local_ips = self.get_all_ips()
            ip_msg = "\n".join([f"  http://{ip}:{port}/" for ip in local_ips])
            
            self.root.after(0, lambda: self.btn_http.config(text="关闭HTTP", state=tk.NORMAL, bg="#f44336"))
            self.log_message_thread_safe(f"HTTP服务已启动. 目标: {root_dir}")
            self.log_message_thread_safe(f"可访问地址:\n{ip_msg}")
            
            self.httpd.serve_forever()
            
        except Exception as e:
            self.log_message_thread_safe(f"HTTP服务启动失败: {e}")
            self.http_server_running = False
            self.root.after(0, lambda: self.btn_http.config(text="开启HTTP", state=tk.NORMAL, bg="#2196F3"))
        finally:
             if self.httpd:
                 self.httpd.server_close()

    def stop_http_server(self):
        """停止HTTP服务"""
        if self.httpd:
            self.log_message("正在停止HTTP服务...")
            # shutdown 需要在独立线程调用，否则会死锁（如果是在 serve_forever 的同一个线程调用）
            # 但这里是在主线程调用 stop，server 在子线程 serve_forever
            threading.Thread(target=self.httpd.shutdown).start()
            
        self.http_server_running = False
        self.btn_http.config(text="开启HTTP", bg="#2196F3")
        self.log_message("HTTP服务已停止。")

    def on_closing(self):
        """关闭程序前的清理"""
        if self.http_server_running:
            try:
                # 尝试优雅关闭，但不必等待太久以免阻塞退出
                if self.httpd:
                   # 强制停止Server
                   self.httpd.shutdown() 
                   self.httpd.server_close()
            except:
                pass
        self.root.destroy()

    def log_message_thread_safe(self, msg):
        """线程安全的日志记录"""
        self.log_message(msg)
        
    def get_all_ips(self):
        """获取所有非回环的IPV4地址"""
        ips = []
        try:
            # 方法1: 获取所有网卡信息
            host_name = socket.gethostname() 
            # gethostbyname_ex 返回 (hostname, aliaslist, ipaddrlist)
            _, _, ip_list = socket.gethostbyname_ex(host_name)
            ips = [ip for ip in ip_list if not ip.startswith("127.")]
        except:
            pass
            
        # 如果获取失败或为空，尝试连接外网探测
        if not ips:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                s.close()
                ips = [ip]
            except:
                pass
        
        # 始终包含 localhost 方便测试
        ips.insert(0, "localhost")
        return list(set(ips)) # 去重


# ======================================================================================
# 核心业务逻辑类 (重构自原 main 函数)
# ======================================================================================

class DirectoryCopier:
    def __init__(self, config_dict):
        self.config = config_dict
        self.target_dir = self.config.get('TARGET_DIR', '')
        self.src_pdir = self.config.get('SRC_PDIR', '')
        self.src_dir = self.config.get('SRC_DIR', '')
        self.src_pdir_prefix = self.config.get('SRC_PDIR_PREFIX', [])
        # 转换为 set
        self.exclude_dirs = set(self.config.get('EXCLUDE_DIRS', []))
        self.exclude_patterns = self.config.get('EXCLUDE_PATTERNS', [])

    def should_exclude_dir(self, dirname, current_excludes):
        return dirname in current_excludes

    def should_exclude_file(self, filename):
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True
        return False

    def copy_directory(self, src, dst, current_excludes):
        if not os.path.exists(dst):
            os.makedirs(dst)
            print(f"创建目录: {dst}")
        
        copied_files = 0
        excluded_items = 0
        
        try:
            for item in os.listdir(src):
                src_path = os.path.join(src, item)
                dst_path = os.path.join(dst, item)
                
                if os.path.isdir(src_path):
                    if self.should_exclude_dir(item, current_excludes):
                        print(f"  [排除目录] {item}/")
                        excluded_items += 1
                        continue
                    sub_copied, sub_excluded = self.copy_directory(src_path, dst_path, current_excludes)
                    copied_files += sub_copied
                    excluded_items += sub_excluded
                else:
                    if self.should_exclude_file(item):
                        print(f"  [排除文件] {item}")
                        excluded_items += 1
                        continue
                    shutil.copy2(src_path, dst_path)
                    copied_files += 1
        except Exception as e:
            print(f"错误: 拷贝 {src} 时出现异常: {e}")
        
        return copied_files, excluded_items
        
    def get_target_dirname(self, dirname):
        today = datetime.now().strftime('%Y%m%d')
        return f"{dirname}_{today}"

    def run(self):
        if not self.target_dir:
            print("错误: 未配置目标目录 (Target Dir)")
            return

        target_dir_path = Path(self.target_dir)
        try:
            if not target_dir_path.exists():
                target_dir_path.mkdir(parents=True, exist_ok=True)
                print(f"创建目标目录: {target_dir_path}\n")
        except Exception as e:
            print(f"错误: 无法创建目标目录 {target_dir_path}: {e}")
            return
            
        source_dirs = []
        
        # 1. Check PDIR
        if self.src_pdir and self.src_pdir.strip():
            pdir = Path(self.src_pdir)
            print(f"模式: 批量扫描父目录 {pdir}")
            
            if pdir.exists() and pdir.is_dir():
                prefixes = self.src_pdir_prefix
                if not prefixes:
                    print("警告: 前缀列表为空")
                
                for item in pdir.iterdir():
                    if item.is_dir():
                        for prefix in prefixes:
                            if item.name.startswith(prefix):
                                source_dirs.append(item)
                                break
                if not source_dirs:
                    print(f"警告: 未找到匹配前缀 {prefixes} 的文件夹")
            else:
                 print(f"错误: PDir 不存在或不是目录: {self.src_pdir}")

        # 2. Check Single Dir (fallback)
        elif self.src_dir and self.src_dir.strip():
            src_path = Path(self.src_dir)
            print(f"模式: 单个目录拷贝 {src_path}")
            if src_path.exists() and src_path.is_dir():
                source_dirs.append(src_path)
            else:
                print(f"错误: Src Dir 不存在或不是目录: {self.src_dir}")
        else:
            print("错误: 未配置 Src PDir 或 Src Dir")
            return

        if not source_dirs:
            print("没有待拷贝的源目录，任务结束。")
            return

        print(f"待处理目录数: {len(source_dirs)}\n")
        
        total_copied = 0
        total_excluded = 0
        
        for idx, src_d in enumerate(source_dirs, 1):
            target_name = self.get_target_dirname(src_d.name)
            target_path = target_dir_path / target_name
            
            print(f"[{idx}/{len(source_dirs)}] 正在处理: {src_d.name}")
            print(f"  -> 目标: {target_path}")
            
            if target_path.exists():
                print(f"  警告: 目标目录已存在，清理旧目录...")
                try:
                    shutil.rmtree(target_path)
                except Exception as e:
                    print(f"  错误: 无法清理目录 {target_path}: {e}")
                    continue
            
            # 防止递归拷贝
            current_excludes = self.exclude_dirs.copy()
            current_excludes.add(target_name)
            
            c, e = self.copy_directory(str(src_d), str(target_path), current_excludes)
            total_copied += c
            total_excluded += e
            print(f"  完成: {c} 文件, 排除 {e} 项\n")
            
        print("=" * 60)
        print(f"此次任务汇总: 拷贝 {total_copied}, 排除 {total_excluded}")
        print("=" * 60)


def main():
    root = tk.Tk()
    app = CopyerApp(root)
    root.mainloop()

if __name__ == '__main__':
    main()