def test_base_metadata_is_naming_convention():
    from shared.models.base import Base
    nc = Base.metadata.naming_convention
    assert nc["ix"].startswith("ix_")
    assert nc["uq"].startswith("uq_")
    assert nc["pk"].startswith("pk_")
