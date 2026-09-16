import ipaddress
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024  # 2MB maximum per manifest file
REQUEST_TIMEOUT_SECONDS = 15.0


class IngestionSecurityError(Exception):
    pass


class GitHubAPIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def validate_and_parse_github_url(url: str) -> tuple[str, str]:
    """
    Strictly validates a public GitHub repository URL against SSRF and illegal paths.
    Returns (owner, repo).
    """
    if not url or not isinstance(url, str):
        raise IngestionSecurityError("Repository URL must be a non-empty string.")

    url_clean = url.strip()
    parsed = urlparse(url_clean)

    if parsed.scheme.lower() != "https":
        raise IngestionSecurityError(f"Unsupported URL scheme: '{parsed.scheme}'. Only HTTPS is permitted.")

    hostname = (parsed.hostname or "").lower()
    if hostname not in ("github.com", "www.github.com"):
        raise IngestionSecurityError(
            f"Invalid repository host '{hostname}'. Only public repositories hosted on 'github.com' are supported."
        )

    # Check for IP literal addresses or SSRF indicators in hostname
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
            raise IngestionSecurityError("Access to internal/private IP space is strictly prohibited.")
    except ValueError:
        pass

    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(path_parts) < 2:
        raise IngestionSecurityError("Invalid GitHub repository URL format. Expected 'https://github.com/owner/repository'.")

    owner = path_parts[0]
    repo = path_parts[1]

    if repo.endswith(".git"):
        repo = repo[:-4]

    ident_pattern = re.compile(r"^[a-zA-Z0-9_.-]+$")
    if not ident_pattern.match(owner) or not ident_pattern.match(repo):
        raise IngestionSecurityError(f"Invalid owner or repository identifier in URL: '{owner}/{repo}'.")

    return owner, repo


class GitHubClient:
    def __init__(self, token: Optional[str] = None, timeout: float = REQUEST_TIMEOUT_SECONDS, client: Optional[httpx.AsyncClient] = None):
        self.token = token
        self.timeout = timeout
        self._external_client = client

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "OpenRobo-Registry-Ingestion/0.1.0"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def get_repository_metadata(self, owner: str, repo: str) -> Dict[str, Any]:
        url = f"https://api.github.com/repos/{owner}/{repo}"
        headers = self._get_headers()

        if self._external_client:
            resp = await self._external_client.get(url, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers=headers)

        if resp.status_code == 404:
            raise GitHubAPIError(f"Repository '{owner}/{repo}' not found on GitHub.", status_code=404)
        elif resp.status_code in (403, 429):
            raise GitHubAPIError(
                f"GitHub API rate limit exceeded while accessing '{owner}/{repo}'. Provide GITHUB_TOKEN for higher limits.",
                status_code=resp.status_code,
            )
        elif resp.status_code != 200:
            raise GitHubAPIError(f"GitHub API returned error {resp.status_code}: {resp.text[:200]}", status_code=resp.status_code)

        return resp.json()

    async def get_head_commit_sha(self, owner: str, repo: str, branch: str) -> Optional[str]:
        url = f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}"
        headers = self._get_headers()

        try:
            if self._external_client:
                resp = await self._external_client.get(url, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.get(url, headers=headers)

            if resp.status_code == 200:
                data = resp.json()
                return data.get("sha")
        except Exception:
            pass
        return None

    async def get_repository_tree(self, owner: str, repo: str, branch: str) -> List[Dict[str, Any]]:
        url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
        headers = self._get_headers()

        if self._external_client:
            resp = await self._external_client.get(url, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers=headers)

        if resp.status_code == 200:
            data = resp.json()
            return data.get("tree", [])
        return []

    async def get_raw_file_content(self, owner: str, repo: str, branch: str, file_path: str) -> str:
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{file_path}"
        headers = {"User-Agent": "OpenRobo-Registry-Ingestion/0.1.0"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"

        if self._external_client:
            resp = await self._external_client.get(url, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers=headers)

        if resp.status_code == 200:
            if len(resp.content) > MAX_FILE_SIZE_BYTES:
                raise IngestionSecurityError(f"File '{file_path}' exceeds maximum allowable size of {MAX_FILE_SIZE_BYTES} bytes.")
            return resp.text
        elif resp.status_code == 404:
            raise GitHubAPIError(f"File '{file_path}' not found in repository '{owner}/{repo}'.", status_code=404)
        else:
            raise GitHubAPIError(f"Failed to fetch file '{file_path}': status {resp.status_code}", status_code=resp.status_code)
