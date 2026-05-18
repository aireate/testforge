# TestForge

A pytest-based automated testing framework for API testing.

## Tech Stack

- **Pytest** - Python testing framework
- **Requests** - HTTP library for API testing
- **Allure** - Test report generation tool

## Installation

```bash
pip install -r requirements.txt
```

## Run Tests

```bash
pytest
```

## Generate Allure Report

```bash
# Run tests with allure results
pytest

# Generate and serve the report
allure serve ./allure-results
```

Or generate static report:

```bash
allure generate ./allure-results -o ./allure-report
allure open ./allure-report
```

## Project Structure

```
testforge/
├── common/
│   └── request_util.py     # Request utility class
├── tests/
│   └── test_demo.py        # Test cases
├── pytest.ini              # Pytest configuration
└── requirements.txt        # Dependencies
```
