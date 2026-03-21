# Contributing to FarmVision

Thank you for your interest in contributing to FarmVision! This document provides guidelines and instructions for contributing to the project.

## Getting Started

1.  **Fork the repository** on GitHub.
2.  **Clone your fork** locally:
    ```bash
    git clone https://github.com/YOUR_USERNAME/farmvision.git
    cd farmvision
    ```
3.  **Set up your environment**:
    - Follow the "Development & Testing" section in `README.md`.
    - Create a virtual environment and install dependencies:
      ```bash
      python -m venv venv
      source venv/bin/activate  # Windows: .\venv\Scripts\activate
      pip install -r requirements.txt
      ```

## Development Process

1.  **Create a branch** for your feature or bugfix:
    ```bash
    git checkout -b feature/my-new-feature
    # or
    git checkout -b fix/issue-description
    ```
2.  **Make your changes**. Keep changes focused and atomic.
3.  **Run tests** locally to ensure no regressions:
    ```bash
    python manage.py test --settings=yolowebapp2.test_settings
    # or if you have pytest installed
    pytest
    ```
4.  **Check for issues** using Django's check command:
    ```bash
    python manage.py check
    ```

## Code Style

- **Python**: Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) guidelines.
- **Django**: Follow standard Django coding style and best practices.
- **Imports**: Group imports as follows:
    1.  Standard library imports
    2.  Third-party library imports (Django, DRF, etc.)
    3.  Local application imports
- **Formatting**: We recommend using `black` for code formatting.

## Pull Request Process

1.  **Push your branch** to your fork:
    ```bash
    git push origin feature/my-new-feature
    ```
2.  **Open a Pull Request (PR)** against the `main` branch of the original repository.
3.  **Description**: Provide a clear title and description of your changes. Link to any relevant issues.
4.  **Review**: Wait for code review. Be ready to address feedback.
5.  **Merge**: Once approved, your PR will be merged.

## Reporting Issues

If you find a bug or have a feature request, please open an issue on the GitHub repository. Provide as much detail as possible, including steps to reproduce the issue.

Thank you for contributing!
