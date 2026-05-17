# DLP Advisor Platform – User Documentation

---

## Output 1: Project Overview

**DLP Advisor Platform** (Defect Liability Period Advisor Platform) is a Flask-based (Python) web application designed to assist in managing property defects during the Defect Liability Period (DLP). This platform connects three key parties: homeowners, developers, and lawyers within a centralized digital ecosystem.

**Core Objectives:**

- Enable homeowners to report property defects with visual evidence (including 3D models)
- Help developers efficiently record and update repair status
- Lawyers can review cases and obtain legal advice through an AI chatbot
- All parties can generate formal reports for further action

**Key Features:**

| Feature | Description |
|---------|-------------|
| User Authentication | Registration and login with three role options |
| 3D Defect Visualizer | Upload and view 3D property models (GLB format, max 50MB) |
| Defect Reporting Module | Homeowners can submit reports with evidence photos |
| AI Legal Chatbot | AI-powered legal advisor for DLP and SPA-related questions |
| Case Management | Status tracking (Reported, In Progress, Resolved) |
| Report Generation | Automatic formal report generation for submission |

---

## Output 2: Step-by-Step User Guides

### A: Step-by-Step Guide for Homeowners (Pemilik Rumah)

1. **Login to the System**
   - Visit the platform's main page
   - Click "Register Now" to create a new account
   - Fill in personal details: full name, email, phone number, password
   - Select "Homeowner" as your role during registration
   - Click "Register" and activate your account via confirmation email (if required)
   - Login using your registered email and password

2. **Access the Dashboard**
   - After logging in, you will enter the homeowner-specific view
   - Review the summary of reports you have submitted
   - Use the menu to navigate to other functions

3. **Using the 3D Defect Visualizer**
   - Click on "3D Model" or "Visualizer" section
   - Click the "Upload" button to select a GLB model file (maximum 50MB)
   - Wait for the upload to complete
   - Use your mouse to rotate, zoom, and pan the 3D model
   - You can view the property model from various angles

4. **Submitting a Defect Report**
   - Click "New Report" or "Create Report"
   - Fill in the defect information:
     - Report title
     - Defect category (structure, electrical, plumbing, etc.)
     - Detailed description of the issue
     - Location of the defect within the property
   - Upload evidence photos (JPEG/PNG format)
   - Optionally, attach the 3D model uploaded earlier
   - Click "Submit" to send your report

5. **Using the AI Legal Chatbot**
   - Click "Legal Chatbot" or "AI Advisor"
   - Type your question about DLP, SPA, or your legal rights
   - Read the AI's response and use it as a reference
   - You can ask follow-up questions in the same session

6. **Tracking Case Status**
   - Go to "My Cases" or "Report Status"
   - View the list of reports you have submitted
   - Check the current status: Reported → In Progress → Resolved
   - Click on each report to view more details

---

### B: Step-by-Step Guide for Developers (Pemaju)

1. **Login to the System**
   - Visit the platform's login page
   - Enter your registered email and password
   - Ensure the "Developer" role is selected

2. **Access the Dashboard**
   - After logging in, the developer-specific view will appear
   - You will see a list of defects reported by homeowners

3. **Viewing Defect Reports**
   - Click on "Defect List" or "Incoming Reports"
   - View all reports submitted by homeowners
   - Filter by status or date
   - Click on each report to view full details:
     - Defect description
     - Evidence photos
     - 3D model (if available)
     - Homeowner information

4. **Updating Repair Status**
   - Open the defect report you wish to update
   - Click "Update Status" or similar button
   - Select a new status:
     - **In Progress** – repair work is underway
     - **Resolved** – repair has been completed
   - Add notes or comments about the actions taken
   - Click "Save" to update the status

5. **Generating Repair Reports**
   - Once repairs are completed, click "Generate Report"
   - The system will generate a formal report
   - Download the report in PDF format for your records

---

### C: Step-by-Step Guide for Lawyers (Peguam)

1. **Login to the System**
   - Visit the platform's login page
   - Enter your registered email and password
   - Ensure the "Lawyer" role is selected

2. **Access the Dashboard**
   - After logging in, the lawyer-specific view will appear
   - You will see all cases requiring legal review

3. **Reviewing Cases and Reports**
   - Click "Cases" or "Case List"
   - View the list of all reported cases
   - Filter by status or homeowner
   - Click on each case to view full details:
     - Defect details
     - Evidence photos
     - 3D model (if available)
     - Status history
     - Notes from the developer

4. **Providing Legal Review**
   - Open the case you wish to review
   - Click "Add Review" or "Legal Comment"
   - Write your comments and legal advice
   - Click "Submit" to save your review

5. **Using the AI Legal Chatbot**
   - Click "Legal Chatbot" or "AI Advisor"
   - Type your question about DLP provisions, SPA clauses, or specific cases
   - Use the AI response as additional reference
   - This helps provide more accurate legal advice

6. **Generating Legal Reports**
   - Go to the required case
   - Click "Generate Legal Report"
   - The system will prepare a comprehensive report including your legal review
   - Download it for use in proceedings or negotiations

---

**Important Note:**
Each user should keep their password secure and log out after use, especially when using a shared computer. For any technical issues or questions, contact the system administrator.