# Devcontainer/Tools Ready Images

Prebuilt, published devcontainer / workspace images — built so you don't have to wait for long built times, or contenerize ready to go environments.

Every push to `main` builds whatever image directories changed and publishes them to GHCR under
[ghcr.io/hfr1994](https://github.com/HFR1994?tab=packages), tagged `latest`, an auto-incremented SemVer
(`<folder>-x.y.z`), and the commit SHA.

## Images in this repo

| Folder | What it is | Published as |
| --- | --- | --- |
| [amzn-linux](amzn-linux) | Amazon Linux 2023 devcontainer aimed to provision AWS Infrastructure with Terraform | `ghcr.io/hfr1994/amzn-linux` |
| [podman_devcontainer](podman_devcontainer) | Rootless Podman-in-Podman image (DinD) to build/run devcontainers | `ghcr.io/hfr1994/podman_devcontainer` |
| [chrome-mcp-server](podman_devcontainer) | Build based on Chrome Dev Tools MCP, just a container way of exposing the tool | `ghcr.io/hfr1994/chrome-mcp-server` |

## Using an image

All images are build using Github Actions. This images are meant to be used on local secure environments so you can add your own CA Certs shipped into the images (optional).

For that set the following actions:

- Go to your GitHub repository -> Settings -> Secrets and variables -> Actions.

- Click New repository secret.

- Set Name to CUSTOM_CA_PEM.

- Set Value to the entire raw content of your PEM file (including -----BEGIN CERTIFICATE----- and -----END CERTIFICATE-----).

### Devcontainers

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

### Containers

Just do a normal docker run:

#### Podman_devcontainer uses fuse

```bash
docker run -it --rm --device /dev/fuse ghcr.io/hfr1994/podman_devcontainer:latest
```

#### Chrome Dev Tool needs extra priviledges

```bash
docker run -i --rm --init --cap-add=SYS_ADMIN chrome-devtools-mcp
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
