"""
RePKG-GUI 应用入口
Flask Web Application Entry Point

启动方式：
  Web 模式: python app.py
  桌面模式: python app.py --gui
"""
import os
import sys
import mimetypes
from flask import Flask, render_template

from backend import api
from backend.paths import get_app_dir
from backend.server import start_gui, start_web

BASE_DIR = get_app_dir()

app = Flask(__name__,
            template_folder=os.path.join(BASE_DIR, 'templates'),
            static_folder=os.path.join(BASE_DIR, 'static'))
app.secret_key = os.urandom(24)

# 确保 .js 文件使用正确的 MIME 类型（PyInstaller 运行时可能丢失）
mimetypes.add_type('application/javascript', '.js')


# ==================== 页面路由 ====================

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/settings')
def settings_page():
    """设置页"""
    return render_template('settings.html')


# ==================== 配置 API ====================

@app.route('/api/settings', methods=['GET'])
def get_settings():
    return api.get_settings()


@app.route('/api/settings', methods=['POST'])
def save_settings():
    return api.save_settings()


# ==================== 扫描 API ====================

@app.route('/api/scan', methods=['GET', 'POST'])
def scan_files():
    return api.scan_files()


# ==================== 预览图 API ====================

@app.route('/api/preview/<path:filename>')
def serve_preview(filename):
    return api.serve_preview(filename)


# ==================== 输出目录管理 API ====================

@app.route('/api/output/scan', methods=['POST'])
def scan_output():
    return api.scan_output()


@app.route('/api/output/delete', methods=['POST'])
def delete_project():
    return api.delete_project()


# ==================== 提取任务 API ====================

@app.route('/api/extract', methods=['POST'])
def start_extract():
    return api.start_extract()


@app.route('/api/progress', methods=['GET'])
def get_progress():
    return api.get_extract_progress()


@app.route('/api/logs', methods=['GET'])
def stream_logs():
    return api.stream_logs()


@app.route('/api/stop', methods=['POST'])
def stop_extract():
    return api.stop_extract()


# ==================== 文件操作 API ====================

@app.route('/api/cache/clear', methods=['POST'])
def clear_cache():
    return api.clear_cache()


# ==================== 背景图片 API ====================

@app.route('/api/backgrounds', methods=['GET'])
def list_backgrounds():
    return api.list_backgrounds()


@app.route('/api/backgrounds/upload', methods=['POST'])
def upload_background():
    return api.upload_background()


@app.route('/api/backgrounds/delete', methods=['POST'])
def delete_background():
    return api.delete_background()


@app.route('/api/background/image/<path:filename>')
def serve_background_image(filename):
    return api.serve_background_image(filename)


# ==================== 文件浏览 API ====================

@app.route('/api/open_location', methods=['POST'])
def open_location():
    return api.open_location()


# ==================== Steam 路径 API ====================

@app.route('/api/steam/detect', methods=['GET'])
def detect_steam():
    return api.detect_steam()


@app.route('/api/steam/validate', methods=['POST'])
def validate_path():
    return api.validate_path()


@app.route('/api/steam/subdirs', methods=['POST'])
def get_subdirs():
    return api.get_subdirs()


# ==================== 启动 ====================

if __name__ == '__main__':
    if getattr(sys, 'frozen', False):
        # 打包模式：始终以窗口化 GUI 启动
        start_gui(app)
    else:
        # 开发模式：python app.py 为 Web 模式，python app.py --gui 为桌面模式
        if '--gui' in sys.argv or '--desktop' in sys.argv:
            start_gui(app)
        else:
            start_web(app)
