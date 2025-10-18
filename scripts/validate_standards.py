#!/usr/bin/env python3
"""
Code Standards Validator
------------------------
Validates that all services follow the AlgoTrading platform code standards.

Usage:
    python scripts/validate_standards.py --check
    python scripts/validate_standards.py --service auth_service
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SERVICES_DIR = ROOT_DIR / "services"


def check_file(file_path):
    """Check a single Python file for standards violations."""
    violations = []
    
    try:
        content = file_path.read_text(encoding='utf-8')
        lines = content.splitlines()
        
        for line_num, line in enumerate(lines, start=1):
            # Check for deprecated logger imports
            if "from common.logger import" in line:
                violations.append((
                    "deprecated_logger_import",
                    f"Use 'from core.utils.logger import get_logger' instead",
                    line_num
                ))
            
            # Check for direct logging without core wrapper
            if "import logging" in line:
                # Allow in core.utils.logger itself
                if "core\\utils\\logger.py" not in str(file_path) and "core/utils/logger.py" not in str(file_path):
                    violations.append((
                        "deprecated_logger_import",
                        f"Use 'from core.utils.logger import get_logger' instead",
                        line_num
                    ))
            
            # Check for direct YAML imports
            if "import yaml" in line or "from yaml import" in line:
                # Allow in config_loader itself and in tests
                if ("core\\utils\\config_loader.py" not in str(file_path) and 
                    "core/utils/config_loader.py" not in str(file_path) and
                    "\\tests\\" not in str(file_path) and 
                    "/tests/" not in str(file_path)):
                    violations.append((
                        "deprecated_config_import",
                        f"Use 'from core.utils.config_loader import load_config' instead",
                        line_num
                    ))
                    
    except Exception as e:
        violations.append(("read_error", f"Failed to read file: {str(e)}", 0))
    
    return violations


def check_service(service_name):
    """Check a single service for standards violations."""
    service_dir = SERVICES_DIR / service_name
    
    if not service_dir.exists():
        return {
            "service": service_name,
            "error": "Service directory not found",
            "violations": []
        }
    
    violations = []
    
    # Check all Python files
    for py_file in service_dir.rglob("*.py"):
        if "__pycache__" in str(py_file) or "venv" in str(py_file):
            continue
            
        file_violations = check_file(py_file)
        if file_violations:
            violations.append({
                "file": str(py_file.relative_to(ROOT_DIR)),
                "violations": file_violations
            })
    
    return {
        "service": service_name,
        "violations": violations
    }


def print_report(results):
    """Print validation report."""
    total_violations = 0
    
    print("\n" + "=" * 80)
    print("CODE STANDARDS VALIDATION REPORT")
    print("=" * 80 + "\n")
    
    for result in results:
        service = result["service"]
        
        if "error" in result:
            print(f"[FAIL] {service}: {result['error']}\n")
            continue
        
        violations = result["violations"]
        
        if not violations:
            print(f"[PASS] {service}: All standards met\n")
            continue
        
        print(f"[WARN] {service}: {len(violations)} file(s) with violations\n")
        total_violations += len(violations)
        
        for v in violations:
            print(f"  File: {v['file']}")
            for viol_type, message, line_num in v['violations']:
                print(f"    Line {line_num}: {message}")
            print()
    
    print("=" * 80)
    print(f"Total violations: {total_violations}")
    print("=" * 80 + "\n")
    
    if total_violations > 0:
        print("Fix suggestions:")
        print("   1. Remove duplicate utility files (logger.py, config_loader.py)")
        print("   2. Update imports to use core.utils.logger and core.utils.config_loader")
        print("   3. See docs/guides/CORE_UTILITIES.md for migration guide\n")
    
    return total_violations


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate code standards")
    parser.add_argument("--service", help="Check specific service only")
    parser.add_argument("--check", action="store_true", help="Check all services")
    
    args = parser.parse_args()
    
    if args.service:
        results = [check_service(args.service)]
    elif args.check:
        if not SERVICES_DIR.exists():
            print(f"❌ Services directory not found: {SERVICES_DIR}")
            return 1
        
        services = [d.name for d in SERVICES_DIR.iterdir() 
                   if d.is_dir() and not d.name.startswith('.')]
        results = [check_service(service) for service in services]
    else:
        parser.print_help()
        return 1
    
    violations = print_report(results)
    return 1 if violations > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
