# TestForge

A pytest-based API automation testing framework for learning and internship preparation.

---

## 🎯 Features

| Feature | Status |
|---------|--------|
| ✅ **GET Request** | [test_user_api.py](tests/test_user_api.py) |
| ✅ **POST Request** | [test_post_api.py](tests/test_post_api.py) |
| ✅ **Request Utility** | [common/request_util.py](common/request_util.py) |
| ✅ **Logging** | [common/log_util.py](common/log_util.py) |
| ✅ **Allure Report** | [pytest.ini](pytest.ini) |
| ✅ **Jenkins Pipeline** | [Jenkinsfile](Jenkinsfile) |

---

## 🛠️ Tech Stack

- **Python**
- **pytest** - Testing framework
- **requests** - HTTP client
- **Allure** - Beautiful test reports
- **Jenkins** - CI/CD pipeline

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run All Tests

```bash
pytest
```

You will see:
```
collected 3 items

tests/test_demo.py::test_get_request PASSED
tests/test_post_api.py::test_create_post PASSED
tests/test_user_api.py::test_get_user PASSED
```

### 3. Generate Allure Report

```bash
# Allure results are already in ./allure-results/
# Just run:
allure serve ./allure-results
```

---

## 📁 Project Structure

```
testforge/
├── common/                  # Utilities
│   ├── request_util.py      # GET/POST wrapper
│   └── log_util.py          # Console + File logging
├── tests/                    # Test cases
│   ├── test_demo.py         # Basic connectivity test
│   ├── test_user_api.py     # GET /users/1 assertions
│   └── test_post_api.py     # POST /posts JSON body
├── Jenkinsfile               # CI/CD pipeline
├── pytest.ini                # pytest + Allure config
├── requirements.txt          # Dependencies: pytest/requests/allure-pytest
└── jenkins-guide.md          # Step-by-step Jenkins guide
```

---

## 📝 Writing Your Own Test

```python
import pytest
from common.request_util import RequestUtil

@pytest.fixture
def api():
    return RequestUtil()

def test_your_case(api):
    response = api.get("https://your-api.com/endpoint")
    assert response.status_code == 200        # HTTP layer
    
    data = response.json()
    assert data["key"] == "expected value"     # Business layer
```

---

## 🎓 For Internship Preparation

This project demonstrates:

| Skill | How? |
|-------|------|
| Python OOP | `RequestUtil` class encapsulation |
| pytest | fixtures, assertions, configuration |
| API Testing | GET/POST methods, HTTP + Business assertions |
| CI/CD | Declarative Jenkinsfile |
| Logging | Dual-output logging module design |
| Git | GitHub repository management |
