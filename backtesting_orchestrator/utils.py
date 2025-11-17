# backtesting_orchestrator/utils.py
"""Utility functions for backtesting orchestrator."""
import os
import base64
import logging
import time
import requests
from typing import Optional


def get_file_sha_from_github(path_from_repo_root: str) -> Optional[str]:
    """Get the SHA of a file from GitHub if it exists.
    
    Args:
        file_path: Path to the file
        
    Returns:
        SHA string if file exists, None otherwise
    """
    response = requests.get(
        f"https://api.github.com/repos/{os.getenv('REPO_PATH')}/contents/{path_from_repo_root}",
        headers={
            "Authorization": f"BEARER {os.getenv('GITHUB_TOKEN')}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
    )
    if response.status_code == 200:
        return response.json().get("sha")
    return None


def encode_file_to_base64(file_path: str) -> str:
    """Encode a file's contents to base64.
    
    Args:
        file_path: Path to the file to encode
        
    Returns:
        Base64 encoded string
    """
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def upload_file_to_github(file_path: str, commit_message: str, upload_location:str = "") -> None:
    """Upload a file to a GitHub repository using the GitHub API.
    If a file with the same name exists, it will be overwritten.
    
    Args:
        file_path: The path to the file to upload
        commit_message: The commit message for the upload
        upload_location: The path in the repository where the file will be uploaded (to the root if empty)
        
    Raises:
        Exception: If upload fails
    """
    path_from_repo_root = ""
    if upload_location:
        path_from_repo_root += upload_location.rstrip("/") + "/"
    path_from_repo_root += os.path.basename(file_path)

    # Check if file exists and get its SHA
    previous_sha = get_file_sha_from_github(path_from_repo_root)

    # Encode file content
    content_b64 = encode_file_to_base64(file_path)

    request_body = {
        "message": commit_message,
        "content": content_b64,
    }
    if previous_sha:
        request_body["sha"] = previous_sha

    response = requests.put(
        f"https://api.github.com/repos/{os.getenv('REPO_PATH')}/contents/{path_from_repo_root}",
        headers={
            "Authorization": f"BEARER {os.getenv('GITHUB_TOKEN')}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        },
        json=request_body
    )

    if response.status_code not in [200, 201]:
        raise Exception(f"Failed to upload file to GitHub: {response.status_code} - {response.text}")

def _create_repo_url_with_token(repo_path: str) -> str:
    """Create a GitHub repository URL from the REPO_PATH environment variable.
    
    Args:
        repo_path: The REPO_PATH environment variable value
    Returns:
        The formatted repository URL with token
    """
    token = os.getenv("GITHUB_TOKEN")
    username = os.getenv("GITHUB_USERNAME")
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable is not set.")
    return f"https://{username}:{token}@github.com/{repo_path}.git"

def pull_files_from_github_to_quantrocket(
    repo: str,
    branch: Optional[str] = None,
    replace: Optional[bool] = None,
    skip_existing: Optional[bool] = None
) -> None:
    """Clone files from a Git repository by calling QuantRocket's /codeload/repo endpoint.
    
    Args:
        repo: The repository name or URL
        branch: Optional branch to clone
        replace: Whether to replace existing files (mutually exclusive with skip_existing)
        skip_existing: Whether to skip existing files (mutually exclusive with replace)
        
    Raises:
        ValueError: If HOUSTON_URL is not set
        requests.HTTPError: If the request fails
    """
    houston_url = os.getenv("HOUSTON_URL")
    username = os.getenv("HOUSTON_USERNAME")
    password = os.getenv("HOUSTON_PASSWORD")

    if not houston_url:
        raise ValueError("HOUSTON_URL environment variable is not set.")

    url = houston_url.rstrip('/') + '/codeload/repo'

    params = {"repo": _create_repo_url_with_token(repo)}
    if branch is not None:
        params["branch"] = branch
    if replace is not None:
        params["replace"] = str(replace)
    if skip_existing is not None:
        params["skip_existing"] = str(skip_existing)

    headers = {
        "Content-Type": "application/json"
    }

    auth = (username, password) if username and password else None

    response = requests.post(url, params=params, headers=headers, auth=auth)

    try:
        response.raise_for_status()
    except requests.HTTPError:
        raise requests.HTTPError(
            f"{response.status_code} {response.reason}: {response.text[:2000]}"
        )


def wait_for_ingestion(
    check_status_func,
    bundle_code: str,
    poll_interval: int = 20,
    log_message: str = "Waiting for ingestion to complete..."
) -> None:
    """Wait for data bundle ingestion to complete.
    
    Args:
        check_status_func: Function to check ingestion status
        bundle_code: Code of the bundle being ingested
        poll_interval: Seconds between status checks
        log_message: Message to log while waiting
    """
    while not check_status_func(bundle_code):
        logging.info(log_message)
        time.sleep(poll_interval)


def generate_markdown_report(
    strategy_id: str,
    total_return: float,
    sharpe_ratio: float,
    max_drawdown: float,
    output_path: Optional[str] = None
) -> str:
    """Generate a markdown backtest report.
    
    Args:
        strategy_id: ID of the strategy
        total_return: Total return percentage
        sharpe_ratio: Sharpe ratio
        max_drawdown: Maximum drawdown percentage
        output_path: Optional path to save the report
        
    Returns:
        Report as a markdown string
    """
    report = f"# Backtest Report: {strategy_id}\n\n"
    report += f"Total Return: {total_return:.2%}\n"
    report += f"Sharpe Ratio: {sharpe_ratio:.2f}\n"
    report += f"Max Drawdown: {max_drawdown:.2%}\n"
    
    if output_path:
        with open(output_path, 'w') as f:
            f.write(report)
    
    return report