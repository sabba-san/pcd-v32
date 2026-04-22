import os
import re

MODULE3_DIR = '/home/abbas/development/pcd-v32/app/module3'
ROUTES_PY = os.path.join(MODULE3_DIR, 'routes.py')
REPORT_DATA_PY = os.path.join(MODULE3_DIR, 'report_data.py')

def patch_file(filepath, replacements):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for pattern, repl in replacements:
        content = re.sub(pattern, repl, content, flags=re.MULTILINE)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

routes_replacements = [
    # 1. Strip out custom get_connection imports and use SQLAlchemy's connection
    (r"try:\n\s+from \.database\.db import get_connection\nexcept ImportError:.*?\n\s+from database\.db import get_connection", "def get_connection():\n    from ..extensions import db\n    return db.engine.raw_connection()"),
    
    # 2. Add flask_login to imports
    (r"from flask import \(", "from flask_login import login_required, current_user\nfrom flask import ("),
    
    # 3. Replace _current_role() and _current_user_id()
    (r"def _current_role\(\):\n\s+return session\.get\(\"role\"\)", 'def _current_role():\n    return current_user.user_type if current_user.is_authenticated else None'),
    (r"def _current_user_id\(\):\n\s+return session\.get\(\"user_id\"\).*?", "def _current_user_id():\n    return current_user.id if current_user.is_authenticated else None"),

    # 4. Remove custom login_required decorator and replace with Flask-Login's
    (r"def login_required\(func\):[\s\S]*?(?=@routes\.route)", ""),
    
    # 5. Fix references to Nabilah's custom auth routes to point to pcd-v32's auth blueprint
    (r"url_for\([\"']routes\.login[\"']\)", "url_for('auth.login')"),
    
    # 6. For simplicity, remove the massive login/logout functions in Nabilah since pcd-v32 auth already exists
    # we can find the def login() and replace it with a pass or remove it
    (r"@routes\.route\([\"']/login[\"'], methods=\[\"GET\", \"POST\"\]\)[\s\S]*?(?=@routes\.route\([\"']/logout[\"']\))", ""),
    (r"@routes\.route\([\"']/logout[\"']\)[\s\S]*?(?=# --------------------------------)", ""),
]

report_data_replacements = [
    (r"try:\n\s+from \.database\.db import get_connection\nexcept ImportError:.*?\n\s+from database\.db import get_connection", "def get_connection():\n    from ..extensions import db\n    return db.engine.raw_connection()"),
]

if __name__ == '__main__':
    print("Patching routes.py...")
    patch_file(ROUTES_PY, routes_replacements)
    print("Patching report_data.py...")
    patch_file(REPORT_DATA_PY, report_data_replacements)
    print("Done!")
