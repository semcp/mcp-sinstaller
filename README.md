# MCP Secure Installer (`mcp-sinstaller`)

This project provides an **MCP server installer** that can automatically install, and containerize other MCP servers from GitHub repositories. It uses the Model Context Protocol (MCP) sampling feature to analyze repositories and create appropriate docker images.

## Requirements

- Docker
- MCP Client with Sampling enabled

### Enable Sampling in VS Code Insiders (Recommended)

Add the following to your VS code settings:

```json
"chat.mcp.serverSampling": {
    "Global in Code - Insiders: sampling": {
        "allowedDuringChat": true
    }
}
```

## Usage

### Running the Server in VS Code (Recommended)

1. **uvx**

```json
"mcp-sinstaller": {
    "type": "stdio",
    "command": "uvx",
    "args": [
            "--from",
            "/path/to/mcp-sinstaller",
            "python",
            "/path/to/mcp-sinstaller/mcp_installer.py",
    ]
},
```

## Server Naming & Multiple Servers

The installer uses a structured naming scheme: `owner-repo-servername` to avoid conflicts when installing multiple servers from the same repository.

**Examples:**
- `https://github.com/modelcontextprotocol/servers/tree/main/src/fetch` → `modelcontextprotocol-servers-fetch`
- `https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem` → `modelcontextprotocol-servers-filesystem`
- `https://github.com/github/github-mcp-server` → `github-github-mcp-server`

This allows you to install multiple MCP servers from repositories like `modelcontextprotocol/servers` without naming conflicts.

## Example (GitHub MCP Server)

Prompt: "install https://github.com/github/github-mcp-server"

```console
GitHub Copilot:
I'll install the GitHub MCP server from the repository you specified.

sampling (MCP Server):

Input:

{
  "url": "https://github.com/github/github-mcp-server"
}

Output:

Successfully built Docker image for MCP server 'github-mcp-server'!

Repository: https://github.com/github/github-mcp-server
Location: /Users/mossaka/.mcp-installer/servers/github-mcp-server

DOCKER IMAGE:
- Using existing Dockerfile
- Image: mcp-installer-github-mcp-server
- Size & Created: REPOSITORY:TAG                           SIZE      CREATED AT
mcp-installer-github-mcp-server:latest   59.5MB    2025-06-09 14:52:46 -0700 PDT
- Ports: {}
- Environment Variables: ['GITHUB_PERSONAL_ACCESS_TOKEN', 'GITHUB_TOOLSETS', 'GITHUB_DYNAMIC_TOOLSETS', 'GITHUB_READ_ONLY', 'GITHUB_HOST']
- Required Secrets: ['GITHUB_PERSONAL_ACCESS_TOKEN']
- Metadata: /Users/mossaka/.mcp-installer/servers/github-mcp-server/metadata.json


TO RUN THE CONTAINER (STDIO Transport):

1. Set required environment variables (if any):
export GITHUB_PERSONAL_ACCESS_TOKEN=your_actual_github_personal_access_token_here

2. Run the container interactively:
   docker run -i --rm --name mcp-github-mcp-server-container -e GITHUB_PERSONAL_ACCESS_TOKEN=GitHub personal access token (required) -e GITHUB_TOOLSETS=Comma-separated list of toolsets to enable (optional) -e GITHUB_DYNAMIC_TOOLSETS=Set to 1 to enable dynamic tool discovery (optional) -e GITHUB_READ_ONLY=Set to 1 to enable read-only mode (optional) -e GITHUB_HOST=Custom GitHub API endpoint for GitHub Enterprise (optional) -e GITHUB_PERSONAL_ACCESS_TOKEN=${GITHUB_PERSONAL_ACCESS_TOKEN} mcp-installer-github-mcp-server
   
   Note: This server uses STDIO transport (stdin/stdout communication).
   - The container runs interactively (-i flag)
   - It will be automatically removed when it exits (--rm flag)
   - No port mapping needed as it uses standard input/output

3. To stop the container:
   Ctrl+C in the terminal where it's running

4. For background operation with MCP client:
   Use your MCP client to connect via subprocess/stdio


Great! The GitHub MCP server has been successfully installed. The installation completed successfully and built a Docker image.

Here's what was installed:

Server Name: github-mcp-server
Repository: https://github.com/github/github-mcp-server
Docker Image: mcp-installer-github-mcp-server:latest (59.5MB)
Transport Type: STDIO (communicates via standard input/output)
Required Configuration: The server requires a GITHUB_PERSONAL_ACCESS_TOKEN environment variable to authenticate with GitHub's API.

Optional Environment Variables:

GITHUB_TOOLSETS: Comma-separated list of toolsets to enable
GITHUB_DYNAMIC_TOOLSETS: Set to 1 to enable dynamic tool discovery
GITHUB_READ_ONLY: Set to 1 to enable read-only mode
GITHUB_HOST: Custom GitHub API endpoint for GitHub Enterprise
The server is now ready to use. To run it, you'll need to set your GitHub personal access token and then run the Docker container with the STDIO transport for communication with MCP clients.
```

After that, you can run `docker` to run the container in your agent's MCP settings.

### VS Code

```json
"github": {
    "type": "stdio",
    "command": "docker",
    "args": [
        "run",
        "-i",
        "--rm",
        "-e",
        "GITHUB_PERSONAL_ACCESS_TOKEN=<PAT>",
        "mcp-installer-github-mcp-server",
    ]
}
```
