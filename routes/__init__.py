"""
routes/__init__.py
รวม Blueprint ทั้งหมดเพื่อให้ app.py register ได้ง่าย
"""

from .auth import auth_bp
from .main import main_bp
from .requests import requests_bp
from .rounds import rounds_bp
from .admin import admin_bp
from .api import api_bp
