ARG VARIANT=3.12-trixie
FROM mcr.microsoft.com/devcontainers/python:${VARIANT}

RUN ln -sf /usr/local/bin/python /usr/bin/python

ARG TYPST=0.15.1
ENV TYPST_VERSION=${TYPST}

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# Create the user
RUN apt-get update && \
    apt-get upgrade -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        sudo \
        libsecret-1-0 \
        build-essential \
        tar \
        zip \
        openssl \
        ca-certificates \
        openssh-client \
        git \
        wget \
        curl \
        unzip \
        libssl-dev \
        cabextract \
        xfonts-utils \
        fontconfig \
        gnupg \
        lsb-release && \ 
    # Setup User
    groupadd --gid $USER_GID $USERNAME && \
    useradd --uid $USER_UID --gid $USER_GID -m -s /bin/bash $USERNAME && \
    echo "$USERNAME ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/$USERNAME && \
    chmod 0440 /etc/sudoers.d/$USERNAME && \
    # Clean up
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Enable contrib repo (for fonts only - shows at duplicated)
RUN echo "deb http://deb.debian.org/debian trixie main contrib" > /etc/apt/sources.list.d/contrib.list \
    && apt-get update \
    && apt-get install --no-install-recommends -y fonts-ibm-plex \
    && rm /etc/apt/sources.list.d/contrib.list \
    && apt-get update

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

RUN curl -L https://coder.com/install.sh | sh