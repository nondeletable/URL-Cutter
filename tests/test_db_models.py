from urlcutter.db.models.link import Link


def test_insert_and_query_link_full(db_session):
    link = Link(short_url="abc", long_url="https://example.com", service="S1")
    db_session.add(link)
    db_session.commit()

    # достаём обратно
    res = db_session.query(Link).filter_by(short_url="abc").first()

    # проверяем, что запись существует
    assert res is not None

    # проверяем поля, которые задавали
    assert res.short_url == "abc"
    assert res.long_url == "https://example.com"
    assert res.service == "S1"

    # проверяем авто-генерацию
    assert res.id is not None and res.id > 0
    assert res.created_at is not None
