import os
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import datetime
import json
import glob
import shutil

CONFIG_FILE = "assets/repkg_config.json"

def win_path(path: str) -> str:
    """将路径统一转换为 Windows 格式（反斜杠）"""
    return os.path.normpath(path)


class RePKG_GUI:
    def __init__(self, root):
        self.root = root
        
        # === 加载配置 ===
        self.config = self.load_config()
        
        # --- UI Initialization / Data Setup ---
        self.initialize_data()
        
        title = f"{self.config['app_name']} {self.config['version']} ({self.config['platform']}) - {self.config['author']}"
        self.root.title(title)
        
        # === 创建主框架 ===
        main_frame = tk.Frame(root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Grid setup for main_frame
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=3)
        main_frame.grid_rowconfigure(2, weight=0)
        main_frame.grid_columnconfigure(0, weight=1)
        
        # === 标签页控件 (Row 0) ===
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew", pady=(0, 5))
        
        # === 创建各个标签页 ===
        self.create_config_tab()  # 只保留 RePKG 配置标签页
        
        # === 日志区域 (Row 1, independent) ===
        log_area_frame = self.create_log_area(main_frame)
        log_area_frame.grid(row=1, column=0, sticky="nsew", pady=5)
        
        # === 底部控制按钮区域 (Row 2) ===
        control_frame = self.create_control_buttons(main_frame)
        control_frame.grid(row=2, column=0, sticky="ew", pady=(5, 0))
        
        # 首次加载时更新预览
        self.root.after(100, self.update_preview)
    
    def initialize_data(self):
        """初始化配置和Tkinter变量 (使用 StringVar)"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Paths
        default_exe = self.config.get("repkg_path", os.path.join(script_dir, "RePKG.exe"))
        default_output = self.config.get("output_dir", os.path.join(script_dir, "output"))
        
        self.repkg_path = tk.StringVar(value=default_exe)
        self.input_entry = tk.StringVar(value=self.config.get("input_dir", ""))
        self.output_entry = tk.StringVar(value=default_output)
        
        # Mode
        self.mode = tk.StringVar(value=self.config.get("mode", "extract"))
        
        # Options
        self.options = {
            "-t, --tex (转换TEX)": tk.BooleanVar(value=self.config.get("tex", True)),
            "-c, --copyproject (复制项目文件)": tk.BooleanVar(value=self.config.get("copyproject", True)),
            "-n, --usename (使用项目名)": tk.BooleanVar(value=self.config.get("usename", True)),
            "--overwrite (覆盖现有文件)": tk.BooleanVar(value=self.config.get("overwrite", True)),
            "-r, --recursive (递归搜索)": tk.BooleanVar(value=self.config.get("recursive", True)),
        }
        self.python_options = {
            "复制预览图像 (preview.*)": tk.BooleanVar(value=self.config.get("copy_preview", True)),
            "原地替换模式自动备份": tk.BooleanVar(value=self.config.get("auto_backup", True)),
        }
        
        # Bindings for preview update
        self.repkg_path.trace_add("write", lambda *args: self.update_preview())
        self.input_entry.trace_add("write", lambda *args: self.update_preview())
        self.output_entry.trace_add("write", lambda *args: self.update_preview())
        self.mode.trace_add("write", lambda *args: self.update_preview())
        for var in self.options.values():
            var.trace_add("write", lambda *args: self.update_preview())
    
    def pack_path_selector(self, parent_frame, label_text, var_control, button_command):
        """Helper to create a path entry with a browse button."""
        
        tk.Label(parent_frame, text=label_text, font=("Arial", 10, "bold")).pack(anchor="w", padx=0, pady=(10, 2))
        frame_selector = tk.Frame(parent_frame)
        frame_selector.pack(fill="x", padx=0, pady=2)
        
        tk.Entry(frame_selector, textvariable=var_control).pack(side="left", fill="x", expand=True)
        tk.Button(frame_selector, text="浏览", command=button_command).pack(side="left", padx=5)
    
    def pack_mode_selector(self, parent_frame, label_text, var_control, modes):
        """Helper to create radio buttons for mode selection."""
        
        tk.Label(parent_frame, text=label_text, font=("Arial", 10, "bold")).pack(anchor="w", padx=0, pady=(10, 2))
        mode_frame = tk.Frame(parent_frame)
        mode_frame.pack(anchor="w", padx=10, pady=2)
        
        for mode in modes:
            text = f"{mode} 模式"
            if mode == "extract":
                text += " (extract)"
            elif mode == "info":
                text += " (info)"
            
            tk.Radiobutton(mode_frame, text=text, variable=var_control, value=mode).pack(anchor="w")
    
    def pack_checkbox_group(self, parent_frame, label_text, options_dict):
        """Helper to create a group of checkboxes."""
        
        tk.Label(parent_frame, text=label_text, font=("Arial", 10, "bold")).pack(anchor="w", padx=0, pady=(10, 2))
        frame_opts = tk.Frame(parent_frame)
        frame_opts.pack(anchor="w", padx=10, pady=2)
        
        for text, var in options_dict.items():
            tk.Checkbutton(frame_opts, text=text, variable=var).pack(anchor="w")
    
    def create_config_tab(self):
        """创建配置标签页"""
        config_frame = ttk.Frame(self.notebook)
        self.notebook.add(config_frame, text="RePKG")
        
        # 配置 config_frame 的 Grid 布局
        config_frame.grid_columnconfigure(0, weight=1, uniform="col")  # 左栏 (路径)
        config_frame.grid_columnconfigure(1, weight=1, uniform="col")  # 右栏 (参数)
        config_frame.grid_rowconfigure(0, weight=1)  # 主要内容行 (扩展)
        config_frame.grid_rowconfigure(1, weight=0)  # 预览行 (固定高度)
        
        # --- 左侧框架 (路径信息) ---
        left_frame = ttk.LabelFrame(config_frame, text="路径信息", padding="10")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        left_frame.grid_columnconfigure(0, weight=1)
        
        # --- 右侧框架 (配置参数) ---
        right_frame = ttk.LabelFrame(config_frame, text="配置参数", padding="10")
        right_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        right_frame.grid_columnconfigure(0, weight=1)
        
        # === 左栏组件 (路径) ===
        self.pack_path_selector(left_frame, "RePKG.exe 路径（默认脚本所在目录）:",
                                self.repkg_path, self.select_exe)
        self.pack_path_selector(left_frame, "输入根目录（含 .pkg 文件或子目录）:",
                                self.input_entry, self.select_input_dir)
        self.pack_path_selector(left_frame, "输出根目录 (可与输入目录相同，将启用原地替换与备份):",
                                self.output_entry, self.select_output_dir)
        
        # === 右栏组件 (模式和选项) ===
        self.pack_checkbox_group(right_frame, "RePKG 命令选项:", self.options)
        self.pack_checkbox_group(right_frame, "Python 脚本选项:", self.python_options)
        
        # --- 命令预览 (Row 1) ---
        preview_frame = ttk.LabelFrame(config_frame, text="命令预览（Windows CMD 格式）", padding="10")
        preview_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        
        self.cmd_preview = tk.Text(preview_frame, height=4, bg="#f5f5f5", font=("Consolas", 9))
        self.cmd_preview.pack(fill="x", expand=True)
    
    def create_log_area(self, parent):
        """创建日志区域，作为独立于标签页的区域，并返回框架"""
        
        # 使用 LabelFrame 增加日志区域的边界和标题
        log_area_frame = tk.LabelFrame(parent, text="📝 运行日志", padx=5, pady=5)
        
        # 日志控制按钮
        log_control_frame = tk.Frame(log_area_frame)
        log_control_frame.pack(fill="x", pady=2)
        
        tk.Button(log_control_frame, text="清空日志", command=self.clear_log).pack(side="left", padx=5)
        tk.Button(log_control_frame, text="保存日志", command=self.save_log).pack(side="left", padx=5)
        
        # 自动滚动状态和按钮
        self.auto_scroll = True
        self.auto_scroll_button = tk.Button(log_control_frame,
                                            text="自动滚动: 启用",
                                            command=self.toggle_auto_scroll)
        self.auto_scroll_button.pack(side="left", padx=5)
        
        # 日志显示区域
        self.log_box = scrolledtext.ScrolledText(log_area_frame,
                                                 font=("Consolas", 9),
                                                 wrap="word")
        # 使用 fill="both", expand=True 确保它占用父框架（log_area_frame）的所有空间
        self.log_box.pack(fill="both", expand=True, padx=5, pady=5)
        
        return log_area_frame  # 返回框架，由 __init__ 中的 grid 管理
    
    def create_control_buttons(self, parent):
        """创建底部控制按钮区域，并返回框架"""
        control_frame = tk.Frame(parent)
        
        # 主要操作按钮
        main_buttons = tk.Frame(control_frame)
        main_buttons.pack(side="left")
        
        tk.Button(main_buttons, text="🚀 运行任务", bg="#4CAF50", fg="white",
                  font=("Arial", 11, "bold"), command=self.start_task).pack(side="left", padx=5)
        tk.Button(main_buttons, text="💾 保存配置", command=self.save_config).pack(side="left", padx=5)
        tk.Button(main_buttons, text="📁 打开输出目录", command=self.open_output_dir).pack(side="left", padx=5)
        
        return control_frame  # 返回框架，由 __init__ 中的 grid 管理
    
    # ------------------------------------------------------------
    #  文件选择区 (使用 StringVar 的 set 方法)
    # ------------------------------------------------------------
    def select_exe(self):
        path = filedialog.askopenfilename(title="选择 RePKG.exe", filetypes=[("RePKG Executable", "*.exe")])
        if path:
            self.repkg_path.set(path)
    
    def select_input_dir(self):
        path = filedialog.askdirectory(title="选择输入根目录")
        if path:
            self.input_entry.set(path)
    
    def select_output_dir(self):
        path = filedialog.askdirectory(title="选择输出根目录")
        if path:
            self.output_entry.set(path)
    
    def open_output_dir(self):
        """打开输出目录"""
        output_dir = self.output_entry.get().strip()
        if not output_dir:
            messagebox.showwarning("警告", "请先设置输出目录！")
            return
        
        if not os.path.exists(output_dir):
            messagebox.showwarning("警告", f"输出目录不存在: {output_dir}")
            return
        
        try:
            os.startfile(output_dir)  # Windows 打开文件夹
        except Exception as e:
            messagebox.showerror("错误", f"无法打开输出目录: {e}")
    
    def clear_log(self):
        """清空日志"""
        self.log_box.delete(1.0, tk.END)
        self.log_box.insert(tk.END, f"📝 [{datetime.datetime.now().strftime('%H:%M:%S')}] 日志已清空\n")
    
    def save_log(self):
        """保存日志到文件"""
        log_content = self.log_box.get(1.0, tk.END)
        if not log_content.strip():
            messagebox.showwarning("警告", "日志内容为空！")
            return
        
        filename = filedialog.asksaveasfilename(
            title="保存日志",
            defaultextension=".txt",
            initialfile=f"RePKG_Log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(log_content)
                messagebox.showinfo("成功", f"日志已保存到: {filename}")
            except Exception as e:
                messagebox.showerror("错误", f"保存日志失败: {e}")
    
    def toggle_auto_scroll(self):
        """切换自动滚动状态"""
        self.auto_scroll = not self.auto_scroll
        status = "启用" if self.auto_scroll else "禁用"
        self.auto_scroll_button.config(text=f"自动滚动: {status}")
    
    # ------------------------------------------------------------
    #  配置保存/加载
    # ------------------------------------------------------------
    def load_config(self):
        # 默认配置
        default_config = {
            "app_name": "RePKG 批量提取 GUI",
            "version": "v4 (Simplified)",
            "platform": "Windows 版",
            "author": "by YuefChen",
            "repkg_path": os.path.join(os.getcwd(), "RePKG.exe"),
            "input_dir": "",
            "output_dir": "",
            "mode": "extract",
            "tex": True,
            "copyproject": True,
            "usename": True,
            "overwrite": True,
            "recursive": True,
            "copy_preview": True,
            "auto_backup": True
        }
        
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    loaded_config = json.load(f)
                
                    # 合并默认配置和加载的配置
                    for key, value in default_config.items():
                        if key not in loaded_config:
                            loaded_config[key] = value
                    # 移除旧的不需要的配置项
                    return loaded_config
            except Exception:
                return default_config
        return default_config
    
    def save_config(self):
        # 更新当前配置 (使用 .get() 获取 StringVar/BooleanVar 的值)
        self.config.update({
            "repkg_path": self.repkg_path.get().strip(),
            "input_dir": self.input_entry.get().strip(),
            "output_dir": self.output_entry.get().strip(),
            "mode": self.mode.get(),
            "tex": self.options["-t, --tex (转换TEX)"].get(),
            "copyproject": self.options["-c, --copyproject (复制项目文件)"].get(),
            "usename": self.options["-n, --usename (使用项目名)"].get(),
            "overwrite": self.options["--overwrite (覆盖现有文件)"].get(),
            "recursive": self.options["-r, --recursive (递归搜索)"].get(),
            "copy_preview": self.python_options["复制预览图像 (preview.*)"].get(),
            "auto_backup": self.python_options["原地替换模式自动备份"].get(),
        })
        
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
        messagebox.showinfo("保存成功", f"配置已保存到 {CONFIG_FILE}")
    
    # ------------------------------------------------------------
    #  命令生成（确保Windows路径）
    # ------------------------------------------------------------
    def build_command(self, pkg_path):
        exe_path = self.repkg_path.get().strip()
        if not os.path.isfile(exe_path):
            raise FileNotFoundError(f"未找到 RePKG 可执行文件: {exe_path}")
        
        project_name = self.get_project_name(pkg_path)
        output_root = self.output_entry.get().strip() or "./output"
        output_dir = os.path.join(output_root, project_name)
        os.makedirs(output_dir, exist_ok=True)
        
        # 使用 Windows 路径（反斜杠 + 引号）
        cmd = [win_path(exe_path), self.mode.get()]
        for key, var in self.options.items():
            if var.get():
                # 提取选项参数
                if ',' in key:
                    option = key.split(',')[0].strip()
                else:
                    option = key.split(' (')[0].strip()
                cmd.append(option)
        
        cmd += ["-o", win_path(output_dir), win_path(pkg_path)]
        return cmd
    
    # ------------------------------------------------------------
    #  扫描 .pkg 文件
    # ------------------------------------------------------------
    def scan_pkg_files(self, root_dir):
        pkg_list = []
        # 根据 -r, --recursive 选项判断是否递归搜索
        recursive = self.options["-r, --recursive (递归搜索)"].get()
        
        # glob.iglob 在 Python 3.5+ 支持 recursive=True
        # 但是 os.walk 更可靠且不需要依赖版本
        for dirpath, _, filenames in os.walk(root_dir):
            for f in filenames:
                if f.lower().endswith(".pkg"):
                    pkg_list.append(os.path.join(dirpath, f))
            
            # 如果不递归，跳过子目录
            if not recursive:
                break  # 只处理一层目录
        
        return pkg_list
    
    def get_project_name(self, pkg_path):
        """获取项目名称（pkg文件所在目录的名称）"""
        pkg_dir = os.path.dirname(pkg_path)
        # 如果是递归搜索，项目名是相对于输入根目录的路径，但RePKG默认使用pkg所在目录名作为项目名，这里保持一致
        return os.path.basename(pkg_dir)
    
    def find_preview_image(self, pkg_path):
        """查找与pkg文件同级的preview图像文件"""
        pkg_dir = os.path.dirname(pkg_path)
        pkg_name = os.path.splitext(os.path.basename(pkg_path))[0]
        
        # 支持的图像格式
        image_extensions = ['*.png', '*.jpg', '*.jpeg', '*.gif', '*.bmp', '*.tiff', '*.webp']
        
        # 查找preview开头的图像文件
        for ext in image_extensions:
            pattern = os.path.join(pkg_dir, f"preview{ext}")
            matches = glob.glob(pattern, recursive=False)
            if matches:
                return matches[0]  # 返回第一个匹配的文件
        
        # 如果没找到preview开头的，查找与pkg同名的图像文件
        for ext in image_extensions:
            pattern = os.path.join(pkg_dir, f"{pkg_name}{ext}")
            matches = glob.glob(pattern, recursive=False)
            if matches:
                return matches[0]
        
        return None
    
    def copy_preview_image(self, pkg_path, output_dir):
        """
        拷贝预览图像到输出目录，并同步拷贝 project.json
        - 拷贝 preview 图像只有在 options 启用时发生
        - project.json 始终同步拷贝
        """
        success_preview = False
        
        # 拷贝 preview 图像（受选项控制）
        if self.python_options["复制预览图像 (preview.*)"].get():
            preview_path = self.find_preview_image(pkg_path)
            if preview_path:
                try:
                    os.makedirs(output_dir, exist_ok=True)
                    # 获取预览图像的文件名和扩展名
                    preview_filename = os.path.basename(preview_path)
                    preview_name, preview_ext = os.path.splitext(preview_filename)
                    # 如果预览图像不是preview开头，重命名为preview
                    if not preview_name.lower().startswith('preview'):
                        preview_filename = f"preview{preview_ext}"
                    dest_path = os.path.join(output_dir, preview_filename)
                    shutil.copy2(preview_path, dest_path)
                    success_preview = True
                except Exception as e:
                    self.log_box.insert(tk.END, f"[Error] 拷贝预览图像失败: {e}\n")
        
        # 无论是否拷贝preview，总是尝试同步拷贝 project.json
        try:
            pkg_dir = os.path.dirname(pkg_path)
            project_json_src = os.path.join(pkg_dir, "project.json")
            if os.path.isfile(project_json_src):
                os.makedirs(output_dir, exist_ok=True)
                dest_project_json = os.path.join(output_dir, "project.json")
                shutil.copy2(project_json_src, dest_project_json)
        except Exception as e:
            self.log_box.insert(tk.END, f"[Error] 同步拷贝 project.json 失败: {e}\n")
        
        return success_preview
    
    # ------------------------------------------------------------
    #  执行批量任务
    # ------------------------------------------------------------
    def start_task(self):
        input_dir = self.input_entry.get().strip()
        output_dir = self.output_entry.get().strip()
        
        if not os.path.isdir(input_dir):
            messagebox.showerror("错误", "请输入有效的输入目录！")
            return
        
        if not output_dir:
            messagebox.showerror("错误", "请输入有效的输出目录！")
            return
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        pkg_files = self.scan_pkg_files(input_dir)
        if not pkg_files:
            messagebox.showinfo("提示", "未找到任何 .pkg 文件。")
            return
        
        self.log_box.delete(1.0, tk.END)
        self.log_box.insert(tk.END,
                            f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 发现 {len(pkg_files)} 个 .pkg 文件，开始处理...\n\n")
        
        self.update_preview(pkg_files[0])
        threading.Thread(target=self.run_batch, args=(pkg_files,), daemon=True).start()
    
    def execute_extraction(self, pkg_path, output_dir):
        """执行 repkg 提取命令并实时输出日志 / Execute extraction command and stream logs"""
        cmd = self.build_command(pkg_path)
        self.log_box.insert(tk.END, f"  → 执行命令: {' '.join(cmd)}\n")
        if self.auto_scroll:
            self.log_box.see(tk.END)
        
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="ignore"
        )
        
        for line in process.stdout:
            self.log_box.insert(tk.END, line)
            if self.auto_scroll:
                self.log_box.see(tk.END)
        
        process.wait()
        
        self.log_box.insert(tk.END, f"  ✅ 完成 {os.path.basename(pkg_path)} (退出码 {process.returncode})\n")
        if self.auto_scroll:
            self.log_box.see(tk.END)
        
        # 拷贝预览图像 / Copy preview image if enabled
        if self.copy_preview_image(pkg_path, output_dir):
            self.log_box.insert(tk.END, f"  📷 已拷贝预览图像到 {output_dir}\n")
        
        self.log_box.insert(tk.END, "\n")
        if self.auto_scroll:
            self.log_box.see(tk.END)
    
    def run_batch(self, pkg_files):
        """批量运行主逻辑 / Main entry for batch execution"""
        output_dir_root = self.output_entry.get().strip()
        
        for i, pkg_path in enumerate(pkg_files, 1):
            project_name = self.get_project_name(pkg_path)
            output_dir = os.path.join(output_dir_root, project_name)
            
            self.log_box.insert(tk.END, f"[{i}/{len(pkg_files)}] 📦 处理项目: {project_name}\n")
            if self.auto_scroll:
                self.log_box.see(tk.END)
            
            # 提取执行
            try:
                self.execute_extraction(pkg_path, output_dir)
            except Exception as e:
                self.log_box.insert(tk.END, f"  [Error] 执行出错: {e}\n\n")
                if self.auto_scroll:
                    self.log_box.see(tk.END)
        
        self.log_box.insert(tk.END, f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ✅ 所有任务完成！\n")
        if self.auto_scroll:
            self.log_box.see(tk.END)
    
    # ------------------------------------------------------------
    #  命令预览（Windows 格式）
    # ------------------------------------------------------------
    def update_preview(self, sample_pkg=None):
        try:
            if sample_pkg:
                cmd = self.build_command(sample_pkg)
            else:
                # 尝试构建一个更有意义的预览路径
                input_dir = self.input_entry.get().strip()
                output_dir = self.output_entry.get().strip()
                
                if input_dir and os.path.exists(input_dir):
                    # 尝试找到第一个 .pkg 文件作为样本 (不进行递归扫描，太耗时)
                    pkg_files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if
                                 f.lower().endswith(".pkg") and os.path.isfile(os.path.join(input_dir, f))]
                    if pkg_files:
                        cmd = self.build_command(pkg_files[0])
                else:
                    # 使用默认的假路径
                    fake_pkg = r"D:\Games\Steam\steamapps\workshop\content\431960\111111111\scene.pkg"
                    cmd = self.build_command(fake_pkg)
            
            self.cmd_preview.delete(1.0, tk.END)
            self.cmd_preview.insert(tk.END, " ".join(cmd))
        except Exception as e:
            pass  # 静默处理预览错误，避免干扰用户


if __name__ == "__main__":
    root = tk.Tk()
    app = RePKG_GUI(root)
    root.mainloop()