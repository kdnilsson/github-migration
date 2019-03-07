#!/usr/bin/env python3.7

import requests
import json
import os
import subprocess

# find repos to migrate
repo_to_migrate = 'monitor-release'

# BitBucket variables/parameters
b_uname = ''
b_passwd = ''
b_s = requests.Session()
b_s.auth = (b_uname, b_passwd)

# GitHub variables/parameters
g_base_url = 'https://api.github.com/'
organization = ''
teamid = ''
g_uname = ''
g_passwd = ''
g_s = requests.Session()
g_s.auth = (g_uname, g_passwd)

def repos_to_migrate(projectkey):
    # Create a list of dicts containing every repo for a given projectkey in
    # BitBucket
    #
    # Returns [{name: repo_name, href: repo_href}]
    #
    url = 'http://scm.dev.op5.com/rest/api/1.0/projects/%s/repos?limit=1000' % projectkey
    r = b_s.get(url)
    if r.status_code == 200:
        print('Retrived repos to migrate from BitBucket')
        data = r.json()
        data = data['values']
    else:
        print('Error: Could not retrive repos from Bitbucket')
        print('Response:', r.content)
        data = []

    repos = []
    for d in data:
        repo_name = d['name']
        project_name = d['project']['name']
        # We want to avoid repo names like monitor-monitor-iot
        if repo_name.split('-')[0] != project_name:
            repo_name = '%s-%s' % (project_name, repo_name)
        # We want to clone using ssh
        for c in d['links']['clone']:
            if c['name'] == 'ssh':
                repo_href = c['href']
        repos.append({'name': repo_name, 'href': repo_href})

    return repos

def create_github_repo(repo):
    url = g_base_url + "orgs/%s/repos" % organization
    data = {'name': repo,
            'private': 'true',
            'team_id': teamid
            }
    r = g_s.post(url, json.dumps(data))
    if r.status_code == 201:
        print('Created repo "%s"' % repo)
        response = r.json()
        return response['ssh_url']
    else:
        print('Error: Could not create repo "%s"' % repo)
        print('Response:', r.content, r.status_code)
        return ''

def add_webhook(repo):
    url = g_base_url + "repos/%s/%s/hooks" % (organization, repo)
    data = {'name': 'web',
            'events': ["push"],
            'config': {'url': 'http://bb-dev.dev.op5.com/change_hook/github',
                       'content_type': 'form'}
            }
    r = g_s.post(url, json.dumps(data))
    if r.status_code == 201:
        print('Created webhook in repo "%s"' % repo)
    else:
        print('Error: Could not create webhook in repo "%s"' % repo)
        print('Response:', r.content)

def execute_git_cmd(cmd, repo_dir):
    p = subprocess.Popen(cmd, shell=True, cwd=repo_dir, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)
    (output, error) = p.communicate()
    #print(output, error)
    p.wait()

    return p.returncode

def migrate_repo(repo, repo_ssh_url):
    print('Migrating repo "%s"' % repo)
    # Go into repo dir
    os.chdir(repo)
    # Where are we
    repo_dir = os.getcwd()
    # Checkout master, maint/7.4 and maint/7.5 branches
    for branch in ['maint/7.4','maint/7.5','master']:
        cmd = 'git checkout "%s"' % branch
        execute_git_cmd(cmd, repo_dir)

    # Change remote
    cmd = 'git remote set-url origin "%s"' % repo_ssh_url
    execute_git_cmd(cmd, repo_dir)

    # Push all local branches to new remote
    cmd = 'git push origin --all'
    execute_git_cmd(cmd, repo_dir)

    # Push all tags to new remote
    cmd = 'git push origin --tags'
    execute_git_cmd(cmd, repo_dir)

    # Go out of repo dir
    os.chdir('../')

def clone_repo(repo, href):
    print('Cloning repo "%s"' % repo)
    # Where are we
    repo_dir = os.getcwd()
    # Clone repo
    cmd = 'git clone "%s" "%s"' % (href, repo)
    execute_git_cmd(cmd, repo_dir)

#create_github_repo(repo_to_migrate)
#add_webhook(repo_to_migrate)
all_repos = repos_to_migrate('MONITOR')
repos = []
for repo in all_repos:
    if repo['name'] == 'monitor-release':
        repos.append({'name': repo['name'], 'href': repo['href']})
    if repo['name'] == 'monitor-nachos':
        repos.append({'name': repo['name'], 'href': repo['href']})

for repo in repos:
    print(repo)
    repo_name = repo['name']
    repo_ssh_url = repo['href']
    new_remote_ssh_url = create_github_repo(repo_name)
    clone_repo(repo_name, repo_ssh_url)
    migrate_repo(repo_name, new_remote_ssh_url)
    add_webhook(repo_name)

# List repos to migrate and rename repos /monitor/nachos to monitor-nachos etc.
# create repo
# add webhook
# populate repo (master and maint branches and tags)
    # Checkout branches to be migrated, master and maint
    # Change remote to github
    # Push branches and tags to new remote
# add branch protection
