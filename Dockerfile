# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install uv
RUN pip install uv

# Copy the requirements file into the container
# We'll create pyproject.toml (which uv uses) first, then copy it.
# For now, this assumes pyproject.toml will list dependencies.
COPY pyproject.toml pyproject.toml

# Install project dependencies using uv
# This command assumes dependencies are listed in pyproject.toml under [project.dependencies]
# and optional dependencies for 'dev' are under [project.optional-dependencies.dev]
# If a requirements.txt is preferred, this step would change.
RUN uv pip install --no-cache --system -r pyproject.toml

# Copy the rest of the application code into the container
COPY . .

# Make port 8000 available to the world outside this container (for the MCP server)
EXPOSE 8000

# Define environment variable
ENV MODULE_NAME="src.mcp_server.main"
ENV VARIABLE_NAME="app"
ENV APP_HOST="0.0.0.0"
ENV APP_PORT="8000"

# Run uvicorn when the container launches
# The command will be: uvicorn src.mcp_server.main:app --host 0.0.0.0 --port 8000
CMD ["uvicorn", "$MODULE_NAME:$VARIABLE_NAME", "--host", "$APP_HOST", "--port", "$APP_PORT"]
