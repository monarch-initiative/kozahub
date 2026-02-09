#!/usr/bin/env python3
"""
Fetch dashboard data for KozaHub ingests.

Queries GitHub API to discover all repos with 'kozahub-ingest' topic
in monarch-initiative org, then fetches release and workflow data.
"""
import base64
import json
import os
import re
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from github import Github, Auth
from github.Repository import Repository
from github.GithubException import GithubException
from packaging import version as pkg_version

# Configuration
ORG_NAME = "monarch-initiative"
TOPIC = "kozahub-ingest"
TEMPLATE_REPO = "monarch-initiative/koza-ingest-template"
STALENESS_THRESHOLD_DAYS = 45
OUTPUT_FILE = Path(__file__).parent.parent / "data" / "dashboard-data.json"


def calculate_status(
    release_date: Optional[datetime],
    workflow_conclusion: Optional[str]
) -> str:
    """
    Calculate health status based on design spec:
    - Green (healthy): workflow success AND release <45 days
    - Yellow (stale): workflow success BUT release >45 days
    - Red (failed): workflow failed (or missing)
    """
    if workflow_conclusion != "success":
        return "failed"
    
    if not release_date:
        return "failed"  # No release is considered failed
    
    days_old = (datetime.now(timezone.utc) - release_date).days
    
    if days_old <= STALENESS_THRESHOLD_DAYS:
        return "healthy"
    else:
        return "stale"


def discover_ingests(github: Github) -> list[Repository]:
    """
    Query GitHub API to find all repos with kozahub-ingest topic.
    
    API: GET /search/repositories?q=org:monarch-initiative+topic:kozahub-ingest
    """
    query = f"org:{ORG_NAME} topic:{TOPIC}"
    try:
        repos = github.search_repositories(query=query)
        return list(repos)
    except GithubException as e:
        print(f"Error searching repositories: {e}")
        return []


def fetch_latest_release(repo: Repository) -> Optional[dict]:
    """
    Fetch latest release for a repository.
    
    Returns None if no releases exist.
    """
    try:
        release = repo.get_latest_release()
        return {
            "tag": release.tag_name,
            "date": release.published_at.isoformat(),
            "url": release.html_url
        }
    except GithubException:
        # No releases found
        return None


def fetch_latest_workflow_run(repo: Repository) -> Optional[dict]:
    """
    Fetch latest workflow run (typically 'release.yaml').
    
    Strategy: Get all workflows, find 'release' workflow, get latest run.
    Falls back to most recent run from any workflow if 'release' not found.
    """
    try:
        workflows = repo.get_workflows()
        release_workflow = None
        
        # Try to find release workflow
        for workflow in workflows:
            if 'release' in workflow.name.lower():
                release_workflow = workflow
                break
        
        # If release workflow found, get its latest run
        if release_workflow:
            runs = release_workflow.get_runs()
            if runs.totalCount > 0:
                latest = runs[0]
                return {
                    "status": latest.status,
                    "conclusion": latest.conclusion,
                    "date": latest.created_at.isoformat(),
                    "url": latest.html_url
                }
        
        # Fallback: get most recent workflow run from any workflow
        runs = repo.get_workflow_runs()
        if runs.totalCount > 0:
            latest = runs[0]
            return {
                "status": latest.status,
                "conclusion": latest.conclusion,
                "date": latest.created_at.isoformat(),
                "url": latest.html_url
            }
        
        return None
    except GithubException as e:
        print(f"Error fetching workflows for {repo.name}: {e}")
        return None


def fetch_koza_version(repo: Repository) -> Optional[str]:
    """
    Detect Koza version from repo's pyproject.toml.

    Returns "2" if Koza >= 2.0.0, None otherwise.
    """
    try:
        # Fetch pyproject.toml from repo
        content = repo.get_contents("pyproject.toml")

        # Decode base64 content
        toml_content = base64.b64decode(content.content).decode('utf-8')

        # Parse TOML
        data = tomllib.loads(toml_content)

        # Get dependencies from [project] section
        dependencies = data.get('project', {}).get('dependencies', [])

        # Find koza dependency
        koza_dep = None
        for dep in dependencies:
            if isinstance(dep, str) and dep.strip().startswith('koza'):
                koza_dep = dep
                break

        if not koza_dep:
            return None

        # Extract version using regex
        # Matches: koza>=2.0.0, koza==2.1.0, koza~=2.0, etc.
        match = re.search(r'koza\s*([><=!~]+)\s*([0-9.]+)', koza_dep)
        if not match:
            return None

        operator, version_str = match.groups()

        # Parse version
        try:
            dep_version = pkg_version.parse(version_str)
            koza_v2 = pkg_version.parse("2.0.0")

            # Check if version constraint allows >= 2.0.0
            # For simplicity: if the specified version is >= 2.0.0, consider it Koza 2
            if dep_version >= koza_v2:
                return "2"
            else:
                return None
        except Exception as e:
            print(f"  Warning: Could not parse version '{version_str}' for {repo.name}: {e}")
            return None

    except GithubException as e:
        if e.status == 404:
            # File not found
            return None
        print(f"  Warning: Error fetching pyproject.toml for {repo.name}: {e}")
        return None
    except Exception as e:
        print(f"  Warning: Error parsing Koza version for {repo.name}: {e}")
        return None


def fetch_template_commits(github: Github) -> list[str]:
    """
    Fetch the commit history of the copier template repo.

    Returns a list of commit SHAs ordered newest-first.
    """
    try:
        repo = github.get_repo(TEMPLATE_REPO)
        commits = repo.get_commits()
        return [c.sha for c in commits]
    except GithubException as e:
        print(f"Error fetching template commits: {e}")
        return []


def fetch_copier_info(repo: Repository) -> Optional[dict]:
    """
    Fetch .copier-answers.yml from a repo to get template commit info.

    Returns dict with '_commit' and '_src_path', or None if not found.
    """
    try:
        content = repo.get_contents(".copier-answers.yml")
        yaml_content = base64.b64decode(content.content).decode('utf-8')
        answers = yaml.safe_load(yaml_content)
        commit = answers.get("_commit")
        src_path = answers.get("_src_path")
        if commit:
            return {"commit": commit, "src_path": src_path}
        return None
    except GithubException:
        return None
    except Exception as e:
        print(f"  Warning: Error parsing copier answers for {repo.name}: {e}")
        return None


def calculate_commits_behind(
    copier_commit: str,
    template_commits: list[str],
) -> Optional[int]:
    """
    Calculate how many commits behind an ingest is from the template HEAD.

    Matches the copier commit (which may be a short hash) against the
    full commit SHAs in the template history.
    """
    for i, sha in enumerate(template_commits):
        if sha.startswith(copier_commit):
            return i
    return None  # Commit not found in history


def fetch_ingest_data(repo: Repository, template_commits: list[str]) -> dict:
    """
    Fetch complete data for a single ingest repository.
    """
    print(f"Fetching data for {repo.name}...")

    release_data = fetch_latest_release(repo)
    workflow_data = fetch_latest_workflow_run(repo)
    koza_version = fetch_koza_version(repo)
    copier_info = fetch_copier_info(repo)

    # Parse release date for status calculation
    release_date = None
    if release_data:
        release_date = datetime.fromisoformat(release_data["date"].replace('Z', '+00:00'))

    # Get workflow conclusion
    workflow_conclusion = workflow_data.get("conclusion") if workflow_data else None

    # Calculate health status
    status = calculate_status(release_date, workflow_conclusion)

    # Calculate template status
    template_status = None
    if copier_info and template_commits:
        commits_behind = calculate_commits_behind(
            copier_info["commit"], template_commits
        )
        template_status = {
            "commit": copier_info["commit"],
            "commits_behind": commits_behind,
        }
        if commits_behind is not None:
            print(f"  Template: {commits_behind} commits behind")
        else:
            print(f"  Template: commit {copier_info['commit']} not found in history")

    return {
        "name": repo.name,
        "repo_url": repo.html_url,
        "status": status,
        "last_release": release_data,
        "last_workflow_run": workflow_data,
        "koza_version": koza_version,
        "template_status": template_status,
    }


def main():
    """
    Main entry point: discover ingests, fetch data, write JSON.
    """
    # Get GitHub token from environment (optional for higher rate limits)
    token = os.environ.get("GITHUB_TOKEN")
    
    if token:
        auth = Auth.Token(token)
        github = Github(auth=auth)
        print("Using GitHub token for authentication (5000 req/hr)")
    else:
        github = Github()  # Anonymous (60 requests/hour)
        print("No GITHUB_TOKEN found, using anonymous access (60 req/hr)")
    
    print(f"Searching for repos with topic '{TOPIC}' in org '{ORG_NAME}'...")
    repos = discover_ingests(github)
    print(f"Found {len(repos)} repositories")

    # Fetch template commit history
    print(f"\nFetching template commit history from {TEMPLATE_REPO}...")
    template_commits = fetch_template_commits(github)
    print(f"Found {len(template_commits)} template commits")

    # Fetch data for each ingest
    ingests_data = []
    for repo in repos:
        try:
            data = fetch_ingest_data(repo, template_commits)
            ingests_data.append(data)
        except Exception as e:
            print(f"Error processing {repo.name}: {e}")
            continue

    # Sort by name for consistent output
    ingests_data.sort(key=lambda x: x["name"])

    # Create output structure
    template_info = None
    if template_commits:
        template_repo = github.get_repo(TEMPLATE_REPO)
        template_info = {
            "repo_url": template_repo.html_url,
            "latest_commit": template_commits[0][:7],
            "total_commits": len(template_commits),
        }
    output = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "template": template_info,
        "ingests": ingests_data,
    }
    
    # Ensure output directory exists
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Write JSON
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\nDashboard data written to {OUTPUT_FILE}")
    print(f"Total ingests: {len(ingests_data)}")
    
    # Print summary
    healthy = sum(1 for i in ingests_data if i["status"] == "healthy")
    stale = sum(1 for i in ingests_data if i["status"] == "stale")
    failed = sum(1 for i in ingests_data if i["status"] == "failed")
    print(f"Status: {healthy} healthy, {stale} stale, {failed} failed")


if __name__ == "__main__":
    main()
