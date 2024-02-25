from fastapi.responses import HTMLResponse
from fastapi import Request, Form
from fastapi.templating import Jinja2Templates
from collections import defaultdict

import os
import itertools
import fastapi
import aiohttp
import asyncio


router = fastapi.APIRouter()
templates = Jinja2Templates(directory='app/templates')
G_TOKEN = os.getenv("GITHUB_TOKEN")

async def fetch_contributors(session, repo_url):
    contributors_url = f"{repo_url}/contributors"
    async with session.get(contributors_url) as response:
        return await response.json()


async def fetch_repos_for_contributor(session, contributor):
    repos_url = contributor['repos_url']
    async with session.get(repos_url) as response:
        return await response.json()

async def get_repo_url(name, session):
    url = f"https://api.github.com/search/repositories?q={name}"
    async with session.get(url) as response:
        resp = await response.json()
        # print('resp1:', resp)
        return resp.get('items', {})[0]

async def count_contributor_joins(repos_list, contributors_names, session, ignore):
    tasks = [check_repo_contributors(session, repo, contributors_names) for repo in repos_list if repo['full_name'].split('/')[1] != ignore]
    return await asyncio.gather(*tasks)

async def check_repo_contributors(session, repo, contributors_names):
    repo_name = repo['full_name']
    count_joint_contribs = {repo_name: 0}
    try:
        user_project_contributors = await fetch_contributors(session, f"https://api.github.com/repos/{repo_name}")
        for contrib in user_project_contributors:
            if contrib.get('login') in contributors_names and contrib.get('login') != repo.get('owner', {}).get('login'):
                count_joint_contribs[repo_name] += 1
    except Exception as e:
        print(f"Error at {repo_name}: {e}")
    return count_joint_contribs

async def start(repo_url: str):

    auth = aiohttp.BasicAuth('your_github_username', G_TOKEN)
    ignore_repo = repo_url.split('/')[-1]

    async with aiohttp.ClientSession(auth=auth) as session:
        contributors = await fetch_contributors(session, repo_url)
        tasks = [fetch_repos_for_contributor(session, c) for c in contributors]
        contributors_repos = await asyncio.gather(*tasks)

        contributors_names = [x.get('login') for x in contributors]

        tasks = [count_contributor_joins(repos_list, contributors_names, session, ignore_repo) for repos_list in contributors_repos]

        repo_contributors_count = await asyncio.gather(*tasks)
        repo_contributors_count = list(itertools.chain(*repo_contributors_count))

        project_contributors = defaultdict(int)
        for project in repo_contributors_count:
            for name, contribs in project.items():
                name = name.split('/')[1]
                project_contributors[name] += contribs

        sorted_projects = sorted(project_contributors.items(), key=lambda x: x[1], reverse=True)

        response = []
        for project in sorted_projects[:5]:
            project_tag = project[0]
            github_url = await get_repo_url(project_tag, session)
            response.append([github_url.get("html_url"), project_tag, project[1]])

        return response



@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "data": []})


@router.post('/git', response_class=HTMLResponse)
async def git(request: Request, url = Form()):
    resp = await start(repo_url=url)

    return templates.TemplateResponse("index.html", {"request": request, "data": resp, "input": url})
