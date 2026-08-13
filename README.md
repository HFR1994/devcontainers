# devcontainers

Prebuilt, published devcontainer / workspace images — built so you don't have to wait on `dnf install` and
`git clone` every time a container starts.

Every push to `main` builds whatever image directories changed and publishes them to GHCR under
[ghcr.io/hfr1994](https://github.com/HFR1994?tab=packages), tagged `latest`, an auto-incremented SemVer
(`<folder>-x.y.z`), and the commit SHA.

## Images in this repo

| Folder | What it is | Published as |
| --- | --- | --- |
| [amzn-linux](amzn-linux) | Amazon Linux 2023 devcontainer aimed to provision AWS Infrastructure with Terraform | `ghcr.io/hfr1994/amzn-linux` |
| [podman_devcontainer](podman_devcontainer) | Rootless Podman-in-Podman image (DinD) to build/run devcontainers | `ghcr.io/hfr1994/podman_devcontainer` |

## Using an image

### amzn-linux, in VS Code / any devcontainer-CLI tool

Point your project's `.devcontainer/devcontainer.json` at the published image instead of building locally:

```json
{
  "image": "ghcr.io/hfr1994/amzn-linux:latest"
}
```

Or pull/run it directly:

```bash
docker run -it --rm ghcr.io/hfr1994/amzn-linux:latest
```

### podman_devcontainer, as a Coder/Kubernetes workspace image

This image expects to run as its own container/pod with `/dev/fuse` available (needed by fuse-overlayfs) and is
meant to be used as the workspace image in a Coder template, not opened directly by VS Code. Its entrypoint
starts a rootless Podman API socket, waits for it to come up, exports `DOCKER_HOST` to point at it, and then
hands off to whatever `CMD`/agent bootstrap the template supplies.

```bash
docker run -it --rm --device /dev/fuse ghcr.io/hfr1994/podman_devcontainer:latest
```

## How the build works

[.github/workflows/build-and-publish.yml](.github/workflows/build-and-publish.yml) does the work:

1. **Discover** — Works only with modified files. Clasifies is as followed:
   - **Devcontainer**: has `.devcontainer/devcontainer.json` → built with `devcontainers/ci`
   - **Container**: has a root-level `Dockerfile` (no devcontainer.json) → built with plain `docker build`/`push`

2. **Build & tag** — each changed folder gets its own auto-incrementing SemVer tag (prefixed with the folder
   name so parallel builds never collide), then is built and pushed to GHCR as `latest`, the new SemVer, and
   (for plain images) the commit SHA.


## Adding a new image

Add a new top-level directory shaped like one of the two kinds above:

```
my-new-image/
  Dockerfile                       # plain image
```

or

```
my-new-image/
  .devcontainer/
    devcontainer.json              # devcontainer image
    Dockerfile
```

No workflow changes are needed — pushing to `main` with files under that folder is enough for CI to pick it up,
tag it, build it, and publish it.

### Testing locally before pushing

```bash
# plain image
docker build -t test-image ./podman_devcontainer

# devcontainer image (mirrors what devcontainers/ci does)
npx @devcontainers/cli build --workspace-folder ./amzn-linux
```

## License

[Apache 2.0](LICENSE)
