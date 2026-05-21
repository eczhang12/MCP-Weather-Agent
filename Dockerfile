# Start from an official Python image.
# Docker images are like templates for a small isolated computer environment.
# `python:3.12-slim` includes Python 3.12 but avoids many extra OS packages.
FROM python:3.12-slim AS final

# Set the working directory inside the container.
# Later Docker commands run relative to `/app`, and `python main.py` will run
# from this folder.
WORKDIR /app

# Install dependencies first so Docker can reuse this layer between code changes.
# Copy only `requirements.txt` first. Because dependencies change less often
# than source code, Docker can cache the `pip install` layer and rebuild faster.
COPY requirements.txt .

# Install the Python packages listed in `requirements.txt`.
# `--no-cache-dir` keeps the image smaller by not storing pip's download cache.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project files into the container.
COPY . .

# This is the command Docker runs when the container starts.
# It launches the same command-line agent as running `python main.py` locally.
CMD ["python", "main.py"]
