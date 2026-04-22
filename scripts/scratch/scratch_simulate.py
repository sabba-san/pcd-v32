import urllib.request
import urllib.parse

# Let's see if we can log in and call export_pdf to see where it crashes or what it returns. Let's just run a backend script.
import sys
sys.path.append('.')
from app import create_app
from app.extensions import db
from app.models import User
from app.module3.report_data import _load_report_metadata

app = create_app()
with app.app_context():
    homeowners = User.query.filter_by(role='Homeowner').all()
    if not homeowners:
        print("No homeowners found")
    else:
        user_id = homeowners[-1].id
        print(f"Testing for Homeowner ID: {user_id}")
        case_info, claimant, respondent, negeri_codes, role_contexts, nota_penting = _load_report_metadata(user_id=user_id, role="Homeowner", claimant_user_id=user_id)
        print("Claimant:")
        print(claimant)
        print("Respondent:")
        print(respondent)
        print("Case Info:")
        print(case_info)
