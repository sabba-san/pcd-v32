# User Acceptance Test (UAT) — DLP Advisor Platform

## 1. UAT Purpose

The purpose of User Acceptance Testing (UAT) is to verify that the DLP Advisor Platform functions according to user requirements and is suitable for actual use by its intended users: homeowners, developers, and lawyers.

## 2. UAT Scope

| No. | Module / Feature |
|---:|---|
| 1 | User registration and login |
| 2 | Role selection |
| 3 | Role-based dashboard access |
| 4 | 3D model upload and viewing |
| 5 | Defect report submission |
| 6 | Evidence photo upload |
| 7 | AI Legal Chatbot |
| 8 | Case status tracking |
| 9 | Developer status update |
| 10 | Lawyer case review |
| 11 | Report generation |
| 12 | Custom error page handling |

## 3. UAT Test Users

| No. | User Role | Description |
|---:|---|---|
| 1 | Homeowner Representative | Tests homeowner registration, report submission, evidence upload, chatbot usage, and status tracking |
| 2 | Developer Representative | Tests report review, repair status updates, and repair notes |
| 3 | Lawyer Representative | Tests legal case review, chatbot support, and report-related workflows |

## 4. UAT Environment

| Item | Details |
|---|---|
| Platform | Web application |
| Framework | Flask (Python) |
| Database | PostgreSQL |
| Browser Used | Google Chrome / Microsoft Edge |
| Test Date | [Insert Date] |
| Test Location | [Insert Location] |

## 5. UAT Test Cases

| TC No. | Test Scenario | User Role | Pre-Condition | Expected Result | Actual Result | Status | Remarks |
|---|---|---|---|---|---|---|---|
| TC-01 | Register a new account | Homeowner | User is not registered | User can register successfully |  |  |  |
| TC-02 | Log in with valid credentials | All roles | Registered account exists | User can log in and access the correct dashboard |  |  |  |
| TC-03 | Select the correct role during registration | All roles | Registration form is available | System assigns the correct role and dashboard access |  |  |  |
| TC-04 | Upload a 3D model in GLB format below 50MB | Homeowner | User is logged in | File uploads successfully and can be viewed |  |  |  |
| TC-05 | Upload a file above 50MB | Homeowner | User is logged in | System rejects the upload and shows a warning message |  |  |  |
| TC-06 | Create a defect report | Homeowner | User is logged in | Defect report is submitted successfully |  |  |  |
| TC-07 | Upload an evidence photo | Homeowner | Defect report exists | Photo uploads successfully and is linked to the report |  |  |  |
| TC-08 | View submitted report status | Homeowner | Submitted report exists | Report status is displayed correctly |  |  |  |
| TC-09 | Use AI Legal Chatbot | Homeowner / Lawyer | User is logged in and chatbot is available | Chatbot responds to legal-related queries appropriately |  |  |  |
| TC-10 | View incoming defect reports | Developer | Developer account is logged in | Developer can view homeowner defect reports |  |  |  |
| TC-11 | Update defect repair status | Developer | Defect report exists | Repair status updates successfully |  |  |  |
| TC-12 | Add repair notes | Developer | Defect report exists | Notes are saved correctly |  |  |  |
| TC-13 | Review case details | Lawyer | Case data exists | Lawyer can access and review case information |  |  |  |
| TC-14 | Generate a formal report | Relevant user | Required case or defect data exists | Report is generated successfully |  |  |  |
| TC-15 | Access an invalid page | All roles | Application is running | Custom 404 page is displayed |  |  |  |
| TC-16 | Trigger a system error page | All roles | Application is running | Custom 500 page is displayed properly |  |  |  |

## 6. UAT Acceptance Criteria

| No. | Acceptance Criterion |
|---:|---|
| 1 | All critical functions can be used successfully |
| 2 | Users can access features based on their assigned roles |
| 3 | Defect reports and evidence uploads work correctly |
| 4 | Developers can update case status without error |
| 5 | Lawyers can review cases and use chatbot assistance |
| 6 | The 50MB upload restriction works as intended |
| 7 | Custom error pages display correctly |
| 8 | Most or all test cases are marked as `Pass` |

## 7. UAT Result Summary

| Item | Result |
|---|---|
| Total Test Cases | 16 |
| Passed | [Insert Number] |
| Failed | [Insert Number] |
| Pending | [Insert Number] |

**Conclusion:**  
The DLP Advisor Platform has met the main user requirements and is acceptable for deployment and demonstration, subject to the final UAT results recorded above.

## 8. UAT Sign-Off

| Role | Name | Signature | Date |
|---|---|---|---|
| Prepared By | [Your Name] |  | [Insert Date] |
| Homeowner Representative | [Insert Name] |  | [Insert Date] |
| Developer Representative | [Insert Name] |  | [Insert Date] |
| Lawyer Representative | [Insert Name] |  | [Insert Date] |

---

## Quick Test Instructions (Smoke Checks)

1. Create a virtual environment and install the dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Run a lightweight import smoke test:

```bash
python -c "from app import create_app; app = create_app(); print('OK')"
```

3. Initialize the database, if required, and run the application:

```bash
flask init-db
python -c "from app import create_app; app = create_app(); app.run(debug=True, host='0.0.0.0', port=5000)"
```

4. Perform manual UAT using the test cases listed in Section 5.
