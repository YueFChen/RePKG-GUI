"""
文件扫描模块
性能优化版本
支持 scene、video、web、application 类型项目
"""
import os
import glob
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from functools import lru_cache


@dataclass
class PkgFile:
    """项目文件信息"""
    path: str
    name: str
    size: int
    dir_name: str
    dir_path: str  # 项目目录完整路径
    preview_path: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    item_type: Optional[str] = None  # 'scene', 'video', 'web', 'application'
    version: Optional[int] = None
    workshop_id: Optional[str] = None
    workshop_url: Optional[str] = None
    schemecolor: Optional[str] = None
    content_rating: Optional[str] = None
    # 项目类型标识
    is_scene: bool = False       # 是否为场景类型（需要 RePKG 提取）
    is_video: bool = False       # 是否为视频类型（直接复制）
    is_web: bool = False         # 是否为 Web 类型（直接复制）
    is_application: bool = False  # 是否为应用程序类型（直接复制）
    # 特定类型文件路径
    video_file: Optional[str] = None  # 视频文件路径（仅视频类型）


# 缓存 project.json 解析结果（按文件路径缓存）
@lru_cache(maxsize=512)
def parse_project_json_cached(dir_path: str) -> Dict[str, Any]:
    """解析 project.json（带缓存）

    预览图查找优先级：
    1. project.json 中的 preview 字段（如 "preview.gif"）
    2. 目录下的 preview.* 文件
    3. 与目录名同名的图像文件
    4. 其他常见预览图名称（thumb, thumbnail, cover, icon）

    项目类型识别（统一使用 type 字段）：
    - type == 'scene' → 场景项目（需要 RePKG 提取）
    - type == 'video' → 视频项目（直接复制）
    - type == 'web' → Web 项目（直接复制）
    - type == 'application' → 应用程序项目（直接复制）
    """
    result = {
        'preview_path': None,
        'title': None,
        'description': None,
        'tags': None,
        'type': None,
        'version': None,
        'workshop_id': None,
        'workshop_url': None,
        'schemecolor': None,
        'content_rating': None,
        'is_scene': False,
        'is_video': False,
        'is_web': False,
        'is_application': False,
        'video_file': None,
        'dir_size': 0
    }

    project_json_path = os.path.join(dir_path, 'project.json')
    if not os.path.exists(project_json_path):
        # 没有 project.json，按模式查找预览图和视频文件
        result['preview_path'] = _find_preview_by_pattern_cached(dir_path)
        result['video_file'] = _find_video_file_cached(dir_path)
        result['is_video'] = result['video_file'] is not None
        result['dir_size'] = _get_dir_size_cached(dir_path)
        return result

    try:
        with open(project_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

            # 基本信息
            result['title'] = data.get('title') or data.get('name')
            result['description'] = data.get('description')
            result['tags'] = data.get('tags', [])
            result['type'] = data.get('type')
            result['version'] = data.get('version')
            result['workshop_id'] = data.get('workshopid')
            result['workshop_url'] = data.get('workshopurl')
            result['content_rating'] = data.get('contentrating')

            # 判断项目类型（统一使用 type 字段）
            project_type = data.get('type', '')
            result['is_scene'] = project_type == 'scene'
            result['is_video'] = project_type == 'video'
            result['is_web'] = project_type == 'web'
            result['is_application'] = project_type == 'application'

            # 预览图：优先使用 project.json 中指定的路径
            preview_rel = data.get('preview')
            if preview_rel:
                preview_path = os.path.join(dir_path, preview_rel)
                if os.path.exists(preview_path):
                    result['preview_path'] = preview_path
                else:
                    preview_base = os.path.splitext(preview_rel)[0]
                    for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp']:
                        alt_path = os.path.join(dir_path, preview_base + ext)
                        if os.path.exists(alt_path):
                            result['preview_path'] = alt_path
                            break

            # 视频文件路径（仅视频类型）
            if result['is_video']:
                # 从 project.json 中获取视频文件名
                general = data.get('general', {})
                properties = general.get('properties', {})
                video_prop = properties.get('video', {})
                video_file_rel = video_prop.get('value') or data.get('file')
                if video_file_rel:
                    video_path = os.path.join(dir_path, video_file_rel)
                    if os.path.exists(video_path):
                        result['video_file'] = video_path
                # 如果没有指定，查找目录中的视频文件
                if not result['video_file']:
                    result['video_file'] = _find_video_file_cached(dir_path)

            # 主题颜色
            general = data.get('general', {})
            properties = general.get('properties', {})
            if 'schemecolor' in properties:
                result['schemecolor'] = properties['schemecolor'].get('value')

    except Exception:
        pass

    # 如果 project.json 中没有 preview 字段或文件不存在，按模式查找
    if not result['preview_path']:
        result['preview_path'] = _find_preview_by_pattern_cached(dir_path)

    # 如果没有找到视频文件但类型是 video，再次查找
    if result['is_video'] and not result['video_file']:
        result['video_file'] = _find_video_file_cached(dir_path)

    # 计算目录大小
    result['dir_size'] = _get_dir_size_cached(dir_path)

    return result


# 缓存预览图查找结果
@lru_cache(maxsize=1024)
def _find_preview_by_pattern_cached(dir_path: str) -> Optional[str]:
    """按文件名模式查找预览图（带缓存）"""
    dir_name = os.path.basename(dir_path)

    for ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif']:
        same_name = os.path.join(dir_path, dir_name + ext)
        if os.path.exists(same_name):
            return same_name

    patterns = ['preview.*', 'thumb.*', 'thumbnail.*', 'cover.*', 'icon.*']
    for pattern in patterns:
        matches = glob.glob(os.path.join(dir_path, pattern))
        if matches:
            return matches[0]

    return None


# 缓存视频文件查找结果
@lru_cache(maxsize=512)
def _find_video_file_cached(dir_path: str) -> Optional[str]:
    """查找目录中的视频文件（带缓存）"""
    video_extensions = ['.mp4', '.webm', '.mkv', '.avi', '.mov', '.wmv', '.flv']

    for ext in video_extensions:
        matches = glob.glob(os.path.join(dir_path, '*' + ext))
        if matches:
            return matches[0]

    return None


# 缓存目录大小计算
@lru_cache(maxsize=512)
def _get_dir_size_cached(dir_path: str) -> int:
    """计算目录大小（带缓存）"""
    total_size = 0
    try:
        for entry in os.scandir(dir_path):
            if entry.is_file():
                total_size += entry.stat().st_size
            elif entry.is_dir():
                for root, dirs, files in os.walk(entry.path):
                    for file in files:
                        total_size += os.path.getsize(os.path.join(root, file))
    except OSError:
        pass
    return total_size


# 缓存文件大小查询
@lru_cache(maxsize=4096)
def get_file_size_cached(path: str) -> int:
    """获取文件大小（带缓存）"""
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


class FileScanner:
    """文件扫描器"""

    def __init__(self, base_dir: str, recursive: bool = True):
        self.base_dir = base_dir
        self.recursive = recursive

    def scan(self) -> List[PkgFile]:
        """扫描目录下所有项目（统一使用 project.json 的 type 字段识别类型）"""
        if not os.path.isdir(self.base_dir):
            return []

        projects = []
        scanned_dirs = set()  # 防止重复扫描同一目录

        # 扫描所有 project.json 文件，根据 type 字段确定项目类型
        if self.recursive:
            for root, dirs, files in os.walk(self.base_dir):
                if 'project.json' in files:
                    project_info = parse_project_json_cached(root)
                    project_type = project_info.get('type', '')
                    if project_type in ('scene', 'video', 'web', 'application'):
                        scanned_dirs.add(root)
                        projects.append(self._create_project_from_info(root, project_info, project_type))
        else:
            if 'project.json' in os.listdir(self.base_dir):
                project_info = parse_project_json_cached(self.base_dir)
                project_type = project_info.get('type', '')
                if project_type in ('scene', 'video', 'web', 'application'):
                    projects.append(self._create_project_from_info(self.base_dir, project_info, project_type))

        return projects

    def _create_project_from_info(self, dir_path: str, project_info: Dict[str, Any], project_type: str) -> PkgFile:
        """根据项目信息创建项目对象"""
        video_file = project_info.get('video_file') if project_type == 'video' else None
        dir_size = project_info.get('dir_size', 0)

        # 场景类型使用 .pkg 文件路径，其他类型使用目录路径
        if project_type == 'scene':
            # 查找 .pkg 文件
            pkg_files = [f for f in os.listdir(dir_path) if f.endswith('.pkg')]
            pkg_path = os.path.join(dir_path, pkg_files[0]) if pkg_files else None
            path = pkg_path or dir_path
            name = os.path.basename(pkg_path) if pkg_path else os.path.basename(dir_path)
            size = get_file_size_cached(pkg_path) if pkg_path else dir_size
        else:
            path = video_file or dir_path
            name = os.path.basename(video_file) if video_file else os.path.basename(dir_path)
            size = dir_size

        return PkgFile(
            path=path,
            name=name,
            size=size,
            dir_name=os.path.basename(dir_path),
            dir_path=dir_path,
            preview_path=project_info.get('preview_path'),
            title=project_info.get('title'),
            description=project_info.get('description'),
            tags=project_info.get('tags'),
            item_type=project_type,
            version=project_info.get('version'),
            workshop_id=project_info.get('workshop_id'),
            workshop_url=project_info.get('workshop_url'),
            schemecolor=project_info.get('schemecolor'),
            content_rating=project_info.get('content_rating'),
            is_scene=project_type == 'scene',
            is_video=project_type == 'video',
            is_web=project_type == 'web',
            is_application=project_type == 'application',
            video_file=video_file
        )

    @staticmethod
    def format_size(size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"

    def get_summary(self, pkg_files: List[PkgFile]) -> Dict[str, Any]:
        """获取扫描摘要"""
        total_size = sum(f.size for f in pkg_files)
        return {
            "total_files": len(pkg_files),
            "total_size": total_size,
            "total_size_formatted": self.format_size(total_size)
        }


def clear_scanner_cache():
    """清除扫描缓存"""
    parse_project_json_cached.cache_clear()
    _find_preview_by_pattern_cached.cache_clear()
    _find_video_file_cached.cache_clear()
    _get_dir_size_cached.cache_clear()
    get_file_size_cached.cache_clear()
