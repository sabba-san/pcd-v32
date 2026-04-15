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

# 7. Expose the port
EXPOSE 5000

# 8. Start the app
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]