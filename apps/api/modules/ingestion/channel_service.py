import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from modules.ingestion.models import KnowledgeSource


async def resolve_channel_id(channel_identifier: str) -> str:
    """Resolve a channel handle or URL to a channel ID using YouTube Data API."""
    if not channel_identifier or not channel_identifier.strip():
        raise ValueError(
            "Channel identifier is empty. Please set your YouTube channel in settings."
        )
    if channel_identifier.startswith("UC") and len(channel_identifier) == 24:
        return channel_identifier
    handle = channel_identifier.lstrip("@")
    async with httpx.AsyncClient() as client:
        # Use forHandle — official way to resolve @handles reliably
        resp = await client.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "id", "forHandle": handle, "key": settings.youtube_api_key},
            timeout=30,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if items:
            return items[0]["id"]
        # Fallback to search
        resp2 = await client.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet", "q": handle,
                "type": "channel", "maxResults": 1,
                "key": settings.youtube_api_key,
            },
            timeout=30,
        )
        resp2.raise_for_status()
        items2 = resp2.json().get("items", [])
        if not items2:
            raise ValueError(f"Could not find YouTube channel: {channel_identifier}")
        return items2[0]["snippet"]["channelId"]



async def get_uploads_playlist_id(channel_id: str) -> str:
    """Get the uploads playlist ID for a channel."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={
                "part": "contentDetails",
                "id": channel_id,
                "key": settings.youtube_api_key,
            },
            timeout=30,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            raise ValueError(f"Could not retrieve channel details for {channel_id}")
        return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


async def fetch_channel_videos_page(
    playlist_id: str,
    page_token: str | None = None,
    per_page: int = 10,
) -> dict:
    """Fetch a page of videos from a playlist."""
    params = {
        "part": "snippet,contentDetails",
        "playlistId": playlist_id,
        "maxResults": per_page,
        "key": settings.youtube_api_key,
    }
    if page_token:
        params["pageToken"] = page_token

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://www.googleapis.com/youtube/v3/playlistItems",
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()


async def get_channel_videos(
    db: AsyncSession,
    tenant_id: str,
    channel_identifier: str,
    page_token: str | None = None,
    per_page: int = 10,
) -> dict:
    """
    Fetch paginated channel videos with ingestion status for each video.
    Returns videos list, next_page_token, total_results.
    """
    channel_id = await resolve_channel_id(channel_identifier)
    playlist_id = await get_uploads_playlist_id(channel_id)
    data = await fetch_channel_videos_page(playlist_id, page_token, per_page)

    # Check which videos are already in the knowledge base
    existing = await db.execute(
        select(KnowledgeSource.original_url, KnowledgeSource.status).where(
            KnowledgeSource.tenant_id == tenant_id,
            KnowledgeSource.source_type == "youtube",
        )
    )
    existing_urls = {
        row.original_url: row.status for row in existing.fetchall()
    }

    videos = []
    for item in data.get("items", []):
        video_id = item["contentDetails"]["videoId"]
        snippet = item["snippet"]
        url = f"https://www.youtube.com/watch?v={video_id}"
        videos.append({
            "video_id": video_id,
            "url": url,
            "title": snippet.get("title", ""),
            "description": snippet.get("description", "")[:200],
            "thumbnail": (
                snippet.get("thumbnails", {}).get("medium", {}).get("url") or
                snippet.get("thumbnails", {}).get("default", {}).get("url")
            ),
            "published_at": snippet.get("publishedAt", ""),
            "status": existing_urls.get(url),
        })

    return {
        "videos": videos,
        "next_page_token": data.get("nextPageToken"),
        "prev_page_token": data.get("prevPageToken"),
        "total_results": data.get("pageInfo", {}).get("totalResults", 0),
        "channel_id": channel_id,
    }
