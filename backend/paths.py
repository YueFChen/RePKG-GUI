"""
路径工具模块
统一处理开发环境和 PyInstaller 打包环境下的路径解析
"""
import os
import sys


def get_app_dir() -> str:
    """
    获取应用根目录（数据文件所在目录）
    - 开发环境: 项目根目录
    - 打包环境: .exe 所在目录（数据文件与 exe 同级）
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    else:
        # paths.py 在 backend/ 下，上一级即项目根目录
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
