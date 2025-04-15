# Email Webhooks Refactoring Plan

## Overview

This document outlines a step-by-step plan to refactor the `app/api/endpoints/email_webhooks.py` file into a more maintainable structure. The plan focuses on very small iterations, with testing and code quality validation after each step.

## Guiding Principles

1. **Small Steps**: Each refactoring iteration should be as small as possible
2. **Continuous Testing**: Run pytest after each change to ensure functionality is preserved
3. **Code Quality**: Check linting and other quality metrics after each step
4. **Complete Replacement**: After each phase, remove old functionality entirely

## Phase 1: Initial Setup

### Step 1.1: Create Basic Directory Structure
- Create directory `app/api/endpoints/webhooks/`
- Create directory `app/api/endpoints/webhooks/common/`
- Create directory `app/api/endpoints/webhooks/mandrill/`
- Add empty `__init__.py` files to each directory
- Run tests to ensure no import issues

### Step 1.2: Move Utils Module
- Create `app/api/endpoints/webhooks/common/mime_utils.py`
- Move MIME-related functions (`_decode_mime_header`)
- Update imports in email_webhooks.py to use new location
- Run tests and fix any issues
- Run linter and fix any issues

### Step 1.3: Remove Old Utils Functions
- Remove old utility functions from email_webhooks.py
- Run tests and fix any issues
- Run linter and fix any issues

## Phase 2: Extract Attachment Processing

### Step 2.1: Create Attachments Module
- Create `app/api/endpoints/webhooks/common/attachments.py`
- Move attachment normalization functions:
  - `_normalize_attachments`
  - `_process_attachment_list`
  - `_parse_attachment_string`
  - `_parse_attachments_from_dict`
  - `_parse_attachments_from_string`
  - `_decode_filenames_in_attachments`
- Update imports in email_webhooks.py
- Run tests and fix any issues
- Run linter and fix any issues

### Step 2.2: Remove Old Attachment Functions
- Remove old attachment functions from email_webhooks.py
- Run tests and fix any issues
- Run linter and fix any issues

## Phase 3: Extract Parsing Logic

### Step 3.1: Extract Form Data Parsing
- Create `app/api/endpoints/webhooks/mandrill/parsers.py`
- Move form data parsing functions:
  - `_handle_form_data`
  - `_parse_form_field`
  - `_check_alternate_form_fields`
- Update imports to use new module
- Run tests and fix any issues
- Run linter and fix any issues

### Step 3.2: Extract JSON Parsing
- Add JSON parsing functions to parsers.py:
  - `_parse_json_from_bytes`
  - `_parse_json_from_string`
  - `_parse_json_from_request`
  - `_log_parsed_body_info`
  - `_create_json_error_response`
  - `_handle_json_body`
  - `_parse_json_body`
- Update imports to use new module
- Run tests and fix any issues
- Run linter and fix any issues

### Step 3.3: Extract Common Webhook Body Preparation
- Add webhook body preparation function to parsers.py:
  - `_prepare_webhook_body`
  - `_is_ping_event`
  - `_is_empty_event_list`
  - `_handle_empty_events`
  - `_handle_ping_event`
- Update imports to use new module
- Run tests and fix any issues
- Run linter and fix any issues

### Step 3.4: Remove Old Parsing Functions
- Remove all old parsing functions from email_webhooks.py
- Run tests and fix any issues
- Run linter and fix any issues

## Phase 4: Extract Event Processing Logic

### Step 4.1: Create Processors Module
- Create `app/api/endpoints/webhooks/mandrill/processors.py`
- Move event processing functions:
  - `_process_single_event`
  - `_process_event_batch`
  - `_process_non_list_event`
  - `_handle_event_list`
  - `_handle_single_event_dict`
- Update imports to use new module
- Run tests and fix any issues
- Run linter and fix any issues

### Step 4.2: Create Formatters Module
- Create `app/api/endpoints/webhooks/mandrill/formatters.py`
- Move event formatting functions:
  - `_format_event`
  - `_process_mandrill_headers`
  - `_parse_message_id`
- Update imports to use new module
- Run tests and fix any issues
- Run linter and fix any issues

### Step 4.3: Remove Old Processing Functions
- Remove old processing and formatting functions from email_webhooks.py
- Run tests and fix any issues
- Run linter and fix any issues

## Phase 5: Refactor Main Route Handler

### Step 5.1: Create Mandrill Router
- Create `app/api/endpoints/webhooks/mandrill/router.py`
- Move the route handler function:
  - `receive_mandrill_webhook`
- Update imports
- Run tests and fix any issues
- Run linter and fix any issues

### Step 5.2: Update Main Webhooks Router
- Replace the content in `app/api/endpoints/email_webhooks.py` to import and use the new router
- Run tests and fix any issues
- Run linter and fix any issues

## Phase 6: Cleanup and Documentation

### Step 6.1: Update Docstrings
- Review and update docstrings across all new modules
- Ensure consistency in documentation style
- Run docstring linter if available

### Step 6.2: Add Module-Level Documentation
- Add comprehensive module docstrings to each new file
- Document the overall architecture and responsibilities

### Step 6.3: Final Quality Check
- Run full test suite
- Run all linters and code quality tools
- Perform manual verification of endpoints

## Phase 7: Prepare for Future Expansion

### Step 7.1: Document Extension Points
- Create a README.md in the webhooks directory explaining how to add new webhook providers
- Document the common interfaces that new providers should implement

### Step 7.2: Review Integration Points
- Review places where the webhook system integrates with other parts of the application
- Document any requirements for future webhook providers

## Conclusion

By following this step-by-step plan, we will have:
1. Completely refactored the monolithic email_webhooks.py file into a modular structure
2. Removed old functionality after each phase is completed
3. Ensured code quality at each step
4. Created a maintainable architecture that can easily accommodate future webhook providers like Twilio 