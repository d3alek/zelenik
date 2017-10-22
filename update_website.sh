#!/bin/bash

# https://git-scm.com/book/en/v1/Git-Tools-Subtree-Merging

git checkout blog &&\
git pull &&\
git checkout master &&\
git merge --squash -s subtree --no-commit --allow-unrelated-histories blog

git checkout landing &&\
git pull &&\
git checkout master &&\
git merge --squash -s subtree --no-commit  --allow-unrelated-histories landing

