FROM quay.io/podman/stable:latest

RUN dnf clean all && \
    dnf update -y && \
    dnf install -y --nogpgcheck libsecret sudo && \
    dnf install -y tar zip openssl ca-certificates git curl free podman-docker openssh-clients node shadow-utils fuse3 fuse-overlayfs && \
    rm -rf /var/cache/dnf/* && dnf clean all && \
    npm install -g @devcontainers/cli

# Mount CA secret conditionally: If the secret exists and is non-empty, copy and update trust
RUN --mount=type=secret,id=MY_CA,dst=/tmp/myCA.pem \
    if [ -s /tmp/myCA.pem ]; then \
        echo "Custom CA detected. Installing into system trust store..."; \
        cp /tmp/myCA.pem /etc/pki/ca-trust/source/anchors/myCA.pem && \
        update-ca-trust; \
    else \
        echo "No additional CA certificates provided, set it with CUSTOM_CA_PEM inside Github Secrets."; \
    fi    

ARG USERNAME=coder
ARG USER_UID=1001
ARG USER_GID=1001

RUN groupadd --gid ${USER_GID} ${USERNAME} && \
    useradd  --uid ${USER_UID} --gid ${USER_GID} \
             --shell /bin/bash --create-home ${USERNAME} && \
    echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" \
         > /etc/sudoers.d/${USERNAME} && \
    chmod 0440 /etc/sudoers.d/${USERNAME}

# ── Rootless podman: subuid / subgid ──────────────────────────────────────────
# 65536 sub-UIDs starting at 100000
RUN echo "${USERNAME}:100000:65536" >> /etc/subuid && \
    echo "${USERNAME}:100000:65536" >> /etc/subgid

# ── Pre-bake storage config (overlay via fuse-overlayfs) ─────────────────────
# fuse-overlayfs gives copy-on-write overlay semantics without the kernel
# overlay module. Requires /dev/fuse to be exposed in the pod (see Coder
# template snippet). mount_program points at the fuse-overlayfs binary.
RUN mkdir -p /home/${USERNAME}/.config/containers
COPY --chown=${USERNAME}:${USERNAME} extras/.config /home/${USERNAME}/containers/storage.conf
RUN chown -R ${USERNAME}:${USERNAME} /home/${USERNAME}/.config

RUN mkdir -p /tmp/podman && chown ${USERNAME}:${USERNAME} /tmp/podman
COPY extras/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER ${USERNAME}
WORKDIR /home/${USERNAME}

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]



