"""TestForge 一键入口。

用法：
    python run.py              # 跑全部用例（接口 + UI）
    python run.py api          # 只跑接口用例（并行 4 进程）
    python run.py ui           # 只跑 Playwright UI 用例
    python run.py smoke        # 只跑冒烟用例
    python run.py faults       # 缺陷注入矩阵：逐个注入缺陷，统计用例检出率
    python run.py eval         # 失败归因评测：标注样本上的准确率/混淆矩阵
    python run.py serve        # 启动内置被测系统，浏览器访问 http://127.0.0.1:8000/ui/login
    python run.py api -k order -x          # 其余参数原样透传给 pytest
"""

import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def pytest_args(tokens: list[str]) -> list[str]:
    if not tokens:
        return []
    mode, rest = tokens[0], tokens[1:]
    if mode == "api":
        return ["-m", "not ui", "-n", "4", *rest]
    if mode == "ui":
        return ["-m", "ui", *rest]
    if mode == "smoke":
        return ["-m", "smoke", *rest]
    if mode == "serve":
        return []
    return tokens


def serve() -> int:
    os.chdir(PROJECT_ROOT)
    env = os.environ.copy()
    env["PYTHONPATH"] = PROJECT_ROOT
    return subprocess.call(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "sut.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            os.getenv("PORT", "8000"),
        ],
        cwd=PROJECT_ROOT,
        env=env,
    )


def main() -> int:
    tokens = sys.argv[1:]
    if tokens and tokens[0] == "serve":
        return serve()
    if tokens and tokens[0] == "faults":
        env = os.environ.copy()
        env["PYTHONPATH"] = PROJECT_ROOT
        return subprocess.call(
            [
                sys.executable,
                os.path.join(PROJECT_ROOT, "tools", "fault_matrix.py"),
                *tokens[1:],
            ],
            cwd=PROJECT_ROOT,
            env=env,
        )
    if tokens and tokens[0] == "eval":
        env = os.environ.copy()
        env["PYTHONPATH"] = PROJECT_ROOT
        return subprocess.call(
            [
                sys.executable,
                os.path.join(PROJECT_ROOT, "tools", "eval_triage.py"),
                *tokens[1:],
            ],
            cwd=PROJECT_ROOT,
            env=env,
        )

    os.chdir(PROJECT_ROOT)
    env = os.environ.copy()
    env["PYTHONPATH"] = PROJECT_ROOT

    print(f"TestForge · {PROJECT_ROOT}")
    print("=" * 56)

    command = [sys.executable, "-m", "pytest", *pytest_args(tokens)]
    print("执行:", " ".join(command[2:]) or "（全部用例）")
    result = subprocess.call(command, cwd=PROJECT_ROOT, env=env)

    if result == 0:
        print("\n全部用例通过。查看报告：allure serve ./allure-results")
    else:
        print("\n存在失败用例，请查看上方输出与 allure-results。")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
