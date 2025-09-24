from datetime import UTC, datetime

from app.db.models import RSSFeed, RSSFeedResponse, RSSFeedStatus


def test_rss_feed_response_from_model():
    now = datetime.now(UTC)
    feed = RSSFeed(
        name="Test Feed",
        url="https://example.com/rss",
        categories=["tech"],
        tags=["deals"],
        poll_interval_minutes=15,
        next_poll_at=now,
        last_polled_at=None,
        status=RSSFeedStatus.ACTIVE,
        error_streak=2,
        health_score=0.8,
        last_error="timeout",
        created_at=now,
        updated_at=now,
    )

    response = RSSFeedResponse.from_model(feed)

    assert response.id == str(feed.id)
    assert response.name == feed.name
    assert response.url == feed.url
    assert response.categories == feed.categories
    assert response.poll_interval_minutes == feed.poll_interval_minutes
    assert response.status == feed.status
    assert response.error_streak == feed.error_streak
    assert response.health_score == feed.health_score
    assert response.last_error == feed.last_error
