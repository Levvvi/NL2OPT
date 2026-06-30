def test_import_nl2opt_exposes_version():
    import nl2opt

    assert hasattr(nl2opt, "__version__")
