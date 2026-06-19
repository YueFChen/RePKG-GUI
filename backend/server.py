"""
服务器启动模块
处理 Flask 服务器启动、pywebview 桌面窗口、端口检测等底层逻辑
"""
import os
import sys
import time
import socket
import threading
import urllib.request
import urllib.error

from backend.paths import get_app_dir

DEFAULT_PORT = 5000
MAX_PORT_RETRY = 10


def _is_port_in_use(host: str, port: int) -> bool:
    """检测端口是否被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def find_available_port(host: str = '127.0.0.1', start_port: int = DEFAULT_PORT) -> int:
    """查找可用端口，从 start_port 开始尝试"""
    for offset in range(MAX_PORT_RETRY):
        port = start_port + offset
        if not _is_port_in_use(host, port):
            return port
    raise RuntimeError(
        f"无法找到可用端口（已尝试 {start_port}-{start_port + MAX_PORT_RETRY - 1}）"
    )


def _wait_for_server(url: str, timeout: float = 5.0, interval: float = 0.1) -> bool:
    """轮询等待服务器就绪"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=0.5)
            return True
        except (urllib.error.URLError, OSError):
            time.sleep(interval)
    return False


def start_flask_server(app, port: int):
    """启动 Flask 服务器（阻塞）"""
    app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)


def start_gui(app):
    """启动桌面 GUI 模式（pywebview）"""
    try:
        import webview
    except ImportError:
        print("错误: pywebview 未安装，请运行: pip install pywebview")
        sys.exit(1)

    host = '127.0.0.1'
    port = find_available_port(host, DEFAULT_PORT)
    server_url = f'http://{host}:{port}'

    # 启动 Flask 服务器（守护线程）
    server_thread = threading.Thread(
        target=start_flask_server,
        args=(app, port),
        daemon=True,
    )
    server_thread.start()

    # 等待服务器就绪
    if not _wait_for_server(server_url):
        print(f"错误: 服务器启动超时，无法连接到 {server_url}")
        sys.exit(1)

    print(f"Flask 服务器已启动: {server_url}")

    # 获取图标路径
    icon_path = os.path.join(get_app_dir(), 'static', 'assets', 'images', 'icon.ico')

    # 创建窗口
    window = webview.create_window(
        title='RePKG-GUI',
        url=server_url,
        width=1400,
        height=900,
        min_size=(1000, 700),
        resizable=True,
    )

    # 启动 WebView（阻塞，窗口关闭后返回）
    start_kwargs = {'debug': False}
    if os.path.exists(icon_path):
        start_kwargs['icon'] = icon_path
    try:
        webview.start(**start_kwargs)
    except Exception as e:
        print(f"WebView 启动失败: {e}")
        sys.exit(1)


def start_web(app):
    """启动 Web 模式（控制台直接运行）"""
    port = find_available_port('127.0.0.1', DEFAULT_PORT)
    print(f"启动 Web 模式: http://127.0.0.1:{port}")
    app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)
