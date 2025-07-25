# python-aapclient

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
![AI Assisted](https://img.shields.io/badge/AI%20Assisted-Yes-green)

⚠️ **This tool is under active development, features may not work entirely or as expected. Use at your own risk!!** ⚠️

A command-line client for [Ansible Automation Platform (AAP)](https://www.redhat.com/en/technologies/management/ansible) that provides a unified interface for managing AAP resources.

## Installation

While under development, this package can be installed from a local repository clone in a Python virtual environment.

```bash
git clone https://github.com/jce-redhat/python-aapclient.git
cd python-aapclient
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configuration

Configure the AAP connection using either environment variables or an `.env` file. Connection information may also be passed as command-line arguments.

### Environment Variables (Recommended)

```bash
export AAP_HOST=https://your-aap-host.example.com
# use token authentication
export AAP_TOKEN=your-token
# OR username and password authentication
export AAP_USERNAME=your-username
export AAP_PASSWORD=your-password
# Optional SSL configuration (defaults shown)
export AAP_VERIFY_SSL=true          # Enable/disable SSL certificate verification (default: true)
export AAP_CA_BUNDLE=""             # Path to custom CA certificate bundle (default: none)
```

### An .env file

Create a `.env` file in your project directory:

```bash
# Copy the example and edit with your details
cp env.example .env
```

Example `.env` file:

```bash
# Required: AAP server hostname or URL
AAP_HOST=https://aap-host.example.com/

# Authentication: Use either token OR username/password
AAP_TOKEN=your-aap-token

# OR use username/password authentication
# AAP_USERNAME=your-username
# AAP_PASSWORD=your-password

# Optional: SSL verification (default: true)
# AAP_VERIFY_SSL=false

# Optional: CA bundle for custom certificates
# AAP_CA_BUNDLE=/path/to/ca-bundle.crt

# Optional: Request timeout in seconds (default: 30)
# AAP_TIMEOUT=60
```

## Quick Start

1. **Configure authentication**:
```bash
export AAP_HOST=https://your-aap-instance.example.com
export AAP_TOKEN=your-api-token
```

2. **Enable command completion**:
```bash
source <(aap complete)
```

3. **Test connectivity**:
```bash
aap ping
```

4. **List available commands**:
```bash
aap --help
```

5. **Explore resources**:
```bash
aap organization list
aap project list
aap inventory list
```

6. **Command-specific help**:
```bash
aap team create -h
aap credential set -h
```

All commands follow a consistent pattern:

```bash
aap <resource> <action> [options] [arguments]
```

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
