def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: needs Hailo runtime, device, and STDC1/StereoNet HEF files",
    )
