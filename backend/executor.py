"""
RePKG 执行器模块
按项目转换，详细日志输出
包含预览图像拷贝功能
支持 scene、video、web、application 类型项目
"""
import os
import subprocess
import threading
import time
import shutil
import glob
from typing import List, Optional
from dataclasses import dataclass


class ExtractOptions:
    """提取选项"""

    def __init__(self, convert_tex: bool = True, copy_project: bool = True,
                 overwrite: bool = False, recursive: bool = True, copy_preview: bool = True):
        self.convert_tex = convert_tex
        self.copy_project = copy_project
        self.overwrite = overwrite
        self.recursive = recursive
        self.copy_preview = copy_preview  # 拷贝预览图像

    def to_dict(self) -> dict:
        """转换为字典用于日志"""
        return {
            "convertTex": self.convert_tex,
            "copyProject": self.copy_project,
            "overwrite": self.overwrite,
            "recursive": self.recursive,
            "copyPreview": self.copy_preview
        }


@dataclass
class ProjectInfo:
    """项目信息"""
    name: str
    title: Optional[str]
    workshop_id: Optional[str]
    pkg_path: str
    pkg_size: int
    dir_name: str
    dir_path: str  # 项目目录完整路径
    # 项目类型标识
    is_scene: bool = False        # 是否为场景类型（需要 RePKG 提取）
    is_video: bool = False        # 是否为视频类型（直接复制）
    is_web: bool = False         # 是否为 Web 类型（直接复制）
    is_application: bool = False  # 是否为应用程序类型（直接复制）
    video_file: Optional[str] = None  # 视频文件路径（仅视频类型）


class RePKGExecutor:
    """RePKG 执行器"""

    def __init__(self, input_dir: str, output_dir: str, repkg_path: str, options: ExtractOptions, targets: list = None):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.repkg_path = repkg_path
        self.options = options
        self.targets = targets  # 可选：只处理指定的项目（按 dir_path 匹配）
        self._stop_event = threading.Event()
        self._progress = 0
        self._current_file = ""
        self._logs: List[dict] = []
        self._is_running = False
        self._start_time = None
        self._processed_count = 0
        self._success_count = 0
        self._failed_count = 0

    def is_running(self) -> bool:
        return self._is_running

    def get_progress(self) -> int:
        return self._progress

    def get_current_file(self) -> str:
        return self._current_file

    def get_logs(self) -> List[dict]:
        return self._logs.copy()

    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        return time.strftime("%H:%M:%S")

    def _add_log(self, level: str, message: str, detail: str = ""):
        """添加日志"""
        log_entry = {
            "level": level,
            "message": message,
            "detail": detail,
            "timestamp": self._get_timestamp()
        }
        self._logs.append(log_entry)
        if len(self._logs) > 500:
            self._logs = self._logs[-500:]

    def start(self):
        """启动提取任务（异步）"""
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()

    def _run(self):
        """执行提取任务"""
        self._is_running = True
        self._progress = 0
        self._logs = []
        self._start_time = time.time()
        self._processed_count = 0
        self._success_count = 0
        self._failed_count = 0

        # 记录开始信息
        self._add_log("info", "╔" + "═" * 48 + "╗")
        self._add_log("info", "║" + " " * 15 + "开始提取任务" + " " * 15 + "║")
        self._add_log("info", "╚" + "═" * 48 + "╝")
        self._add_log("info", "")
        self._add_log("info", "【配置信息】")
        self._add_log("info", f"  输入目录: {self.input_dir}")
        self._add_log("info", f"  输出目录: {self.output_dir}")
        self._add_log("info", f"  RePKG路径: {self.repkg_path}")

        # 记录选项
        opts = self.options.to_dict()
        opt_strs = [k for k, v in opts.items() if v]
        self._add_log("info", f"  提取选项: {', '.join(opt_strs) if opt_strs else '无'}")
        self._add_log("info", "")

        # 检查 RePKG
        if not os.path.isfile(self.repkg_path):
            self._add_log("error", "RePKG.exe 未找到")
            self._add_log("error", f"  路径: {self.repkg_path}")
            self._add_log("error", "  请确保 RePKG.exe 存在于指定路径")
            self._is_running = False
            return

        self._add_log("success", "RePKG.exe 已就绪")
        self._add_log("info", "")

        from .scanner import FileScanner
        scanner = FileScanner(self.input_dir, recursive=self.options.recursive)
        pkg_files = scanner.scan()

        # 如果指定了 targets，只处理匹配的项目
        if self.targets:
            pkg_files = [f for f in pkg_files if f.dir_path in self.targets]
            self._add_log("info", f"  指定提取: {len(pkg_files)} 个项目")

        if not pkg_files:
            self._add_log("warning", "未找到任何项目文件")
            self._add_log("warning", f"  请检查输入目录: {self.input_dir}")
            self._is_running = False
            return

        total = len(pkg_files)
        total_size = sum(f.size for f in pkg_files)

        # 统计项目类型
        scene_count = sum(1 for f in pkg_files if f.is_scene)
        video_count = sum(1 for f in pkg_files if f.is_video)
        web_count = sum(1 for f in pkg_files if f.is_web)
        application_count = sum(1 for f in pkg_files if f.is_application)

        self._add_log("info", "【扫描结果】")
        self._add_log("info", f"  发现项目: {total} 个")
        if scene_count > 0:
            self._add_log("info", f"  场景类型: {scene_count} 个")
        if video_count > 0:
            self._add_log("info", f"  视频类型: {video_count} 个")
        if web_count > 0:
            self._add_log("info", f"  Web 类型: {web_count} 个")
        if application_count > 0:
            self._add_log("info", f"  应用程序类型: {application_count} 个")
        self._add_log("info", f"  总大小: {self._format_size(total_size)}")
        self._add_log("info", "")

        os.makedirs(self.output_dir, exist_ok=True)
        self._add_log("success", "输出目录已准备")
        self._add_log("info", "")
        self._add_log("info", "╔" + "═" * 48 + "╗")
        self._add_log("info", "║" + " " * 15 + "开始处理项目" + " " * 15 + "║")
        self._add_log("info", "╚" + "═" * 48 + "╝")
        self._add_log("info", "")

        for i, pkg_file in enumerate(pkg_files):
            if self._stop_event.is_set():
                self._add_log("warning", "任务被用户停止")
                break

            self._progress = int((i + 1) / total * 100)
            self._current_file = pkg_file.name
            self._processed_count += 1

            # 构建项目信息
            project_info = ProjectInfo(
                name=pkg_file.name,
                title=pkg_file.title,
                workshop_id=pkg_file.workshop_id,
                pkg_path=pkg_file.path,
                pkg_size=pkg_file.size,
                dir_name=pkg_file.dir_name,
                dir_path=pkg_file.dir_path,
                is_scene=pkg_file.is_scene,
                is_video=pkg_file.is_video,
                is_web=pkg_file.is_web,
                is_application=pkg_file.is_application,
                video_file=pkg_file.video_file
            )

            # 输出项目详细信息
            self._add_log("info", f"【项目 {i + 1}/{total}】")
            if project_info.is_scene:
                self._add_log("info", f"  类型: 📦 场景项目")
            elif project_info.is_video:
                self._add_log("info", f"  类型: 📹 视频项目")
            elif project_info.is_web:
                self._add_log("info", f"  类型: 🌐 Web 项目")
            elif project_info.is_application:
                self._add_log("info", f"  类型: 📱 应用程序")
            else:
                self._add_log("info", f"  类型: 未知")
            if project_info.title:
                self._add_log("info", f"  名称: {project_info.title}")
            else:
                self._add_log("info", f"  文件: {project_info.name}")
            if project_info.workshop_id:
                self._add_log("info", f"  Workshop ID: {project_info.workshop_id}")
            self._add_log("info", f"  目录: {project_info.dir_name}")
            self._add_log("info", f"  大小: {self._format_size(project_info.pkg_size)}")

            start_time = time.time()

            # 根据项目类型选择处理方法
            if project_info.is_scene:
                success = self._extract_scene(pkg_file, project_info)
            else:
                # video、web、application 类型都直接复制
                success = self._copy_project(pkg_file, project_info)

            elapsed = time.time() - start_time

            if success:
                self._success_count += 1
                self._add_log("success", f"  ✓ 处理成功", f"耗时: {elapsed:.2f}秒")
            else:
                self._failed_count += 1
                self._add_log("error", f"  ✗ 处理失败", f"耗时: {elapsed:.2f}秒")

            self._add_log("info", "")

        self._is_running = False
        self._progress = 100
        self._current_file = ""

        # 记录完成信息
        elapsed = time.time() - self._start_time
        self._add_log("info", "╔" + "═" * 48 + "╗")
        self._add_log("info", "║" + " " * 15 + "任务完成统计" + " " * 15 + "║")
        self._add_log("info", "╚" + "═" * 48 + "╝")
        self._add_log("info", "")
        self._add_log("info", f"  处理项目: {self._processed_count} 个")
        self._add_log("success", f"  成功: {self._success_count} 个")
        if self._failed_count > 0:
            self._add_log("error", f"  失败: {self._failed_count} 个")
        self._add_log("info", f"  总耗时: {elapsed:.2f} 秒")
        if self._success_count > 0:
            avg_time = elapsed / self._success_count
            self._add_log("info", f"  平均耗时: {avg_time:.2f} 秒/项目")
        self._add_log("info", "")
        self._add_log("success", "提取任务已完成")

    def _extract_scene(self, pkg_file, project_info: ProjectInfo) -> bool:
        """提取场景类型项目（使用 RePKG）

        RePKG 命令参数说明：
        -o, --output     输出目录
        -t, --tex        转换 TEX 文件为图像
        -c, --copyproject 复制 project.json 和 preview.jpg（自动）
        -n, --usename    使用 project.json 中的 name 字段作为子文件夹名（不使用）
        -s, --singledir  所有文件放到一个目录
        --overwrite      覆盖现有文件
        --no-tex-convert 不转换 TEX 文件

        注意：-n 选项需要 project.json 中有 "name" 字段才能工作，但大多数项目只有 "title" 字段。
        因此我们手动创建子目录（使用 Workshop ID）。
        """
        try:
            # 手动创建项目子目录（使用 Workshop ID）
            project_output_dir = os.path.join(self.output_dir, project_info.dir_name)
            os.makedirs(project_output_dir, exist_ok=True)

            cmd = [self.repkg_path, "extract"]

            # 核心选项
            if self.options.convert_tex:
                cmd.append("-t")  # 转换 TEX 为图像

            if self.options.copy_project:
                cmd.append("-c")  # 复制 project.json 和 preview.jpg

            # 不使用 -n 选项，因为大多数 project.json 没有 name 字段
            # 手动创建子目录

            if self.options.overwrite:
                cmd.append("--overwrite")

            # 输出到项目子目录
            cmd.extend(["-o", project_output_dir, pkg_file.path])

            # 记录执行命令
            cmd_str = ' '.join(cmd)
            self._add_log("debug", f"  执行: {cmd_str}")
            self._add_log("debug", f"  输出到: {project_output_dir}")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode != 0:
                if result.stderr:
                    for line in result.stderr.strip().split('\n'):
                        if line.strip():
                            self._add_log("error", f"    错误: {line.strip()}")
                return False

            # 输出成功信息
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        if 'extracting' in line.lower() or 'writing' in line.lower():
                            self._add_log("debug", f"    {line.strip()}")
                        elif 'success' in line.lower() or 'complete' in line.lower():
                            self._add_log("success", f"    {line.strip()}")

            # 补充拷贝其他格式的预览图像（如 gif, webp 等）
            # -c 选项只复制 preview.jpg，这里补充其他格式
            if self.options.copy_preview:
                self._copy_additional_preview(pkg_file, project_info, project_output_dir)

            return True

        except subprocess.TimeoutExpired:
            self._add_log("error", "  处理超时（超过300秒）")
            return False
        except FileNotFoundError:
            self._add_log("error", f"  RePKG 未找到: {self.repkg_path}")
            return False
        except Exception as e:
            self._add_log("error", f"  处理异常: {str(e)}")
            return False

    def _copy_project(self, pkg_file, project_info: ProjectInfo) -> bool:
        """复制项目目录（video/web/application 类型，直接复制）

        处理逻辑：
        1. 直接复制整个项目目录到输出目录
        2. 保留所有文件结构（视频文件、HTML文件、project.json、预览图等）
        """
        try:
            # 创建项目输出目录
            project_output_dir = os.path.join(self.output_dir, project_info.dir_name)

            # 检查是否已存在
            if os.path.exists(project_output_dir):
                if self.options.overwrite:
                    self._add_log("debug", f"  目标目录已存在，将覆盖")
                    shutil.rmtree(project_output_dir)
                else:
                    self._add_log("warning", f"  目标目录已存在，跳过")
                    return True

            self._add_log("debug", f"  复制目录: {project_info.dir_path}")
            self._add_log("debug", f"  输出到: {project_output_dir}")

            # 复制整个目录
            shutil.copytree(project_info.dir_path, project_output_dir)

            # 计算复制的文件数量
            copied_files = sum(1 for _ in os.walk(project_output_dir) for _ in os.listdir(_[0]))
            self._add_log("info", f"  📁 已复制 {copied_files} 个文件")

            return True

        except Exception as e:
            self._add_log("error", f"  复制失败: {str(e)}")
            return False

    def _find_preview_image(self, pkg_file) -> Optional[str]:
        """查找预览图像文件

        优先级：
        1. pkg_file.preview_path（从 project.json 解析）
        2. preview.* 文件
        3. 其他常见预览图名称
        """
        # 优先使用 scanner 解析的预览图路径（来自 project.json）
        if pkg_file.preview_path and os.path.isfile(pkg_file.preview_path):
            return pkg_file.preview_path

        pkg_dir = os.path.dirname(pkg_file.path)
        pkg_name = os.path.splitext(pkg_file.name)[0]

        # 支持的图像格式
        image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp']

        # 查找 preview 开头的图像文件
        for ext in image_extensions:
            preview_path = os.path.join(pkg_dir, f"preview{ext}")
            if os.path.isfile(preview_path):
                return preview_path

        # 如果没找到 preview 开头的，查找与 pkg 同名的图像文件
        for ext in image_extensions:
            same_name_path = os.path.join(pkg_dir, f"{pkg_name}{ext}")
            if os.path.isfile(same_name_path):
                return same_name_path

        # 尝试其他常见预览图名称
        common_names = ['thumb', 'thumbnail', 'cover', 'icon']
        for name in common_names:
            for ext in image_extensions:
                path = os.path.join(pkg_dir, f"{name}{ext}")
                if os.path.isfile(path):
                    return path

        return None

    def _copy_additional_preview(self, pkg_file, project_info: ProjectInfo, project_output_dir: str) -> bool:
        """拷贝预览图像到项目输出目录

        处理逻辑：
        1. -c 选项会自动复制 project.json 和 preview.jpg（如果存在）
        2. 这里拷贝 project.json 中指定的预览图（可能是 gif, webp, png 等）
        3. 如果预览图是 jpg/jpeg，且 -c 已复制，则跳过
        """
        preview_path = self._find_preview_image(pkg_file)
        if not preview_path:
            self._add_log("debug", "  未找到预览图像")
            return False

        # 获取预览图像扩展名
        preview_ext = os.path.splitext(preview_path)[1].lower()
        preview_filename = os.path.basename(preview_path)

        try:
            # 直接使用传入的项目输出目录
            if not os.path.exists(project_output_dir):
                self._add_log("warning", f"  找不到项目输出目录: {project_output_dir}")
                return False

            # 构建目标路径
            dest_path = os.path.join(project_output_dir, preview_filename)

            # 检查是否需要拷贝
            should_copy = True

            # jpg/jpeg 可能已被 -c 选项复制
            if preview_ext in ['.jpg', '.jpeg']:
                if os.path.exists(dest_path):
                    # 已存在，检查是否相同
                    if os.path.getsize(dest_path) == os.path.getsize(preview_path):
                        should_copy = False
                        self._add_log("debug", f"  预览图已存在: {preview_filename}")
                    elif not self.options.overwrite:
                        should_copy = False
                        self._add_log("debug", f"  预览图已存在（不同），跳过覆盖")

            if should_copy:
                shutil.copy2(preview_path, dest_path)
                self._add_log("info", f"  📷 已拷贝预览图: {preview_filename}")
            return True

        except Exception as e:
            self._add_log("warning", f"  拷贝预览图失败: {str(e)}")
            return False

    @staticmethod
    def _format_size(size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def stop(self):
        """停止提取任务"""
        self._add_log("warning", "正在停止任务...")
        self._stop_event.set()
