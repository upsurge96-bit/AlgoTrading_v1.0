#!/usr/bin/env python3#!/usr/bin/env python3#!/usr/bin/env python3

"""

Code Standards Validator""""""

------------------------

Validates that all services follow the AlgoTrading platform code standards:Code Standards ValidatorCode Standards Validator

- Use core.utils.logger for logging

- Use core.utils.config_loader for configuration------------------------------------------------

- No duplicate utility files

- Consistent import patternsValidates that all services follow the AlgoTrading platform code standards:Validates that all services follow the AlgoTrading platform code standards:



Usage:- Use core.utils.logger for logging- Use core.utils.logger for logging

    python scripts/standardize_logging.py --check        # Check all services

    python scripts/standardize_logging.py --service auth_service  # Check specific service- Use core.utils.config_loader for configuration- Use core.utils.config_loader for configuration

"""

- No duplicate utility files- No duplicate utility files

import sys

from pathlib import Path- Consistent import patterns- Consistent import patterns

from typing import List, Dict, Tuple



# Root directory of the project

ROOT_DIR = Path(__file__).resolve().parent.parentUsage:Usage:

SERVICES_DIR = ROOT_DIR / "services"

    python scripts/standardize_logging.py --check        # Check all services    python scripts/standardize_logging.py --check        # Check all services

# Standards to check

STANDARDS = {    python scripts/standardize_logging.py --service auth_service  # Check specific service    python scripts/standardize_logging.py --service auth_service  # Check specific service

    "logger_import": {

        "approved": [""""""

            "from core.utils.logger import",

            "from core import get_logger",

        ],

        "deprecated": [import sysimport sys

            "from common.logger import",

            "import logging",  # Direct logging without core wrapperfrom pathlib import Pathfrom pathlib import Path

        ],

    },from typing import List, Dict, Tuplefrom typing import List, Dict, Tuple

    "config_import": {

        "approved": [

            "from core.utils.config_loader import",

            "from core import load_config",# Root directory of the project# Root directory of the project

        ],

        "deprecated": [ROOT_DIR = Path(__file__).resolve().parent.parentROOT_DIR = Path(__file__).resolve().parent.parent

            "import yaml",  # Direct YAML loading

        ],SERVICES_DIR = ROOT_DIR / "services"SERVICES_DIR = ROOT_DIR / "services"

    },

    "forbidden_files": [

        "utils/logger.py",  # Should use core.utils.logger

        "logger.py",# Standards to check# Standards to check

        "config_loader.py",  # Should use core.utils.config_loader

    ],STANDARDS = {STANDARDS = {

}

    "logger_import": {    "logger_import": {



def check_file(file_path: Path) -> List[Tuple[str, str, int]]:        "approved": [        "approved": [

    """

    Check a single Python file for standards violations.            "from core.utils.logger import",            "from core.utils.logger import",

    

    Returns:            "from core import get_logger",            "from core import get_logger",

        List of (violation_type, message, line_number) tuples

    """        ],        ],

    violations = []

            "deprecated": [        "deprecated": [

    try:

        content = file_path.read_text(encoding='utf-8')            "from common.logger import",            "from common.logger import",

        lines = content.splitlines()

                    "import logging",  # Direct logging without core wrapper            "import logging",  # Direct logging without core wrapper

        for line_num, line in enumerate(lines, start=1):

            # Check for deprecated logger imports        ],        ],

            for deprecated in STANDARDS["logger_import"]["deprecated"]:

                if deprecated in line and "import logging" in line:    },    },

                    # Allow "import logging" if it's within core.utils.logger itself

                    if "core\\utils\\logger.py" not in str(file_path) and "core/utils/logger.py" not in str(file_path):    "config_import": {    "config_import": {

                        violations.append((

                            "deprecated_logger_import",        "approved": [        "approved": [

                            f"Use 'from core.utils.logger import get_logger' instead of '{line.strip()}'",

                            line_num            "from core.utils.config_loader import",            "from core.utils.config_loader import",

                        ))

                elif deprecated in line and deprecated != "import logging":            "from core import load_config",            "from core import load_config",

                    violations.append((

                        "deprecated_logger_import",        ],        ],

                        f"Use 'from core.utils.logger import get_logger' instead of '{line.strip()}'",

                        line_num        "deprecated": [        "deprecated": [

                    ))

                        "import yaml",  # Direct YAML loading            "import yaml",  # Direct YAML loading

            # Check for direct YAML imports (should use config_loader)

            if "import yaml" in line or "from yaml import" in line:        ],        ],

                # Allow in config_loader itself and in tests

                if "core\\utils\\config_loader.py" not in str(file_path) and "core/utils/config_loader.py" not in str(file_path) and "\\tests\\" not in str(file_path) and "/tests/" not in str(file_path):    },    },

                    violations.append((

                        "deprecated_config_import",    "forbidden_files": [    "forbidden_files": [

                        f"Use 'from core.utils.config_loader import load_config' instead of '{line.strip()}'",

                        line_num        "utils/logger.py",  # Should use core.utils.logger        "utils/logger.py",  # Should use core.utils.logger

                    ))

                            "logger.py",        "logger.py",

    except Exception as e:

        violations.append((        "config_loader.py",  # Should use core.utils.config_loader        "config_loader.py",  # Should use core.utils.config_loader

            "read_error",

            f"Failed to read file: {str(e)}",    ],    ],

            0

        ))}}

    

    return violations



def list_services():

def check_forbidden_files(service_dir: Path) -> List[Tuple[str, str]]:

    """def check_file(file_path: Path) -> List[Tuple[str, str, int]]:    """List all services in the services directory."""

    Check for forbidden utility files that duplicate core utilities.

        """    services = []

    Returns:

        List of (file_path, reason) tuples    Check a single Python file for standards violations.    for item in SERVICES_DIR.iterdir():

    """

    violations = []            if item.is_dir() and not item.name.startswith('__'):

    

    for forbidden in STANDARDS["forbidden_files"]:    Returns:            services.append(item.name)

        forbidden_path = service_dir / forbidden

        if forbidden_path.exists():        List of (violation_type, message, line_number) tuples    return services

            violations.append((

                str(forbidden_path.relative_to(ROOT_DIR)),    """

                f"Duplicate utility file - should use core.utils instead"

            ))    violations = []def check_service_logger(service_name):

    

    return violations        """Check if a service is using the core logger correctly."""



    try:    service_dir = SERVICES_DIR / service_name

def check_service(service_name: str) -> Dict[str, any]:

    """        content = file_path.read_text(encoding='utf-8')    

    Check a single service for standards violations.

            lines = content.splitlines()    # Check main service files

    Returns:

        Dictionary with violation details            main_files = []

    """

    service_dir = SERVICES_DIR / service_name        for line_num, line in enumerate(lines, start=1):    for file in ["main.py", "app.py", "__init__.py", "service.py"]:

    

    if not service_dir.exists():            # Check for deprecated logger imports        if (service_dir / file).exists():

        return {

            "service": service_name,            for deprecated in STANDARDS["logger_import"]["deprecated"]:            main_files.append(service_dir / file)

            "error": "Service directory not found",

            "violations": [],                if deprecated in line and "import logging" in line:    

            "forbidden_files": []

        }                    # Allow "import logging" if it's within core.utils.logger itself    if not main_files:

    

    violations = []                    if "core/utils/logger.py" not in str(file_path):        print(f"⚠️ {service_name}: No main service file found")

    

    # Check all Python files in the service                        violations.append((        return False

    for py_file in service_dir.rglob("*.py"):

        # Skip __pycache__ and virtual environments                            "deprecated_logger_import",    

        if "__pycache__" in str(py_file) or "venv" in str(py_file):

            continue                            f"Use 'from core.utils.logger import get_logger' instead of '{line.strip()}'",    # Check if any main file imports the core logger

            

        file_violations = check_file(py_file)                            line_num    using_core_logger = False

        if file_violations:

            violations.append({                        ))    for file_path in main_files:

                "file": str(py_file.relative_to(ROOT_DIR)),

                "violations": file_violations                elif deprecated in line and deprecated != "import logging":        if file_path.exists():

            })

                        violations.append((            try:

    # Check for forbidden files

    forbidden_files = check_forbidden_files(service_dir)                        "deprecated_logger_import",                with open(file_path, 'r', encoding='utf-8') as f:

    

    return {                        f"Use 'from core.utils.logger import get_logger' instead of '{line.strip()}'",                    content = f.read()

        "service": service_name,

        "violations": violations,                        line_num                    if "core.utils.logger" in content:

        "forbidden_files": forbidden_files

    }                    ))                        using_core_logger = True



                                    break

def print_report(results: List[Dict[str, any]]) -> int:

    """            # Check for direct YAML imports (should use config_loader)            except Exception as e:

    Print validation report.

                if "import yaml" in line or "from yaml import" in line:                print(f"⚠️ {service_name}: Error reading {file_path.name}: {e}")

    Returns:

        Number of total violations found                # Allow in config_loader itself and in tests    

    """

    total_violations = 0                if "core/utils/config_loader.py" not in str(file_path) and "/tests/" not in str(file_path):    return using_core_logger

    

    print("\n" + "=" * 80)                    violations.append((

    print("CODE STANDARDS VALIDATION REPORT")

    print("=" * 80 + "\n")                        "deprecated_config_import",def fix_service_logger(service_name, dry_run=True):

    

    for result in results:                        f"Use 'from core.utils.config_loader import load_config' instead of '{line.strip()}'",    """Fix a service to use the core logger correctly."""

        service = result["service"]

                                line_num    service_dir = SERVICES_DIR / service_name

        if "error" in result:

            print(f"❌ {service}: {result['error']}\n")                    ))    

            continue

                                # Find the main file

        violations = result["violations"]

        forbidden_files = result["forbidden_files"]    except Exception as e:    main_file = None

        

        if not violations and not forbidden_files:        violations.append((    for file in ["main.py", "app.py", "service.py", "__init__.py"]:

            print(f"✅ {service}: All standards met\n")

            continue            "read_error",        if (service_dir / file).exists():

        

        print(f"⚠️  {service}: {len(violations)} file(s) with violations\n")            f"Failed to read file: {str(e)}",            main_file = service_dir / file

        total_violations += len(violations) + len(forbidden_files)

                    0            break

        # Print forbidden files

        if forbidden_files:        ))    

            print("  Forbidden Files:")

            for file_path, reason in forbidden_files:        if not main_file:

                print(f"    ❌ {file_path}")

                print(f"       Reason: {reason}\n")    return violations        print(f"⚠️ {service_name}: No main service file found to modify")

        

        # Print file violations        return False

        for v in violations:

            print(f"  File: {v['file']}")    

            for viol_type, message, line_num in v['violations']:

                print(f"    Line {line_num}: {message}")def check_forbidden_files(service_dir: Path) -> List[Tuple[str, str]]:    try:

            print()

        """        with open(main_file, 'r', encoding='utf-8') as f:

    print("=" * 80)

    print(f"Total violations: {total_violations}")    Check for forbidden utility files that duplicate core utilities.            content = f.read()

    print("=" * 80 + "\n")

                

    if total_violations > 0:

        print("💡 Fix suggestions:")    Returns:        # Check if the file already imports the core logger

        print("   1. Remove duplicate utility files (logger.py, config_loader.py)")

        print("   2. Update imports to use core.utils.logger and core.utils.config_loader")        List of (file_path, reason) tuples        if "core.utils.logger" in content:

        print("   3. See docs/guides/CORE_UTILITIES.md for migration guide\n")

        """            print(f"✓ {service_name}: Already using core logger")

    return total_violations

    violations = []            return True



def main():            

    """Main entry point."""

    import argparse    for forbidden in STANDARDS["forbidden_files"]:        # Check for other logging configurations

    

    parser = argparse.ArgumentParser(description="Validate code standards across services")        forbidden_path = service_dir / forbidden        has_logging_import = "import logging" in content

    parser.add_argument(

        "--service",        if forbidden_path.exists():        

        help="Check specific service only",

        type=str            violations.append((        # Create a backup of the file

    )

    parser.add_argument(                str(forbidden_path.relative_to(ROOT_DIR)),        if not dry_run:

        "--check",

        action="store_true",                f"Duplicate utility file - should use core.utils instead"            backup_path = main_file.with_suffix(main_file.suffix + '.bak')

        help="Check all services"

    )            ))            shutil.copy2(main_file, backup_path)

    

    args = parser.parse_args()                print(f"📄 {service_name}: Created backup at {backup_path}")

    

    if args.service:    return violations        

        # Check single service

        results = [check_service(args.service)]        # Add import paths if needed

    elif args.check:

        # Check all services        if "sys.path.append" not in content and "parent_dir" not in content:

        if not SERVICES_DIR.exists():

            print(f"❌ Services directory not found: {SERVICES_DIR}")def check_service(service_name: str) -> Dict[str, any]:            path_setup = """

            return 1

            """import sys

        services = [d.name for d in SERVICES_DIR.iterdir() if d.is_dir() and not d.name.startswith('.')]

        results = [check_service(service) for service in services]    Check a single service for standards violations.from pathlib import Path

    else:

        parser.print_help()    

        return 1

        Returns:# Add parent directory to path to resolve imports

    violations = print_report(results)

    return 1 if violations > 0 else 0        Dictionary with violation detailsparent_dir = Path(__file__).resolve().parent.parent



    """sys.path.append(str(parent_dir))

if __name__ == "__main__":

    sys.exit(main())    service_dir = SERVICES_DIR / service_name"""


                # Find a good location to insert the path setup

    if not service_dir.exists():            # Look for other imports as a guide

        return {            import_pattern = re.compile(r'^import\s+', re.MULTILINE)

            "service": service_name,            import_matches = list(import_pattern.finditer(content))

            "error": "Service directory not found",            

            "violations": [],            if import_matches:

            "forbidden_files": []                # Insert before the first import

        }                pos = import_matches[0].start()

                    new_content = content[:pos] + path_setup + content[pos:]

    violations = []            else:

                    # If no imports found, add it after any module docstring

    # Check all Python files in the service                docstring_end = content.find('"""', content.find('"""') + 3) + 3 if '"""' in content else 0

    for py_file in service_dir.rglob("*.py"):                new_content = content[:docstring_end] + "\n" + path_setup + content[docstring_end:]

        # Skip __pycache__ and virtual environments            

        if "__pycache__" in str(py_file) or "venv" in str(py_file):            content = new_content

            continue        

                    # Add core logger import

        file_violations = check_file(py_file)        if "core.utils.logger" not in content:

        if file_violations:            # Look for existing imports to decide where to insert

            violations.append({            if "import " in content:

                "file": str(py_file.relative_to(ROOT_DIR)),                # Find the last import statement

                "violations": file_violations                import_blocks = re.findall(r'((?:import|from)\s+[^;]*?)$|^(?:import|from)\s+.*?$', content, re.MULTILINE)

            })                if import_blocks:

                        last_import = content.rfind(import_blocks[-1])

    # Check for forbidden files                    end_of_imports = content.find('\n', last_import)

    forbidden_files = check_forbidden_files(service_dir)                    if end_of_imports == -1:

                            end_of_imports = len(content)

    return {                    

        "service": service_name,                    new_content = content[:end_of_imports] + LOGGER_IMPORT_PATTERN + content[end_of_imports:]

        "violations": violations,                    content = new_content

        "forbidden_files": forbidden_files            else:

    }                # If no imports found, add after path setup

                path_end = content.find('sys.path.append')

                if path_end != -1:

def print_report(results: List[Dict[str, any]]) -> int:                    path_end = content.find('\n', path_end) + 1

    """                    new_content = content[:path_end] + LOGGER_IMPORT_PATTERN + content[path_end:]

    Print validation report.                    content = new_content

            

    Returns:        # Add logger configuration

        Number of total violations found        if "setup_logging" not in content:

    """            # Find a good location for configuration

    total_violations = 0            # Typically after imports but before code

                main_func = re.search(r'def\s+main\(', content)

    print("\n" + "=" * 80)            if main_func:

    print("CODE STANDARDS VALIDATION REPORT")                # Insert before main function

    print("=" * 80 + "\n")                pos = content.rfind('\n', 0, main_func.start())

                    if pos == -1:

    for result in results:                    pos = main_func.start()

        service = result["service"]                config_text = LOGGER_CONFIG_PATTERN.format(service_name=service_name)

                        new_content = content[:pos] + config_text + content[pos:]

        if "error" in result:                content = new_content

            print(f"❌ {service}: {result['error']}\n")            else:

            continue                # Look for __name__ == "__main__" block

                        main_block = re.search(r'if\s+__name__\s*==\s*[\'"]__main__[\'"]', content)

        violations = result["violations"]                if main_block:

        forbidden_files = result["forbidden_files"]                    # Insert before main block

                            pos = content.rfind('\n', 0, main_block.start())

        if not violations and not forbidden_files:                    if pos == -1:

            print(f"✅ {service}: All standards met\n")                        pos = main_block.start()

            continue                    config_text = LOGGER_CONFIG_PATTERN.format(service_name=service_name)

                            new_content = content[:pos] + config_text + content[pos:]

        print(f"⚠️  {service}: {len(violations)} file(s) with violations\n")                    content = new_content

        total_violations += len(violations) + len(forbidden_files)                else:

                            # Add at the end of imports

        # Print forbidden files                    last_import = re.search(r'(?:import|from)\s+[^;]*$', content, re.MULTILINE)

        if forbidden_files:                    if last_import:

            print("  Forbidden Files:")                        pos = content.find('\n', last_import.end())

            for file_path, reason in forbidden_files:                        if pos == -1:

                print(f"    ❌ {file_path}")                            pos = len(content)

                print(f"       Reason: {reason}\n")                        config_text = LOGGER_CONFIG_PATTERN.format(service_name=service_name)

                                new_content = content[:pos] + config_text + content[pos:]

        # Print file violations                        content = new_content

        for v in violations:                    else:

            print(f"  File: {v['file']}")                        # Add after docstring if exists

            for viol_type, message, line_num in v['violations']:                        docstring_end = content.find('"""', content.find('"""') + 3) + 3 if '"""' in content else 0

                print(f"    Line {line_num}: {message}")                        if docstring_end > 0:

            print()                            new_content = content[:docstring_end] + "\n" + LOGGER_CONFIG_PATTERN.format(service_name=service_name) + content[docstring_end:]

                                content = new_content

    print("=" * 80)        

    print(f"Total violations: {total_violations}")        # Replace existing logging configurations

    print("=" * 80 + "\n")        if "logging.basicConfig" in content:

                content = re.sub(

    if total_violations > 0:                r'logging\.basicConfig\([^)]*\)', 

        print("💡 Fix suggestions:")                f'# Replaced with core logger\n# setup_logging(config_path="config/logging.yaml", service_name="{service_name}")', 

        print("   1. Remove duplicate utility files (logger.py, config_loader.py)")                content

        print("   2. Update imports to use core.utils.logger and core.utils.config_loader")            )

        print("   3. See docs/guides/CORE_UTILITIES.md for migration guide\n")        

            # Write the modified content

    return total_violations        if not dry_run:

            with open(main_file, 'w', encoding='utf-8') as f:

                f.write(content)

def main():            print(f"✅ {service_name}: Updated {main_file.name} to use core logger")

    """Main entry point."""        else:

    import argparse            print(f"🔍 {service_name}: Would update {main_file.name} (dry run)")

            

    parser = argparse.ArgumentParser(description="Validate code standards across services")        # Ensure utils directory exists

    parser.add_argument(        utils_dir = service_dir / "utils"

        "--service",        if not utils_dir.exists() and not dry_run:

        help="Check specific service only",            utils_dir.mkdir(exist_ok=True)

        type=str            print(f"📁 {service_name}: Created utils directory")

    )        

    parser.add_argument(        # Check for local logger implementations and create wrapper if needed

        "--check",        local_logger = service_dir / "utils" / "logger.py"

        action="store_true",        if local_logger.exists():

        help="Check all services"            # Analyze if it's a custom implementation or a wrapper

    )            try:

                    with open(local_logger, 'r', encoding='utf-8') as f:

    args = parser.parse_args()                    local_logger_content = f.read()

                    

    if args.service:                if "core.utils.logger" not in local_logger_content:

        # Check single service                    # Create a wrapper that delegates to core logger

        results = [check_service(args.service)]                    wrapper_content = """\"\"\"

    elif args.check:Logger Module (Wrapper)

        # Check all services-----------------------

        if not SERVICES_DIR.exists():DEPRECATED: This module is a wrapper around core.utils.logger.

            print(f"❌ Services directory not found: {SERVICES_DIR}")Please use core.utils.logger directly in new code.

            return 1\"\"\"

        

        services = [d.name for d in SERVICES_DIR.iterdir() if d.is_dir() and not d.name.startswith('.')]import warnings

        results = [check_service(service) for service in services]import sys

    else:from pathlib import Path

        parser.print_help()

        return 1# Add parent directory to path to resolve imports

    try:

    violations = print_report(results)    parent_dir = Path(__file__).resolve().parent.parent.parent

    return 1 if violations > 0 else 0    sys.path.append(str(parent_dir))

    

    # Import from core logger

if __name__ == "__main__":    from core.utils.logger import setup_logging, get_logger

    sys.exit(main())except ImportError:

    # Fallback to basic logging if core logger is not available
    import logging
    
    def setup_logging(config_path=None, service_name="{service_name}", **kwargs):
        \"\"\"Fallback logging setup.\"\"\"
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        print(f"⚠️ Using fallback logging configuration for {service_name}")
    
    def get_logger(name):
        \"\"\"Get a basic logger.\"\"\"
        return logging.getLogger(name)
    
# Show deprecation warning
warnings.warn(
    "{service_name}.utils.logger is deprecated. Use core.utils.logger instead.",
    DeprecationWarning,
    stacklevel=2
)
"""
                    if not dry_run:
                        # Backup the original local logger
                        local_logger_backup = local_logger.with_suffix(local_logger.suffix + '.bak')
                        shutil.copy2(local_logger, local_logger_backup)
                        print(f"📄 {service_name}: Created backup of local logger at {local_logger_backup}")
                        
                        # Write the wrapper
                        with open(local_logger, 'w', encoding='utf-8') as f:
                            f.write(wrapper_content.format(service_name=service_name))
                        print(f"✅ {service_name}: Created wrapper for local logger")
                    else:
                        print(f"🔍 {service_name}: Would create wrapper for local logger (dry run)")
            except Exception as e:
                print(f"⚠️ {service_name}: Error processing local logger: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ {service_name}: Error fixing logger: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Standardize logging across services")
    parser.add_argument("--check", action="store_true", help="Only check services, don't modify")
    parser.add_argument("--fix", action="store_true", help="Fix services that don't use core logger")
    parser.add_argument("--service", help="Only process a specific service")
    
    args = parser.parse_args()
    
    services = [args.service] if args.service else list_services()
    
    if not services:
        print("No services found in the services directory")
        return
    
    print(f"Found {len(services)} services: {', '.join(services)}")
    
    if args.check or not args.fix:
        # Check mode
        results = {}
        for service in services:
            using_core_logger = check_service_logger(service)
            results[service] = using_core_logger
            status = "✅ Using core logger" if using_core_logger else "❌ Not using core logger"
            print(f"{service}: {status}")
        
        # Summary
        compliant = sum(1 for s in results.values() if s)
        print(f"\nSummary: {compliant}/{len(services)} services using core logger")
        
        if not args.fix:
            print("\nRun with --fix to update non-compliant services")
    
    if args.fix:
        # Fix mode
        print("\nFixing services to use core logger...")
        for service in services:
            if not check_service_logger(service):
                print(f"\nUpdating {service}...")
                fix_service_logger(service, dry_run=False)
            else:
                print(f"✓ {service}: Already using core logger")

if __name__ == "__main__":
    main()