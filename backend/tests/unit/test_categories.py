def test_channel_categories_constant():
    from shared.categories import CATEGORY_SLUGS, CHANNEL_CATEGORIES

    slugs = [slug for slug, _ in CHANNEL_CATEGORIES]
    titles = [title for _, title in CHANNEL_CATEGORIES]

    assert slugs == ["news", "tech", "business", "entertainment", "sports", "education"]
    assert titles == [
        "Новости",
        "Технологии",
        "Бизнес",
        "Развлечения",
        "Спорт",
        "Образование",
    ]
    assert len(set(slugs)) == len(slugs)
    assert CATEGORY_SLUGS == frozenset(slugs)
    assert isinstance(CATEGORY_SLUGS, frozenset)
