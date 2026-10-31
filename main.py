import argparse
import logging
import subprocess
import json
from packaging import version
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def setup_argparse():
    """
    Sets up the argument parser for the command-line interface.
    """
    parser = argparse.ArgumentParser(description="Scans project dependencies and notifies if newer versions are available.")
    parser.add_argument("-r", "--requirements", type=str, help="Path to a requirements file. When given, only the packages named in it are checked.", default=None)
    parser.add_argument("-p", "--project_path", type=str, help="Path to the project directory. Defaults to current directory.", default=".")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging.")
    parser.add_argument("--check-security", action="store_true", help="Check for known security vulnerabilities using safety.")
    return parser.parse_args()

def get_installed_packages(project_path):
    """
    Retrieves the list of installed packages within the specified project path using pip.
    Handles potential errors during the pip execution.
    """
    try:
        # Construct the command to list installed packages
        command = ["pip", "list", "--format=json"]
        if project_path != ".":
            command.extend(["--path", project_path])

        result = subprocess.run(command, capture_output=True, text=True, check=True)
        
        # Parse the JSON output from pip list
        installed_packages = json.loads(result.stdout)
        return installed_packages
    except subprocess.CalledProcessError as e:
        logging.error(f"Error listing installed packages: {e}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON output from pip: {e}")
        return None
    except FileNotFoundError:
         logging.error("pip not found. Ensure pip is installed and in your PATH.")
         return None
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return None

def get_latest_package_version(package_name):
    """
    Retrieves the latest available version of a package from PyPI using pip.
    Handles potential errors during the pip execution.
    """
    try:
        result = subprocess.run(["pip", "install", f"{package_name}==NonExistentVersion"], capture_output=True, text=True, check=False)
        output = result.stderr
        
        # Extract the latest version from the pip output
        start_index = output.find("(from versions:")
        if start_index == -1:
            logging.warning(f"Could not determine the latest version for {package_name}")
            return None

        start_index += len("(from versions:")
        end_index = output.find(")", start_index)
        if end_index == -1:
            logging.warning(f"Could not determine the latest version for {package_name}")
            return None
        
        versions_str = output[start_index:end_index].strip()
        if versions_str.lower() == "none":
            logging.warning(f"Could not determine the latest version for {package_name}")
            return None
        versions = [v.strip() for v in versions_str.split(",")]
        if not versions:
             logging.warning(f"Could not determine the latest version for {package_name}")
             return None
        
        # Return the last version in the list, assuming pip orders them chronologically
        return versions[-1]

    except subprocess.CalledProcessError as e:
        logging.error(f"Error getting latest version for {package_name}: {e}")
        return None
    except FileNotFoundError:
         logging.error("pip not found. Ensure pip is installed and in your PATH.")
         return None
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return None
    

def parse_requirement_names(requirements_path):
    # Only the names matter here: the installed version comes from pip
    # list, so specifiers, extras and markers on a line are dropped.
    # Returns None when the file cannot be read, so main can fail loudly
    # instead of silently checking every installed package instead.
    names = set()
    try:
        with open(requirements_path) as f:
            for line in f:
                line = line.split("#", 1)[0].strip()
                if not line or line.startswith("-"):
                    continue
                for sep in ("==", ">=", "<=", "!=", "~=", ">", "<", "[", ";"):
                    line = line.split(sep, 1)[0]
                name = line.strip().lower().replace("_", "-")
                if name and " " not in name:
                    names.add(name)
    except OSError as e:
        logging.error(f"Could not read requirements file {requirements_path}: {e}")
        return None
    return names


def check_for_updates(installed_packages):
    """
    Compares the installed package versions with the latest available versions and
    identifies packages with potential updates.
    """
    updates_available = []
    probed_count = 0
    unknown_count = 0

    if installed_packages is None:
        logging.error("No installed packages found. Exiting.")
        return updates_available, probed_count, unknown_count

    for package in installed_packages:
        package_name = package['name']
        installed_version = package['version']
        
        latest_version = get_latest_package_version(package_name)

        if latest_version:
            probed_count += 1
            try:
                if version.parse(installed_version) < version.parse(latest_version):
                    updates_available.append({
                        "name": package_name,
                        "installed_version": installed_version,
                        "latest_version": latest_version
                    })
                    logging.info(f"Update available for {package_name}: Installed version {installed_version}, latest version {latest_version}")
            except version.InvalidVersion as e:
                unknown_count += 1
                logging.warning(f"Invalid version format for {package_name}: {e}")
        else:
            unknown_count += 1
            logging.warning(f"Could not retrieve latest version for {package_name}. Skipping update check.")

    return updates_available, probed_count, unknown_count

def check_security_vulnerabilities(project_path):
    """
    Checks for known security vulnerabilities in the project's dependencies using the 'safety' tool.
    Requires 'safety' to be installed.
    """
    try:
        command = ["safety", "check", "--full-report"]
        if project_path != ".":
            command.extend(["--project", project_path])

        result = subprocess.run(command, capture_output=True, text=True, check=False) # Don't check=True, handle return codes explicitly
        
        if result.returncode == 0:
            logging.info("No known security vulnerabilities found.")
            return True
        elif result.returncode == 1:
            logging.warning("Security vulnerabilities found:")
            logging.warning(result.stdout) # Display the safety output
            return True
        else:
             logging.error(f"Safety check failed with return code {result.returncode}: {result.stderr}")
             return False

    except FileNotFoundError:
        logging.error("Safety not found. Please install it using: pip install safety")
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred during safety check: {e}")
        return False

def main():
    """
    Main function to execute the dependency update notifier.
    """
    args = setup_argparse()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logging.info("Starting dependency update check...")
    
    installed_packages = get_installed_packages(args.project_path)

    if installed_packages and args.requirements:
        wanted = parse_requirement_names(args.requirements)
        if wanted is None:
            sys.exit(1)
        # pip list spells names as installed; requirement files use the
        # same PEP 503 normalisation, so compare on the normalised form.
        installed_packages = [
            pkg for pkg in installed_packages
            if pkg["name"].lower().replace("_", "-") in wanted
        ]
        logging.info(f"Checking {len(installed_packages)} package(s) named in {args.requirements}.")

    exit_code = 0
    if installed_packages:
        updates_available, probed_count, unknown_count = check_for_updates(installed_packages)
        checked_count = len(installed_packages)
        print(f"Summary: probed={probed_count} updated={len(updates_available)} unknown={unknown_count}")

        if updates_available:
            print("Updates available:")
            for update in updates_available:
                print(f"- {update['name']}: Installed version {update['installed_version']}, latest version {update['latest_version']}")
        elif unknown_count == 0 and probed_count == checked_count:
            print("All dependencies are up to date.")
        else:
            print("Update check incomplete: some packages could not be checked.")
        if unknown_count > 0:
            exit_code = 1
    else:
        logging.error("Failed to retrieve installed packages. Check logs for details.")
        sys.exit(1)

    if args.check_security:
        logging.info("Checking for security vulnerabilities...")
        if not check_security_vulnerabilities(args.project_path):
            logging.error("Security check did not complete: safety is missing or the safety run failed.")
            exit_code = 1

    logging.info("Dependency update check complete.")
    if exit_code:
        sys.exit(exit_code)

if __name__ == "__main__":
    main()