![Banner](banner.png)

# codeintel-Dependency-Update-Notifier
Scans project dependencies and notifies the user if there are newer versions available, potentially including security updates. Uses `pip` and `packaging`. - Focused on Tools for static code analysis, vulnerability scanning, and code quality assurance

Every run prints a closing summary with probed, updated, and unknown counts. The run exits 1 when any checked package ended unknown. The line saying all dependencies are up to date is printed only when every checked package was probed successfully and none has an update waiting. Under --check-security, the run exits 1 when the safety tool is missing or the safety run itself fails.

## Install
`git clone https://github.com/ShadowStrikeHQ/codeintel-dependency-update-notifier`

## Usage
`./codeintel-dependency-update-notifier [params]`

## Parameters
- `-h`: Show help message and exit
- `-r`: Path to the requirements.txt file.
- `-p`: Path to the project directory. Defaults to current directory.
- `-v`: Enable verbose logging.
- `--check-security`: Check for known security vulnerabilities using safety.

## License
Copyright (c) ShadowStrikeHQ
