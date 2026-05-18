# TestForge | 接口自动化测试框架

基于 pytest + requests + Allure 的接口自动化测试框架，用于学习与实习准备。

---

## 🎯 功能特性

| 功能 | 状态 | 位置 |
|---------|--------|------|
| ✅ **GET 请求封装** | 已完成 | [test_user_api.py](tests/test_user_api.py) |
| ✅ **POST 请求封装** | 已完成 | [test_post_api.py](tests/test_post_api.py) |
| ✅ **通用请求工具类** | 已完成 | [common/request_util.py](common/request_util.py) |
| ✅ **日志模块** | 已完成 | [common/log_util.py](common/log_util.py) |
| ✅ **Allure 测试报告** | 已完成 | [pytest.ini](pytest.ini) |
| ✅ **Jenkins 流水线** | 已完成 | [Jenkinsfile](Jenkinsfile) |

---

## 🛠️ 技术栈

- **Python** 编程语言
- **pytest** - 测试框架
- **requests** - HTTP 客户端
- **Allure** - 可视化测试报告
- **Jenkins** - CI/CD 持续集成流水线

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 运行全部测试

Windows PowerShell（先进入正确目录）：

```powershell
cd D:\codecode\testforge\testforge
$env:PYTHONPATH = "D:\codecode\testforge\testforge"
python -m pytest -v
```

你会看到：
```
collected 3 items

tests/test_demo.py::test_get_request PASSED
tests/test_post_api.py::test_create_post PASSED
tests/test_user_api.py::test_get_user PASSED
```

### 3. 生成 Allure 报告

```bash
# 测试结果自动输出到 ./allure-results/
# 直接运行：
allure serve ./allure-results
```

---

## 📁 项目结构

```
testforge/
├── common/                  # 工具类目录
│   ├── request_util.py      # GET/POST 请求封装
│   └── log_util.py          # 控制台+文件双输出日志
├── tests/                    # 测试用例目录
│   ├── test_demo.py         # 基础连通性测试
│   ├── test_user_api.py     # GET /users/1 业务断言
│   └── test_post_api.py     # POST /posts JSON 请求
├── Jenkinsfile               # CI/CD 流水线配置
├── pytest.ini                # pytest + Allure 配置
├── requirements.txt          # 依赖清单: pytest/requests/allure-pytest
├── jenkins-guide.md          # Jenkins 分步配置手册
└── README.md                 # 本文档
```

---

## 📝 编写你自己的测试

```python
import pytest
from common.request_util import RequestUtil

@pytest.fixture
def api():
    return RequestUtil()

def test_your_case(api):
    response = api.get("https://你的接口地址/endpoint")
    assert response.status_code == 200        # HTTP 层断言
    
    data = response.json()
    assert data["key"] == "预期值"             # 业务层断言
```

---

## 🎓 用于实习简历

这个项目展示了以下技能：

| 技能 | 如何体现 |
|-------|------|
| Python 面向对象 | `RequestUtil` 类封装设计 |
| pytest 框架 | fixture 依赖注入、断言设计、配置管理 |
| 接口测试 | GET/POST 方法封装、HTTP + 业务双层断言 |
| CI/CD 持续集成 | Declarative 风格 Jenkinsfile 流水线 |
| 日志模块 | 控制台+文件双输出日志模块设计 |
| 版本控制 | GitHub 代码仓库管理 |

---

---

# English Version

A pytest-based API automation testing framework for learning and internship preparation.

---

## 🎯 Features

| Feature | Status | Location |
|---------|--------|------|
| ✅ **GET Request** | Done | [test_user_api.py](tests/test_user_api.py) |
| ✅ **POST Request** | Done | [test_post_api.py](tests/test_post_api.py) |
| ✅ **Request Utility** | Done | [common/request_util.py](common/request_util.py) |
| ✅ **Logging** | Done | [common/log_util.py](common/log_util.py) |
| ✅ **Allure Report** | Done | [pytest.ini](pytest.ini) |
| ✅ **Jenkins Pipeline** | Done | [Jenkinsfile](Jenkinsfile) |

---

## 🛠️ Tech Stack

- **Python** Programming Language
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

Windows PowerShell (enter correct directory first):

```powershell
cd D:\codecode\testforge\testforge
$env:PYTHONPATH = "D:\codecode\testforge\testforge"
python -m pytest -v
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
├── jenkins-guide.md          # Step-by-step Jenkins guide
└── README.md                 # This document
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
