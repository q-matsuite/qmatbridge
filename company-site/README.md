# q-matsuite company page

Source for `https://q-matsuite.com/`. This folder is staged inside the QMatBridge
repo for review; it is meant to live in its own repository named
**`q-matsuite.github.io`** under the `q-matsuite` GitHub org, which is what makes
GitHub Pages serve `qmatbridge` at `q-matsuite.com/qmatbridge/`.

## Set-up (one time)

1. Rename the GitHub org `QMatBridge` to `q-matsuite` (Settings → Organization → Rename).
2. Create the repo `q-matsuite/q-matsuite.github.io` and copy `index.html`,
   `favicon.svg` and `CNAME` to its root (add a `.nojekyll` file). Push to `main`.
3. In that repo: Settings → Pages → Source: *Deploy from a branch*, `main` / root;
   Custom domain: `q-matsuite.com`; tick *Enforce HTTPS* once the certificate is issued.
4. DNS at your registrar:
   - four `A` records for `@` → `185.199.108.153`, `185.199.109.153`,
     `185.199.110.153`, `185.199.111.153`
   - `CNAME` for `www` → `q-matsuite.github.io`
   (Check GitHub's current Pages IPs in their docs before adding them.)
5. In `q-matsuite/qmatbridge`: Settings → Pages → Source: *GitHub Actions*. It then
   appears at `q-matsuite.com/qmatbridge/` automatically; its own `CNAME` is not needed.
