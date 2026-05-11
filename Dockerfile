# 1. Use the Conda base image
FROM docker.io/condaforge/mambaforge:latest

# 2. Set the working directory
WORKDIR /usr/src/app

# 3. Copy the Conda shopping list
COPY environment.yml .

# 4. Install dependencies into the base environment
RUN conda env update -n base -f environment.yml

# 5. Copy your project code
COPY . /usr/src/app

# 6. Set the Flask App environment variable (CRITICAL)
ENV FLASK_APP=app:app

# 7. Expose a default port (DO injects $PORT at runtime)
EXPOSE 8080

# 8. Start the app using Gunicorn WSGI for production stability
CMD gunicorn --bind 0.0.0.0:${PORT:-8080} app:app