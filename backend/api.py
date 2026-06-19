"""
Backend API 模块
处理所有后端业务逻辑
"""
import os
import json
import shutil
import subprocess
from flask import request, jsonify, Response, send_file
from backend.scanner import FileScanner
from backend.executor import RePKGExecutor, ExtractOptions
from backend.config import get_config, save_config, update_steam
from backend.steam import detect_steam_paths, validate_workshop_path, get_workshop_subdirs
from backend.paths import get_app_dir


# ==================== 配置 API ====================

def get_settings():
    """获取配置（用户配置 + Steam 检测路径）"""
    config = get_config()
    return jsonify({
        "success": True,
        "data": config.get_full_config()
    })


def save_settings():
    """保存用户配置"""
    data = request.get_json() or {}
    success, error = save_config(data)
    if success:
        return jsonify({"success": True})
    return jsonify({"success": False, "error": error})


# ==================== 扫描 API ====================

def scan_files():
    """扫描目录"""
    # 支持 GET（query params）和 POST（JSON body）
    if request.method == 'GET':
        input_path = request.args.get('path', '')
        recursive = request.args.get('recursive', 'true').lower() == 'true'
    else:
        data = request.get_json() or {}
        input_path = data.get('path') or data.get('inputPath', '')
        recursive = data.get('recursive', True)

    if not input_path:
        return jsonify({"success": False, "error": "输入路径不能为空"})

    if not os.path.isdir(input_path):
        return jsonify({"success": False, "error": "输入路径不存在"})

    scanner = FileScanner(input_path, recursive=recursive)
    pkg_files = scanner.scan()
    summary = scanner.get_summary(pkg_files)

    files_data = [
        {
            "path": f.path,
            "name": f.name,
            "size": f.size,
            "dir": f.dir_name,
            "dir_path": f.dir_path,
            "preview": f.preview_path,
            "title": f.title,
            "description": f.description,
            "tags": f.tags,
            "type": f.item_type,
            "version": f.version,
            "workshop_id": f.workshop_id,
            "schemecolor": f.schemecolor,
            "is_scene": f.is_scene,
            "is_video": f.is_video,
            "is_web": f.is_web,
            "is_application": f.is_application,
            "video_file": f.video_file
        }
        for f in pkg_files
    ]

    return jsonify({
        "success": True,
        "data": {
            "files": files_data,
            "summary": summary
        }
    })


# ==================== 输出目录管理 API ====================

def scan_output():
    """扫描输出目录中的项目"""
    data = request.get_json() or {}
    output_path = data.get('outputPath', '')

    if not output_path:
        return jsonify({"success": False, "error": "输出路径不能为空"})

    if not os.path.isdir(output_path):
        return jsonify({"success": False, "error": "输出路径不存在"})

    scanner = FileScanner(output_path, recursive=True)
    pkg_files = scanner.scan()
    summary = scanner.get_summary(pkg_files)

    files_data = [
        {
            "path": f.path,
            "name": f.name,
            "size": f.size,
            "dir": f.dir_name,
            "dir_path": f.dir_path,
            "preview": f.preview_path,
            "title": f.title,
            "description": f.description,
            "tags": f.tags,
            "type": f.item_type,
            "version": f.version,
            "workshop_id": f.workshop_id,
            "schemecolor": f.schemecolor,
            "is_scene": f.is_scene,
            "is_video": f.is_video,
            "is_web": f.is_web,
            "is_application": f.is_application,
            "video_file": f.video_file
        }
        for f in pkg_files
    ]

    return jsonify({
        "success": True,
        "data": {
            "files": files_data,
            "summary": summary
        }
    })


def delete_project():
    """删除输出目录中的项目"""
    data = request.get_json() or {}
    dir_paths = data.get('dirPaths', [])

    if not dir_paths:
        return jsonify({"success": False, "error": "未指定要删除的项目"})

    results = []
    for dir_path in dir_paths:
        if not os.path.isdir(dir_path):
            results.append({"path": dir_path, "success": False, "error": "目录不存在"})
            continue
        try:
            shutil.rmtree(dir_path)
            results.append({"path": dir_path, "success": True})
        except Exception as e:
            results.append({"path": dir_path, "success": False, "error": str(e)})

    deleted = sum(1 for r in results if r["success"])
    failed = len(results) - deleted
    return jsonify({
        "success": True,
        "data": {
            "total": len(results),
            "deleted": deleted,
            "failed": failed,
            "results": results
        }
    })

def serve_preview(filename):
    """提供预览图片访问"""
    # Windows 路径处理：确保使用正确的路径分隔符
    filename = filename.replace('/', os.sep).replace('\\', os.sep)
    if os.path.isfile(filename):
        return send_file(filename)
    return "", 404


# ==================== 提取任务 API ====================

current_executor = None


def start_extract():
    """开始提取任务"""
    global current_executor

    data = request.get_json() or {}
    input_path = data.get('inputPath', '')
    output_path = data.get('outputPath', '')
    repkg_path = data.get('repkgPath', './static/assets/RePKG.exe')
    options = data.get('options', {})
    targets = data.get('targets', None)  # 可选：指定要提取的项目列表

    if not input_path or not output_path:
        return jsonify({"success": False, "error": "路径不能为空"})

    # 解析 RePKG 绝对路径
    if not os.path.isabs(repkg_path):
        repkg_path = os.path.join(get_app_dir(), repkg_path)

    extract_options = ExtractOptions(
        convert_tex=options.get('convertTex', True),
        copy_project=options.get('copyProject', True),
        overwrite=options.get('overwrite', False),
        recursive=options.get('recursive', True),
        copy_preview=options.get('copyPreview', True)
    )

    current_executor = RePKGExecutor(input_path, output_path, repkg_path, extract_options, targets=targets)
    current_executor.start()

    return jsonify({"success": True, "message": "任务已开始"})


def get_extract_progress():
    """获取提取进度"""
    global current_executor

    if current_executor is None:
        return jsonify({
            "success": True,
            "data": {
                "isRunning": False,
                "progress": 0,
                "current": "",
                "logs": []
            }
        })

    return jsonify({
        "success": True,
        "data": {
            "isRunning": current_executor.is_running(),
            "progress": current_executor.get_progress(),
            "current": current_executor.get_current_file(),
            "logs": current_executor.get_logs()
        }
    })


def stream_logs():
    """SSE 流式日志"""
    global current_executor

    def generate():
        while True:
            if current_executor and current_executor.is_running():
                yield f"data: {json.dumps({'progress': current_executor.get_progress(), 'current': current_executor.get_current_file(), 'logs': current_executor.get_logs()})}\n\n"
            else:
                yield f"data: {json.dumps({'progress': 0, 'current': '', 'logs': []})}\n\n"

    return Response(generate(), mimetype='text/event-stream')


def stop_extract():
    """停止提取任务"""
    global current_executor

    if current_executor:
        current_executor.stop()
        current_executor = None

    return jsonify({"success": True})


# ==================== Steam 路径检测 API ====================

def detect_steam():
    """自动检测 Steam 路径"""
    paths = detect_steam_paths()
    # 更新全局配置的 Steam 检测路径
    update_steam(paths)
    return jsonify({
        "success": True,
        "data": paths
    })


def validate_path():
    """验证路径是否有效"""
    data = request.get_json() or {}
    path = data.get('path', '')
    path_type = data.get('type', 'workshop')

    if not path:
        return jsonify({"success": False, "error": "路径不能为空"})

    if path_type == 'workshop':
        valid = validate_workshop_path(path)
    else:
        valid = os.path.isdir(path)

    return jsonify({
        "success": True,
        "data": {"valid": valid}
    })


def get_subdirs():
    """获取目录下的子目录列表"""
    data = request.get_json() or {}
    path = data.get('path', '')

    if not path:
        return jsonify({"success": False, "error": "路径不能为空"})

    subdirs = get_workshop_subdirs(path)
    return jsonify({
        "success": True,
        "data": {"subdirs": subdirs}
    })


# ==================== 文件操作 API ====================

def clear_cache():
    """清除扫描缓存"""
    from .scanner import clear_scanner_cache
    clear_scanner_cache()
    return jsonify({"success": True, "message": "缓存已清除"})


# ==================== 背景图片 API ====================

BACKGROUND_DIR = os.path.join(get_app_dir(), 'static', 'assets', 'images', 'background')

DEFAULT_BACKGROUND_DIR = BACKGROUND_DIR  # 背景图片存储目录


def list_backgrounds():
    """列出所有可用背景图片"""
    try:
        os.makedirs(BACKGROUND_DIR, exist_ok=True)
        files = []
        for f in sorted(os.listdir(BACKGROUND_DIR)):
            fpath = os.path.join(BACKGROUND_DIR, f)
            if os.path.isfile(fpath) and f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp')):
                files.append({
                    "filename": f,
                    "size": os.path.getsize(fpath),
                    "url": f"/api/background/image/{f}"
                })
        return jsonify({"success": True, "data": files})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


def upload_background():
    """上传背景图片"""
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "未选择文件"})

        file = request.files['file']
        if not file.filename:
            return jsonify({"success": False, "error": "文件名为空"})

        # 安全检查：只允许图片扩展名
        safe_name = file.filename
        ext = os.path.splitext(safe_name)[1].lower()
        if ext not in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'):
            return jsonify({"success": False, "error": "不支持的图片格式"})

        os.makedirs(BACKGROUND_DIR, exist_ok=True)
        dest = os.path.join(BACKGROUND_DIR, safe_name)

        # 避免覆盖：同名文件添加序号
        base, ext = os.path.splitext(safe_name)
        counter = 1
        while os.path.exists(dest):
            dest = os.path.join(BACKGROUND_DIR, f"{base}_{counter}{ext}")
            safe_name = os.path.basename(dest)
            counter += 1

        file.save(dest)
        return jsonify({
            "success": True,
            "data": {
                "filename": safe_name,
                "url": f"/api/background/image/{safe_name}",
                "size": os.path.getsize(dest)
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


def delete_background():
    """删除背景图片"""
    data = request.get_json() or {}
    filename = data.get('filename', '')
    if not filename:
        return jsonify({"success": False, "error": "文件名不能为空"})

    # 安全检查：防止路径穿越
    safe_name = os.path.basename(filename)
    file_path = os.path.join(BACKGROUND_DIR, safe_name)
    if not os.path.isfile(file_path):
        return jsonify({"success": False, "error": "文件不存在"})

    try:
        os.remove(file_path)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


def serve_background_image(filename):
    """提供背景图片访问"""
    safe_name = os.path.basename(filename)
    file_path = os.path.join(BACKGROUND_DIR, safe_name)
    if os.path.isfile(file_path):
        return send_file(file_path)
    return "", 404


def open_location():
    """打开文件所在位置"""
    data = request.get_json() or {}
    file_path = data.get('path', '')

    if not file_path:
        return jsonify({"success": False, "error": "路径不能为空"})

    file_path = os.path.abspath(file_path)

    if not os.path.exists(file_path):
        return jsonify({"success": False, "error": "路径不存在"})

    try:
        if os.path.isdir(file_path):
            # 目录：直接打开该目录
            os.startfile(file_path)
        else:
            # 文件：在资源管理器中打开所在目录并选中文件
            subprocess.run(['explorer', '/select,', os.path.normpath(file_path)])
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
