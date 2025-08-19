#!/bin/bash
# Pre-commit validation script
set -e

echo "🔍 Running pre-commit validation checks..."
echo

# Check Python syntax and critical errors
echo "1️⃣ Running flake8 critical checks..."
python -m flake8 src/ tests/ --count --select=E9,F63,F7,F82 --show-source --statistics
echo "✅ No critical errors found"
echo

# Check code formatting
echo "2️⃣ Checking black formatting..."
python -m black --check --diff src/ tests/
echo "✅ Code formatting is correct"
echo

# Check import sorting
echo "3️⃣ Checking import sorting..."
python -m isort --check-only --diff src/ tests/
echo "✅ Import sorting is correct"
echo

# Run tests
echo "4️⃣ Running unit tests..."
python -m pytest tests/ --tb=short -q
echo "✅ All tests passed"
echo

# Validate package structure
echo "5️⃣ Validating package structure..."
python -c "import tomllib; tomllib.load(open('pyproject.toml', 'rb')); print('✅ pyproject.toml is valid')"
echo

echo "🎉 All checks passed! Your code is ready to be committed."
