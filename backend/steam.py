"""
Steam 路径检测模块
自动检测 Steam 安装路径和 Wallpaper Engine 相关路径
"""
import os
import re
import winreg


# Steam 注册表路径
STEAM_REG_KEYS = [
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),  # 64-bit
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam"),              # 32-bit
    (winreg.HKEY_CURRENT_USER, r"SOFTWARE\WOW6432Node\Valve\Steam"),
    (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Valve\Steam"),
]

# 常见 Steam 安装路径
STEAM_COMMON_PATHS = [
    r"C:\Program Files\Steam",
    r"C:\Program Files (x86)\Steam",
    r"D:\Steam",
    r"E:\Steam",
    r"F:\Steam",
    r"G:\Steam",
]

# Wallpaper Engine AppID
WALLPAPER_APPID = "431960"


def _get_steam_path_from_registry():
    """从注册表获取 Steam 安装路径"""
    for hkey, subkey in STEAM_REG_KEYS:
        try:
            with winreg.OpenKey(hkey, subkey, 0, winreg.KEY_READ) as key:
                install_path, _ = winreg.QueryValueEx(key, "InstallPath")
                if install_path and os.path.isdir(install_path):
                    if _is_valid_steam_path(install_path):
                        return install_path
        except (WindowsError, OSError):
            continue
    return None


def _get_steam_path_from_common_locations():
    """从常见路径获取 Steam 安装路径"""
    for path in STEAM_COMMON_PATHS:
        if _is_valid_steam_path(path):
            return path
    return None


def _is_valid_steam_path(steam_path):
    """验证是否是有效的 Steam 安装目录"""
    if not steam_path or not os.path.isdir(steam_path):
        return False

    # 检查关键文件
    required = ['steamapps', 'steam.exe']
    for item in required:
        if not os.path.exists(os.path.join(steam_path, item)):
            return False

    return True


def _parse_vdf_value(value: str) -> str:
    """解析 VDF 字符串值（处理引号和转义）"""
    if not value:
        return ""
    # 移除首尾引号
    value = value.strip('"')
    # 处理转义
    value = value.replace('\\\\', '\\')
    return value


def _parse_libraryfolders_vdf(vdf_path: str) -> list:
    """解析 libraryfolders.vdf 获取所有库路径"""
    paths = []

    if not os.path.isfile(vdf_path):
        return paths

    try:
        with open(vdf_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 匹配 "path" "实际路径" 模式
        pattern = r'"path"\s*"([^"]+)"'
        matches = re.findall(pattern, content)

        for match in matches:
            path = _parse_vdf_value(match)
            # 转换路径分隔符
            path = path.replace('\\\\', '\\')
            if os.path.isdir(path):
                paths.append(path)
    except (IOError, OSError):
        pass

    return paths


def _get_steam_library_paths(steam_path: str) -> list:
    """获取所有 Steam 库路径（包括主库和所有附加库）"""
    paths = []

    # 主 steamapps 目录
    main_steamapps = os.path.join(steam_path, 'steamapps')
    if os.path.isdir(main_steamapps):
        paths.append(main_steamapps)

    # 解析 libraryfolders.vdf 获取其他库
    library_vdf = os.path.join(main_steamapps, 'libraryfolders.vdf')
    extra_paths = _parse_libraryfolders_vdf(library_vdf)

    for extra_path in extra_paths:
        steamapps = os.path.join(extra_path, 'steamapps')
        if os.path.isdir(steamapps) and steamapps not in paths:
            paths.append(steamapps)

    return paths


def _parse_acf_file(acf_path: str) -> dict:
    """解析 ACF 文件获取游戏信息"""
    info = {
        'appid': None,
        'name': None,
        'installdir': None,
        'appstate': None
    }

    if not os.path.isfile(acf_path):
        return info

    try:
        with open(acf_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 解析关键字段
        patterns = {
            'appid': r'"appid"\s*"(\d+)"',
            'name': r'"name"\s*"([^"]+)"',
            'installdir': r'"installdir"\s*"([^"]+)"',
            'appstate': r'"appstate"\s*"(\d+)"'
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, content)
            if match:
                info[key] = match.group(1)
    except (IOError, OSError, UnicodeDecodeError):
        pass

    return info


def _find_app_in_steamapps(steamapps_path: str, appid: str) -> dict:
    """在 steamapps 目录中查找指定 AppID 的游戏"""
    result = {
        'found': False,
        'path': None,
        'name': None,
        'installdir': None
    }

    if not os.path.isdir(steamapps_path):
        return result

    # 查找所有 .acf 文件
    try:
        for filename in os.listdir(steamapps_path):
            if not filename.endswith('.acf'):
                continue

            acf_path = os.path.join(steamapps_path, filename)
            info = _parse_acf_file(acf_path)

            if info['appid'] == appid:
                result['found'] = True
                result['name'] = info['name']
                result['installdir'] = info['installdir']

                # 构建完整路径
                if result['installdir']:
                    result['path'] = os.path.join(steamapps_path, 'common', result['installdir'])
                break
    except (OSError, PermissionError):
        pass

    return result


def get_steam_path():
    """
    获取 Steam 安装路径
    优先级：注册表 > 常见路径
    """
    # 首先尝试注册表
    path = _get_steam_path_from_registry()
    if path:
        return path

    # 降级到常见路径
    path = _get_steam_path_from_common_locations()
    if path:
        return path

    return None


def detect_steam_paths():
    """
    自动检测 Steam 路径
    返回: dict {
        'steam_path': str,           # Steam 主目录
        'workshop_path': str,        # 创意工坊内容目录
        'wallpaper_projects': str,   # Wallpaper Engine 项目目录
        'wallpaper_projects_my': str # 我的项目目录
    }
    """
    result = {
        'steam_path': None,
        'workshop_path': None,
        'wallpaper_projects': None,
        'wallpaper_projects_my': None,
        'wallpaper_found': False,
        'wallpaper_info': None
    }

    steam_path = get_steam_path()
    if not steam_path:
        return result

    # 获取所有库路径
    library_paths = _get_steam_library_paths(steam_path)

    # 在所有库中查找 Wallpaper Engine
    for steamapps in library_paths:
        info = _find_app_in_steamapps(steamapps, WALLPAPER_APPID)
        if info['found']:
            result['steam_path'] = steam_path
            result['wallpaper_found'] = True
            result['wallpaper_info'] = {
                'name': info['name'],
                'path': info['path'],
                'installdir': info['installdir']
            }
            # Wallpaper Engine 的 workshop 路径在 steamapps/workshop/content 下
            result['workshop_path'] = os.path.join(steamapps, 'workshop', 'content', WALLPAPER_APPID)
            result['wallpaper_projects'] = os.path.join(info['path'], 'projects')
            result['wallpaper_projects_my'] = os.path.join(result['wallpaper_projects'], 'myprojects')
            break

    # 如果没找到 Wallpaper Engine，使用默认位置
    if not result['wallpaper_found']:
        main_steamapps = os.path.join(steam_path, 'steamapps')
        result['workshop_path'] = os.path.join(main_steamapps, 'workshop', 'content', WALLPAPER_APPID)
        result['wallpaper_projects'] = None
        result['wallpaper_projects_my'] = None

    return result


def get_steam_library_paths() -> list:
    """获取所有 Steam 库路径"""
    steam_path = get_steam_path()
    if not steam_path:
        return []

    return _get_steam_library_paths(steam_path)


def list_installed_games() -> list:
    """列出所有已安装的游戏"""
    games = []
    steam_path = get_steam_path()

    if not steam_path:
        return games

    library_paths = _get_steam_library_paths(steam_path)

    for steamapps in library_paths:
        try:
            for filename in os.listdir(steamapps):
                if not filename.endswith('.acf'):
                    continue

                acf_path = os.path.join(steamapps, filename)
                info = _parse_acf_file(acf_path)

                if info['appid']:
                    games.append({
                        'appid': info['appid'],
                        'name': info['name'],
                        'installdir': info['installdir'],
                        'steamapps_path': steamapps
                    })
        except (OSError, PermissionError):
            continue

    return games


def validate_workshop_path(path: str) -> bool:
    """验证是否是有效的 Wallpaper Engine 创意工坊路径"""
    if not path or not os.path.isdir(path):
        return False

    try:
        for item in os.listdir(path):
            if item.endswith('.pkg'):
                return True
    except PermissionError:
        pass

    return False


def get_workshop_subdirs(path: str) -> list:
    """获取创意工坊目录下的所有子目录（每个子目录是一个项目）"""
    if not path or not os.path.isdir(path):
        return []

    subdirs = []
    try:
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path):
                try:
                    if any(f.endswith('.pkg') for f in os.listdir(item_path)):
                        subdirs.append(item_path)
                except PermissionError:
                    continue
    except PermissionError:
        pass

    return subdirs
