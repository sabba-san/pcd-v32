# User Acceptance Test (UAT) — DLP Advisor Platform

## 1. UAT Purpose
The purpose of User Acceptance Testing (UAT) is to verify that the DLP Advisor Platform functions correctly based on user requirements and is suitable for actual use by the intended users: homeowners, developers, and lawyers.

## 2. UAT Scope
The UAT covers the following modules:

- user registration and login
- role selection
- role-based dashboard access
- 3D model upload and viewing
- defect report submission
- evidence photo upload
- AI Legal Chatbot
- case status tracking
- developer status update
- lawyer case review
- report generation
- custom error page handling

## 3. UAT Test Users

- Homeowner Representative
- Developer Representative
- Lawyer Representative

## 4. UAT Environment

- Platform: Web application
- Framework: Flask (Python)
- Browser used: Google Chrome / Microsoft Edge
- Test date: [Insert Date]
- Test location: [Insert Location]

## 5. UAT Test Cases

| No. | Test Scenario | User Role | Expected Result | Actual Result | Status |
|---:|---|---|---|---|---|
| 1 | Register a new account | Homeowner | User can register successfully |  | |
| 2 | Log in with valid credentials | All roles | User can log in and access dashboard |  | |
| 3 | Select correct role during registration | All roles | System assigns correct role and dashboard |  | |
| 4 | Upload 3D model in GLB format below 50MB | Homeowner | File uploads successfully and can be viewed |  | |
| 5 | Upload file above 50MB | Homeowner | System rejects upload and shows warning |  | |
| 6 | Create a defect report | Homeowner | Report is submitted successfully |  | |
| 7 | Upload evidence photo | Homeowner | Photo uploads successfully and is linked to report |  | |
| 8 | View submitted report status | Homeowner | Status is displayed correctly |  | |
| 9 | Use AI Legal Chatbot | Homeowner/Lawyer | Chatbot responds to legal-related query |  | |
| 10 | View incoming defect reports | Developer | Developer can view homeowner reports |  | |
| 11 | Update defect repair status | Developer | Status changes successfully |  | |
| 12 | Add repair notes | Developer | Notes are saved correctly |  | |
| 13 | Review case details | Lawyer | Lawyer can access and review case data |  | |
| 14 | Generate formal report | Relevant user | Report is generated successfully |  | |
| 15 | Access invalid page | All roles | Custom 404 page is displayed |  | |
| 16 | Trigger system error page | All roles | Custom 500 page is displayed properly |  | |

## 6. UAT Acceptance Criteria

The system is considered accepted if:

- all critical functions can be used successfully
- users can access features based on their assigned role
- defect reports and evidence uploads work correctly
- developers can update case status without error
- lawyers can review cases and use chatbot assistance
- the 50MB upload restriction works as intended
- custom error pages display correctly
- most or all test cases are marked as Pass

## 7. UAT Result Summary

Example summary:

- Total test cases: 16
- Passed: 16
- Failed: 0

**Conclusion:**

The DLP Advisor Platform has met the main user requirements and is acceptable for deployment and demonstration.

## 8. UAT Sign-Off

Prepared by: [Your Name]
Role: Project Developer / Student

Tested by:

[Homeowner Representative Name]
[Developer Representative Name]
[Lawyer Representative Name]
Date: [Insert Date]

---

## Quick test instructions (smoke checks)

1. Create virtualenv and install requirements:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Run a lightweight import smoke test (verifies Flask app factory imports):

```bash
python -c "from app import create_app; app = create_app(); print('OK')"
```

3. Initialize DB (if required) and run the app:

```bash
flask init-db
python -c "from app import create_app; app = create_app(); app.run(debug=True,host='0.0.0.0',port=5000)"
```

4. Manual UAT: follow the test cases in section 5 via browser.

If you want this converted into a PowerPoint-style slide script, a formal FYP report section, or an academic UAT table, tell me which format you prefer.
