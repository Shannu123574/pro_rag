import subprocess
import json
import sys

def main():
    print("Running regression checks...")
    result = subprocess.run(["pytest", "tests/", "-q", "--tb=short"], capture_output=True, text=True)
    
    passed = result.returncode == 0
    report = {
        "status": "PASS" if passed else "FAIL",
        "output": result.stdout,
        "errors": result.stderr,
    }
    
    with open("regression_report.json", "w") as f:
        json.dump(report, f, indent=2)
        
    print(f"Regression check {'PASSED' if passed else 'FAILED'}.")
    print("Report saved to regression_report.json")
    
    if not passed:
        print(result.stdout)
        sys.exit(1)

if __name__ == "__main__":
    main()
