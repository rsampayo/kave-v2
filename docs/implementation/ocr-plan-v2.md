**AI Assistant Task: Implement PDF OCR for Email Attachments (macOS Dev / Heroku Prod)**

**IMPORTANT WORKFLOW INSTRUCTIONS:**
* IMPLEMENT ONLY ONE STEP AT A TIME. After completing a step, STOP and ask for permission before proceeding to the next step.
* Each step should be fully implemented, tested, and verified before moving on.
* Clearly indicate which step you've completed and wait for explicit approval before starting the next one.
* If anything is unclear, ask for clarification before proceeding.

**Overall Goal:** Add functionality to OCR PDF attachments received via email webhooks using Celery, PyMuPDF, and Pytesseract (as fallback). Store the extracted text per page in a new database table. Deployable on Heroku.

**Mandatory Guidelines:** Strictly follow the provided "Development Guidelines" document, including:
*   **TDD:** Red-Green-Refactor cycle for all code.
*   **Iterative Quality:** Run Black, isort, Flake8, MyPy frequently and fix issues immediately.
*   **Minimal Changes:** Only implement the changes required for the current step.
*   **Testing:** Ensure all tests pass before moving to the next step.
*   **Dependencies:** Use `pip-compile` via `requirements.in`.
*   **Migrations:** Use Alembic.

---

## Implementation Steps

This implementation plan is divided into 12 sequential steps, each with its own detailed instructions. Follow each step in order and seek approval before moving to the next step.

### Step 1: [Add Dependencies and Basic Celery Setup](steps/step01-dependencies.md)
Add required libraries and minimal Celery configuration, considering macOS dev and Heroku prod environments.

### Step 2: [Define AttachmentTextContent Model & Relationship](steps/step02-models.md)
Create the SQLAlchemy model structure for storing OCR results and establish relationships.

### Step 3: [Generate & Apply Database Migration](steps/step03-migration.md)
Update the database schema to include the new attachment_text_content table.

### Step 4: [Create Basic Celery Task Structure](steps/step04-task-structure.md)
Define the Celery task function signature and basic logging, without OCR logic.

### Step 5: [Implement Task: Fetch Attachment & PDF Data](steps/step05-fetch-data.md)
Add logic to fetch the Attachment record and retrieve its PDF data from storage.

### Step 6: [Implement Task: Basic PyMuPDF Parsing (Page Count)](steps/step06-pdf-parsing.md)
Add PyMuPDF logic to open the retrieved PDF data and log the page count.

### Step 7: [Implement Task: Loop & Direct Text Extraction & DB Save](steps/step07-text-extraction.md)
Loop through PDF pages, extract text directly, and save to the AttachmentTextContent table.

### Step 8: [Implement Task: Pytesseract OCR Fallback](steps/step08-ocr-fallback.md)
Enhance page processing to use Pytesseract OCR if direct text extraction returns minimal text.

### Step 9: [Implement Task: Final Error Handling & Retries](steps/step09-error-handling.md)
Ensure proper error handling, database rollback, Celery retries, and session management.

### Step 10: [Trigger Task from AttachmentService](steps/step10-trigger-task.md)
Modify AttachmentService to dispatch the OCR task when a PDF attachment is processed.

### Step 11: [Integration Testing](steps/step11-integration-testing.md)
Verify the end-to-end flow from webhook reception to OCR text being saved in the database.

### Step 12: [Documentation and Heroku Preparation](steps/step12-documentation.md)
Update project documentation and add Heroku-specific deployment configurations.

---

## Implementation Workflow

For each step:

1. Read the detailed instructions in the corresponding step file
2. Implement the step following the TDD approach (RED-GREEN-REFACTOR)
3. Run the quality checks and tests
4. Complete the self-verification checklist
5. Stop and request approval before proceeding to the next step

This structured approach ensures that each component is properly implemented and tested before moving forward, reducing the risk of integration issues later in the process.

---

This implementation plan accounts for macOS development and Heroku deployment specifics. Remember to verify each step thoroughly before proceeding to the next. 