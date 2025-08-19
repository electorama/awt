# Testing Best Practices

## Standard Test Structure

### Test Case Naming
Use format: `{module}_NNN[_optional_descriptor]`
- Examples: `performance_001`, `performance_002_nocache`, `integration_001_star_voting`
- Sequential numbering ensures consistent ordering and easy reference

### File Organization Pattern
```python
# 1. Test case definitions
TEST_CASES = [
    {"id": "module_001", "param1": "value1", "param2": "value2"},
    {"id": "module_002_variant", "param1": "alt_value", "param2": "value2"},
]

# 2. Parametrized fixtures
@pytest.fixture(params=TEST_CASES, ids=lambda c: c["id"])
def test_case(request):
    return request.param

# 3. Single test function (preferred)
def test_module_functionality(test_case, other_fixtures):
    # Implementation using test_case["param1"], etc.
```

### Multiple Test Functions
Should be **exceptionally rare**. Use only when:
- Fundamentally different test categories that can't be parametrized
- Different fixture requirements that create complex dependency chains
- Performance testing vs functional testing with different timeouts/resources

## Current Issues for 0.34+ Improvement

### test_performance.py
- **Remove `indirect=True` parametrization**: Use parametrized fixture pattern instead
- **Consolidate three near-identical functions**: Single parametrized test function
- **Fix fixture scope**: `awt_server` should be function-scoped, not session-scoped for performance tests

### conftest.py 
- **Standardize fixture naming**: Some fixtures use inconsistent naming patterns
- **Add timeout configuration**: Performance tests need configurable timeouts via environment variables

### Integration Tests
- **Replace manual server startup**: Multiple test files duplicate server management logic
- **Centralize URL building**: Path construction scattered across test files
- **Add election data fixtures**: Tests hardcode election IDs instead of using parametrized data sets

### Test Data Management
- **Missing test election registry**: Tests assume specific election files exist without verification
- **No test data validation**: Large election files (sf2024-mayor) used without size/timing guards
- **Hardcoded paths**: ABIFTOOL_DIR pattern repeated instead of centralized fixture