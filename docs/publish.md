# Publish the dashboard

<p class="lede">The dashboard is published to GitHub Pages from the same
repository, on every push to main. One setting to change, once.</p>

## One-time setup

In the repository on GitHub: **Settings**, then **Pages**, then under **Build
and deployment** set the source to **GitHub Actions**. Nothing else.

The workflow `hunter init` writes already carries the publish job. On the next
push to main the site appears at:

```
https://<organisation>.github.io/<repository>/
```

The dashboard is the front page. The detail pages sit behind it.

## What the workflow does

```yaml
  hunter:
    steps:
      - uses: sav-sus/Hunter@v0.1.0
        with:
          publish: ${{ github.event_name != 'pull_request' }}
      - uses: actions/upload-pages-artifact@v3
        if: github.event_name != 'pull_request'
        with:
          path: out/site/_built

  publish:
    if: github.event_name != 'pull_request'
    needs: hunter
    permissions:
      pages: write
      id-token: write
    environment:
      name: github-pages
    steps:
      - uses: actions/deploy-pages@v4
```

The score job builds the site and hands it to Pages. The publish job deploys
it. Pull requests never publish: the dashboard shows what is on main, not what
is proposed.

## Who can see it

<div class="key" markdown>
**On GitHub Enterprise Cloud, Pages can be restricted to people with read
access to the repository.** Anywhere else, a Pages site is public even when the
repository is private, and every HTML and JSON file on it can be downloaded by
anyone with the link.
</div>

The dashboard carries table names, column names, owners and findings. It carries
no row-level data. Decide whether that is acceptable for a public link before
switching Pages on. If it is not, the alternative is Cloud Run behind
Identity-Aware Proxy, which the site's static files suit without change.

A browser-side password check is not access control.

## If the site does not appear

| Symptom | Cause |
|---|---|
| The publish job is skipped | The run was for a pull request. Only pushes to main publish |
| The publish job fails with a permissions error | The Pages source is still set to a branch. Set it to GitHub Actions |
| The page is there but out of date | Look at the Actions tab. A failed score job means nothing was handed to Pages |
| The diagrams show as text | Scripting is switched off in the browser. Everything else on the page is unaffected |

## Without GitHub Pages

```bash
hunter docs build . --out out/site
```

`out/site/_built/` is a static site. Copy it anywhere that serves files. The
dashboard alone is one file, `out/site/_built/dashboard.html`, and can be sent
as an attachment.
