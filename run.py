import os
import sys
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

os.environ["PYTHONPATH"] = PROJECT_ROOT
os.chdir(PROJECT_ROOT)

if __name__ == "__main__":
    args = sys.argv[1:] if len(sys.argv) > 1 else ["-v"]
    
    if "run" in args:
        args.remove("run")
    
    if not any(a.startswith("-") for a in args):
        args.insert(0, "-v")
    
    print(f"TestForge - Project Root: {PROJECT_ROOT}")
    print("=" * 50)
    
    result = subprocess.run(
        [sys.executable, "-m", "pytest"] + args,
        cwd=PROJECT_ROOT,
        env=os.environ,
    )
    
    if result.returncode == 0:
        print("\nAll tests passed!")
        print("To view Allure report: allure serve allure-results")
