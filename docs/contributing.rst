Contributing
============

We welcome contributions to cpcbfetch! This guide will help you get started.

Development Setup
-----------------

1. Fork the repository on GitHub
2. Clone your fork locally:

.. code-block:: bash

   git clone https://github.com/yourusername/cpcbfetch.git
   cd cpcbfetch

3. Set up the development environment:

.. code-block:: bash

   # Create a virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate

   # Install in development mode
   pip install -e ".[dev]"

   # Set up pre-commit hooks
   pre-commit install

Code Style
----------

We use several tools to maintain code quality:

- **Black**: Code formatting
- **isort**: Import sorting  
- **flake8**: Linting
- **mypy**: Type checking

Run all checks:

.. code-block:: bash

   make lint
   make format

Testing
-------

Run the test suite:

.. code-block:: bash

   # Run all tests
   make test

   # Run with coverage
   make test-cov

Writing tests for new features:

.. code-block:: python

   import pytest
   from cpcbfetch import AQIClient

   def test_get_state_list():
       client = AQIClient()
       states = client.get_state_list()
       assert isinstance(states, list)
       assert len(states) > 0

Documentation
-------------

Documentation is built with Sphinx. To build locally:

.. code-block:: bash

   make docs

   # Serve locally
   make docs-serve

The documentation will be available at http://localhost:8000.

Submitting Changes
------------------

1. Create a new branch for your feature:

.. code-block:: bash

   git checkout -b feature/your-feature-name

2. Make your changes and add tests
3. Ensure all tests pass and code style is correct:

.. code-block:: bash

   make test
   make lint

4. Commit your changes:

.. code-block:: bash

   git add .
   git commit -m "Add your feature description"

5. Push to your fork:

.. code-block:: bash

   git push origin feature/your-feature-name

6. Create a Pull Request on GitHub

Guidelines
----------

Code Quality
~~~~~~~~~~~~

- Write clear, readable code with meaningful variable names
- Add docstrings to all public functions and classes
- Include type hints where appropriate
- Follow existing code patterns and conventions

Testing
~~~~~~~

- Write tests for new functionality
- Ensure tests are isolated and don't depend on external services
- Mock external API calls in tests
- Aim for good test coverage

Documentation
~~~~~~~~~~~~~

- Update documentation for new features
- Include code examples in docstrings
- Add entries to the changelog
- Ensure documentation builds without warnings

Commit Messages
~~~~~~~~~~~~~~~

Use clear, descriptive commit messages:

- Start with a verb in imperative mood
- Keep the first line under 50 characters
- Use the body to explain what and why, not how

Example:

.. code-block:: text

   Add PM2.5 data aggregation feature

   - Implement monthly aggregation function
   - Add support for custom time ranges
   - Include error handling for missing data

Bug Reports
-----------

When reporting bugs, please include:

- Python version
- cpcbfetch version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Error messages (if any)

Feature Requests
----------------

For feature requests, please describe:

- The use case for the feature
- How it would be used
- Any alternative solutions considered
- Whether you're willing to implement it

Release Process
---------------

Releases are handled by maintainers:

1. Update version in ``__init__.py`` and ``pyproject.toml``
2. Update ``CHANGELOG.md``
3. Create a git tag
4. Build and upload to PyPI
5. Update documentation

License
-------

By contributing to cpcbfetch, you agree that your contributions will be licensed under the MIT License.