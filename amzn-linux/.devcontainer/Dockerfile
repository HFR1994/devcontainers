# Amazon Linux 2023 devcontainer
ARG VARIANT=2023
FROM public.ecr.aws/amazonlinux/amazonlinux:${VARIANT}

ARG TYPST=0.14.2
ENV TYPST_VERSION=${TYPST}

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# Create the user
RUN dnf clean all && \
    dnf upgrade -y --refresh --releasever=latest && \
    dnf install -y --nogpgcheck libsecret sudo && \
    dnf groupinstall -y "Development Tools" && \
    dnf install -y tar zip openssl ca-certificates yum-utils shadow-utils openssh-clients git wget util-linux-user unzip openssl-devel cabextract xorg-x11-font-utils fontconfig && \
    dnf config-manager --add-repo https://rpm.releases.hashicorp.com/AmazonLinux/hashicorp.repo && \
    dnf install -y terraform  && \
    groupadd --gid $USER_GID $USERNAME && \
    useradd --uid $USER_UID --gid $USER_GID -m $USERNAME && \
    echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME && \
    chmod 0440 /etc/sudoers.d/$USERNAME && \
    rm -rf /var/cache/dnf/* && dnf clean all;

# Mount CA secret conditionally: If the secret exists and is non-empty, copy and update trust
RUN --mount=type=secret,id=MY_CA,dst=/tmp/myCA.pem \
    if [ -s /tmp/myCA.pem ]; then \
        echo "Custom CA detected. Installing into system trust store..."; \
        cp /tmp/myCA.pem /etc/pki/ca-trust/source/anchors/myCA.pem && \
        update-ca-trust; \
    else \
        echo "No additional CA certificates provided, set it with CUSTOM_CA_PEM inside Github Secrets."; \
    fi    

RUN curl -fsSL \
        https://github.com/typst/typst/releases/download/v${TYPST_VERSION}/typst-x86_64-unknown-linux-musl.tar.xz \
    | tar -xJ \
    && mv typst-x86_64-unknown-linux-musl/typst /usr/local/bin/typst \
    && rm -rf typst-x86_64-unknown-linux-musl

# Powerline fonts
RUN git clone https://github.com/powerline/fonts.git /tmp/fonts && \
    /tmp/fonts/install.sh && \
    rm -rf /tmp/fonts
 
# Powerlevel10k theme
RUN P10K_DIR="/home/${USERNAME}/.oh-my-zsh/custom/themes/powerlevel10k" && \
    mkdir -p "$P10K_DIR" && \ 
    git clone --depth=1 https://github.com/romkatv/powerlevel10k.git "$P10K_DIR" && \
    chown -R ${USERNAME}:${USERNAME} "$P10K_DIR"
 
# Copy custom Zsh configurations
COPY extras/.zshrc /etc/skel/.zshrc
COPY extras/.p10k.zsh /home/${USERNAME}/.p10k.zsh
RUN chown ${USERNAME}:${USERNAME} /home/${USERNAME}/.zshrc /home/${USERNAME}/.p10k.zsh