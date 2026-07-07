FROM python:3.11-slim

RUN apt-get update && apt-get install -y git ffmpeg && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir autogenstudio

# Create the working directory
RUN mkdir -p /home/user/app

WORKDIR /home/user/app

EXPOSE 8081

# Run as root (default)
ENTRYPOINT ["autogenstudio", "ui", "--port", "8081", "--host", "0.0.0.0", "--appdir", "/home/user/app"]