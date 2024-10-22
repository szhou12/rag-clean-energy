# Step 1: Use an official Python runtime as a parent image
FROM python:3.10-slim

# Step 2: Set the working directory in the container
WORKDIR /app

# Step 3: Copy the requirements file into the container at /app
COPY requirements.txt .

# Step 4: Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Step 5: Copy the rest of the application code into the container
COPY src /app/src
COPY webapp /app/webapp
COPY temp /app/temp
COPY downloads /app/downloads

# Step 6: Set the PYTHONPATH environment variable to include /app/src
# This allows imports from the /src directory in /webapp.
# This sets the PYTHONPATH permanently within the Docker image during the image build process.
# Every container that runs from this image will have /app/src in its PYTHONPATH by default.
ENV PYTHONPATH="/app/src"

# Step 7: Expose two container ports for Streamlit (8501 for app_client, 8502 for app_staff)
EXPOSE 8501
EXPOSE 8502
