FROM quay.io/podman/stable:latest

RUN dnf clean all && \
    dnf update -y && \
    dnf install -y --nogpgcheck libsecret sudo && \
    dnf install -y tar zip openssl ca-certificates git curl free podman-docker openssh-clients node shadow-utils fuse3 fuse-overlayfs && \
    rm -rf /var/cache/dnf/* && dnf clean all && \
    npm install -g @devcontainers/cli

RUN --mount=type=secret,id=MY_CA,dst=/tmp/myCA.pem \
    if [ -s /tmp/myCA.pem ]; then \
        echo "Custom CA detected. Installing into system trust store..."; \
        cp /tmp/myCA.pem /etc/pki/ca-trust/source/anchors/myCA.pem && \
        update-ca-trust; \
    else \
        echo "No additional CA certificates provided, set it with CUSTOM_CA_PEM inside Github Secrets."; \
    fi

# Must match security_context.run_as_user in the Coder template
ARG USERNAME=coder
ARG USER_UID=1000
ARG USER_GID=1000

# ── Replace the base image's "podman" user (uid 1000) with ours ──────────────
RUN userdel -r podman 2>/dev/null || true; \
    groupdel podman 2>/dev/null || true; \
    sed -i '/^podman:/d' /etc/subuid /etc/subgid && \
    groupadd --gid ${USER_GID} ${USERNAME} && \
    useradd  --uid ${USER_UID} --gid ${USER_GID} \
             --shell /bin/bash --create-home ${USERNAME} && \
    echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME} && \
    chmod 0440 /etc/sudoers.d/${USERNAME}

# ── Rootless podman: subuid / subgid ──────────────────────────────────────────
RUN echo "${USERNAME}:100000:65536" >> /etc/subuid && \
    echo "${USERNAME}:100000:65536" >> /etc/subgid

# ── Storage config (overlay via fuse-overlayfs) ──────────────────────────────
# Requires /dev/fuse in the pod. Path fixed: was missing ".config/".
COPY --chown=${USERNAME}:${USERNAME} extras/.config /home/${USERNAME}/.config/containers/storage.conf

RUN mkdir -p /tmp/podman && chown ${USERNAME}:${USERNAME} /tmp/podman
COPY extras/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER ${USERNAME}
WORKDIR /home/${USERNAME}

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]