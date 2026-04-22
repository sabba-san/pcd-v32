import os
import re

ROUTES_PY = '/home/abbas/development/pcd-v32/app/module3/routes.py'
INIT_PY = '/home/abbas/development/pcd-v32/app/__init__.py'

def patch_routes():
    with open(ROUTES_PY, 'r', encoding='utf-8') as f:
        content = f.read()

    # Update render_template calls
    # dashboard_admin.html -> module3/dashboard_admin.html
    # ai_report.html -> module3/ai_report.html
    # dashboard_homeowner.html -> module3/dashboard_homeowner.html
    # dashboard_developer.html -> module3/dashboard_developer.html
    # dashboard_legal.html -> module3/dashboard_legal.html
    # login.html -> module3/login.html
    
    template_names = [
        "dashboard_admin.html",
        "ai_report.html",
        "dashboard_homeowner.html",
        "dashboard_developer.html",
        "dashboard_legal.html",
        "login.html"
    ]
    
    for name in template_names:
        content = content.replace(f'"{name}"', f'"module3/{name}"')
        content = content.replace(f"'{name}'", f"'module3/{name}'")

    with open(ROUTES_PY, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched routes.py templates.")

def patch_init():
    with open(INIT_PY, 'r', encoding='utf-8') as f:
        content = f.read()

    # app.register_blueprint(module3) -> app.register_blueprint(module3, url_prefix='/module3')
    content = content.replace('app.register_blueprint(module3)', "app.register_blueprint(module3, url_prefix='/module3')")

    with open(INIT_PY, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched __init__.py with url_prefix='/module3'.")

if __name__ == '__main__':
    patch_routes()
    patch_init()
