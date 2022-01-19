# iblrig

iblrig is using gitflow and semantic versioning conventions. Click on the following links for more information on [gitflow](https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow) or [semantic versioning](https://semver.org/).

### Gitflow divergence:
`rc` branch is a "pre-release" branch for beta testers on production rigs

---
### New features:
- `new_feature` branches are forked from the current `develop` branch
- the `new_feature` branches are then merged back into the `develop` branch
- a release candidate `rc` branch is forked from the `develop` branch
- once the `rc` has been thoroughly tested, it will get merged into `master` and `develop`
- the `rc` branch will be deleted

---
### Hotfixes:
- `hotfix` or `maintenance` branches are forked from `master`
- once the fix has been thoroughly tested, it will get merged back into `master`, `develop`, `rc`