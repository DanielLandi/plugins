# Security

Report a problem privately through a GitHub security advisory on
[DanielLandi/plugins](https://github.com/DanielLandi/plugins/security/advisories/new), not in a public issue.

The plugin stores no credentials and calls no Suno API: Suno is used only through your own signed-in Chrome, via
the Claude in Chrome extension, and Claude never types your password. It downloads only what `doctor` installs
(npm packages from the npm registry, Remotion's headless browser, the alignment models from PyPI and their model
hubs) into your cache folder.
