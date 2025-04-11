#!/bin/bash
set -e

# Colors for better readability
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
BLUE="\033[0;34m"
RESET="\033[0m"

echo -e "${BLUE}==== FastAPI Project Test Runner ====${RESET}"
echo -e "${YELLOW}Running tests and checks according to TDD workflow${RESET}"

# Create a virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${RESET}"
    python -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies if needed
if [ "$1" == "--install" ]; then
    echo -e "${YELLOW}Installing dependencies...${RESET}"
    pip install -r requirements.txt
fi

# Format code with Black
echo -e "\n${BLUE}[1/6] Running Black formatter...${RESET}"
black .

# Sort imports with isort
echo -e "\n${BLUE}[2/6] Running isort...${RESET}"
isort .

# Run Flake8 linting
echo -e "\n${BLUE}[3/6] Running Flake8 linter...${RESET}"
flake8 .

# Run MyPy type checking
echo -e "\n${BLUE}[4/6] Running MyPy type checker...${RESET}"
mypy app

# Run tests with coverage
echo -e "\n${BLUE}[5/6] Running Pytest with coverage...${RESET}"

if [ "$1" == "--unit" ]; then
    # Run only unit tests
    pytest app/tests/test_unit --cov=app --cov-report=term-missing --cov-report=xml
elif [ "$1" == "--integration" ]; then
    # Run only integration tests
    pytest app/tests/test_integration --cov=app --cov-report=term-missing --cov-report=xml
elif [ "$1" == "--e2e" ]; then
    # Run only e2e tests
    pytest app/tests/test_e2e --cov=app --cov-report=term-missing --cov-report=xml
elif [ "$1" == "--fast" ]; then
    # Skip slow tests
    pytest app/tests -k "not slow" --cov=app --cov-report=term-missing --cov-report=xml
else
    # Run all tests
    pytest app/tests --cov=app --cov-report=term-missing --cov-report=xml
fi

# Generate HTML coverage report
echo -e "\n${BLUE}[6/6] Generating HTML coverage report...${RESET}"
pytest app/tests --cov=app --cov-report=html

# Display coverage report path
echo -e "\n${GREEN}Test run complete!${RESET}"
echo -e "${GREEN}HTML coverage report generated at: ${YELLOW}htmlcov/index.html${RESET}"
echo -e "\n${YELLOW}Available options:${RESET}"
echo -e "  --install     : Install dependencies"
echo -e "  --unit        : Run only unit tests"
echo -e "  --integration : Run only integration tests"
echo -e "  --e2e         : Run only end-to-end tests"
echo -e "  --fast        : Skip slow tests" 